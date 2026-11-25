"""El área «Lectura» (decisiones §9.6): el controlador lee la base de lectura de la muestra, en solo lectura."""
from __future__ import annotations

from pathlib import Path

from conftest import requiere_binding


@requiere_binding
def test_lectura_resumen_libros_y_subrayados(app, entorno, muestra):
    from biblioteca_app.controladores.lectura import Lectura
    db = Path(muestra.entorno["LECTURA_DB"])
    antes = db.stat().st_mtime_ns
    lec = Lectura(None, vigilar=False)
    assert lec.hayBase and lec.rutaBase == str(db)
    r = lec.resumen
    assert r["anotaciones"] == 4 and r["compartidas"] == 1 and "KOReader 2" in r["origenes"]
    assert len(lec.semanas) == 12
    assert [l["titulo"] for l in lec.libros][0].startswith("Economía")
    primero = lec.libros[0]["id"]
    assert lec.actualId == primero                       # sin libro en el catálogo, el más reciente
    b = lec.libro
    assert b["hay"] and b["total"] == 4 and {p["origen"] for p in b["progreso"]} == {"KOReader", "Zotero"}
    assert [o["nombre"] for o in lec.origenes] == ["", "koreader", "zotero", "okular", "yachay"]
    compartido = lec.anotaciones[0]
    assert "KOReader, Zotero" in compartido["detalle"] and compartido["cita"].startswith("“Las ciudades") and "(p. 12)" in compartido["cita"]
    lec.fijarOrigen("zotero")
    assert len(lec.anotaciones) == 1
    lec.fijarOrigen("")
    assert len(lec.anotaciones) == 4
    # el rediseño (§9.9): las cuatro cifras, el mapa de calor y el color de cada herramienta
    assert [c["rotulo"] for c in lec.cifras] == ["Subrayados", "Horas en 12 semanas", "Libros con lectura", "Racha"]
    assert lec.cifras[0]["valor"] == "4" and lec.cifras[2]["valor"] == "2"
    assert len(lec.dias) == 84 and any(d["nivel"] > 0 for d in lec.dias) and lec.dias[0]["texto"].startswith("lun ")
    assert lec.colores["koreader"] == "#378ADD" and lec.colores["yachay"] == "#7F77DD" and lec.colores["nawinchay"] == "#BA7517"
    assert compartido["colorOrigen"] == "#378ADD" and compartido["origen"] == "KOReader"
    assert {a["colorOrigen"] for a in lec.anotaciones} == {"#378ADD", "#1D9E75", "#7F77DD"}
    assert b["fraccion"] == 0.42 and next(p for p in b["progreso"] if p["origen"] == "KOReader")["color"] == "#378ADD"
    assert db.stat().st_mtime_ns == antes                # la ventana no escribe la base


@requiere_binding
def test_lectura_sin_base(app, entorno, muestra, monkeypatch, tmp_path):
    from biblioteca_app.controladores.lectura import Lectura
    monkeypatch.setenv("LECTURA_DB", str(tmp_path / "no-existe" / "lectura.sqlite"))
    lec = Lectura(None, vigilar=False)
    assert not lec.hayBase and lec.libros == [] and not lec.libro["hay"] and lec.cifras == []
    assert not (tmp_path / "no-existe").exists()


def test_las_operaciones_de_la_base_de_lectura():
    from biblioteca_app.servicios import operaciones as ops
    o = ops.operacion("base_lectura")
    assert o.argv(False) == ["python3", "lectura_base/main.py", "sincronizar"] and o.bases == ()
    z = ops.operacion("lectura_a_zotero")
    assert z.argv(True)[-1] == "--aplicar" and z.bases == ("zotero",)
    for destino in ("koreader", "okular"):
        o = ops.operacion(f"lectura_a_{destino}")
        assert o.argv(True)[-3:] == ["exportar", destino, "--aplicar"] and o.bases == ()


def test_estado_del_timer_y_resumen_de_una_vuelta():
    """Lo que la tarjeta «Sincronización» lee de systemd y cómo cuenta una vuelta de `main.py ciclo` (§9.8)."""
    from datetime import date
    from biblioteca_app.controladores.lectura import estado_timer, resumen_ciclo
    hoy = date.today().isoformat()
    e = estado_timer(f"LoadState=loaded\nActiveState=active\nLastTriggerUSec=Tue {hoy} 23:18:48 -05\n"
                     "NextElapseUSecRealtime=Wed 2030-01-02 00:18:48 -05\n")
    assert e == {"instalado": True, "activo": True, "ultima": "23:18", "proxima": "02/01 00:18"}
    assert estado_timer(f"LoadState=loaded\nActiveState=active\nLastTriggerUSec=Tue {hoy} 10:05:00 -05\nNextElapseUSecRealtime=\n")["proxima"] == "11:05"
    assert estado_timer("LoadState=not-found\nActiveState=inactive\n")["instalado"] is False
    assert estado_timer("", 1) == {"instalado": False, "activo": False, "ultima": "", "proxima": ""}
    assert resumen_ciclo({"ida": [], "vuelta": {}, "saltados": []}, 0) == ("Nada nuevo: la base y las herramientas ya coinciden", "informacion")
    texto, tipo = resumen_ciclo({"ida": [{"altas": 2, "cambios": 0, "borradas": 0, "progreso": {"altas": 1, "cambios": 0}}],
                                 "vuelta": {"zotero": 2}, "saltados": ["okular: Okular está abierto"]}, 75)
    assert tipo == "aviso" and texto.startswith("2 subrayados") and "Zotero (2)" in texto and texto.endswith("Okular")
    assert resumen_ciclo(None, 1)[1] == "error"


class SincroniaFalsa:
    def __init__(self):
        self.activo, self.vueltas = True, 0

    def estado(self):
        return {"instalado": True, "activo": self.activo, "ultima": "23:18", "proxima": "00:18"}

    def fijar(self, activo):
        self.activo = activo
        return True, ""

    def ciclo(self):
        self.vueltas += 1
        return {"ida": [], "vuelta": {"yachay": 3}, "saltados": []}, 0


@requiere_binding
def test_sincronizar_ahora_y_el_interruptor_de_cada_hora(app, entorno, muestra):
    from biblioteca_app.controladores.lectura import Lectura
    falsa = SincroniaFalsa()
    lec = Lectura(None, vigilar=False, sincronia=falsa)
    avisos = []
    lec.aviso.connect(lambda texto, tipo: avisos.append((texto, tipo)))
    lec.leerTimer()
    assert lec.timerActivo and lec.estadoSincronia == "última vuelta 23:18 · próxima 00:18"
    lec.sincronizarAhora()
    assert falsa.vueltas == 1 and not lec.sincronizando
    assert avisos[-1] == ("llevados a Yachay (3)", "positivo") and lec.estadoSincronia.startswith("ahora: llevados a Yachay")
    lec.fijarTimer(False)
    assert not lec.timerActivo and "apagada" in lec.estadoSincronia and "solo con el botón" in avisos[-1][0]


@requiere_binding
def test_el_mapa_de_lo_leido_sale_del_diario_de_nawinchay(app, entorno, muestra):
    """2026-11-19: los conceptos, relaciones y temas que la IA estructuró en las sesiones guiadas de Ñawinchay, leídos de
    su diario de muestra en solo lectura; un concepto del primer libro que también aparece en otro lo dice."""
    from biblioteca_app.controladores.lectura import Lectura
    from biblioteca_app.servicios import mapa_lectura
    lec = Lectura(None, vigilar=False)
    m = lec.mapa
    assert m["sesiones"] == 2 and len(m["conceptos"]) == 5 and len(m["relaciones"]) == 5
    ag = m["conceptos"][0]
    assert ag["termino"] == "Economía de aglomeración" and ag["veces"] == 2 and len(ag["definiciones"]) == 2
    ch = next(c for c in m["conceptos"] if c["termino"] == "Capital humano")
    assert ch["otros"] == 1                                 # también en el segundo libro de muestra
    assert m["etiquetas"][0] == ["localización", 2]
    assert mapa_lectura.mapa_libro(-1)["conceptos"] == []


def test_la_cifra_de_un_libro_para_la_fila_del_catalogo():
    """2026-11-22: la fila del catálogo dice lo leído (avance, subrayados, horas) en vez de la clave para citar."""
    from biblioteca_app.controladores.lectura import cifra_libro
    assert cifra_libro({"fraccion": 0.83, "porcentaje": 83, "anotaciones": 4, "segundos": 4380, "tiempo": "1 h 13 min"}) == \
        "83 % · 4 subrayados · 1 h 13 min"
    assert cifra_libro({"fraccion": None, "porcentaje": 0, "anotaciones": 1, "segundos": 0, "tiempo": ""}) == "1 subrayado"
    assert cifra_libro({"fraccion": None, "porcentaje": 0, "anotaciones": 0, "segundos": 0, "tiempo": ""}) == ""


@requiere_binding
def test_el_mapa_global_junta_los_diarios_de_toda_la_biblioteca(app, entorno, muestra):
    """2026-11-24 (§9.19): un solo barrido de los diarios da el mapa de toda la biblioteca; cada concepto sabe en qué
    libros aparece, y el del libro se arma de ahí (antes cada libro rehacía el mapa de todos los demás)."""
    from biblioteca_app.servicios import mapa_lectura
    g = mapa_lectura.mapa_global()
    assert g["libros"] == 2 and g["sesiones"] == 3            # los dos libros de muestra con diario
    assert len(g["conceptos"]) == 5 and len(g["relaciones"]) == 5
    ch = g["conceptos"][0]                                     # el que está en más libros va primero
    assert ch["termino"] == "Capital humano" and ch["nlibros"] == 2 and len(ch["libros"]) == 2
    assert ch["veces"] == 2 and len(ch["definiciones"]) == 2   # una definición de cada libro
    assert dict(g["etiquetas"])["localización"] == 2
    assert "por_libro" not in g                                # eso se queda en la caché
    uno = mapa_lectura.mapa_libro(ch["libros"][0])             # el del libro sigue dando lo suyo y lo que comparte
    assert next(c for c in uno["conceptos"] if c["termino"] == "Capital humano")["otros"] == 1
    uno["conceptos"][0]["termino"] = "tocado"                  # lo que entrega es copia: la caché no se ensucia
    assert mapa_lectura.mapa_global()["conceptos"][0]["termino"] == "Capital humano"


def test_el_estado_de_lectura_de_un_libro():
    """2026-11-24 (§9.19): «complete» o el progreso casi al final es leído; algo empezado, en curso; lo demás, sin abrir."""
    from biblioteca_app.servicios import mapa_lectura as m
    assert m.estado_lectura({"ko_estado": "complete", "ko_progreso": 1.0}) == m.LEIDO
    assert m.estado_lectura({"ko_estado": "", "ko_progreso": 0.97}) == m.LEIDO
    assert m.estado_lectura({"ko_estado": "reading", "ko_progreso": 0.4}) == m.EN_CURSO
    assert m.estado_lectura({"ko_estado": "", "ko_progreso": 0.0}) == m.SIN_ABRIR
    assert m.estado_lectura({"ko_estado": "", "ko_progreso": None}) == m.SIN_ABRIR


def test_la_cobertura_dice_por_tema_cuanto_falta():
    """2026-11-24 (§9.19): por etiqueta del vocabulario cerrado, cuántos libros hay, cuántos leídos, en curso y sin
    abrir, y cuántos conceptos salieron de ellos; primero el tema con más libros sin abrir, que es lo que falta."""
    from biblioteca_app.servicios import mapa_lectura as m
    libros = [{"id": "1", "etiquetas": ["economia", "ciudades"], "ko_estado": "complete", "ko_progreso": 1.0},
              {"id": "2", "etiquetas": ["economia"], "ko_estado": "reading", "ko_progreso": 0.4},
              {"id": "3", "etiquetas": ["economia", "filosofia"], "ko_estado": "", "ko_progreso": None},
              {"id": "4", "etiquetas": ["filosofia"], "ko_estado": "", "ko_progreso": None}]
    # el «id» va en texto porque así lo entrega `catalogo.leer`, y el mapa lo tiene en número: con enteros aquí la
    # prueba pasaba y la cobertura real decía «0 conceptos» en todos los temas (2026-11-24)
    mapa = {"conceptos": [{"termino": "Aglomeración", "libros": [1]}, {"termino": "Ciudad", "libros": [1, 2]}]}
    c = m.cobertura(libros, mapa)
    assert c["libros"] == 4 and c[m.LEIDO] == 1 and c[m.EN_CURSO] == 1 and c[m.SIN_ABRIR] == 2 and c["conceptos"] == 2
    filosofia, economia = c["temas"][0], next(t for t in c["temas"] if t["tema"] == "economia")
    assert filosofia["tema"] == "filosofia"                    # dos libros sin abrir: lo que más falta
    assert filosofia["libros"] == 2 and filosofia[m.SIN_ABRIR] == 2 and filosofia["conceptos"] == 0
    assert economia["libros"] == 3 and economia[m.LEIDO] == 1 and economia[m.EN_CURSO] == 1 and economia[m.SIN_ABRIR] == 1
    assert economia["conceptos"] == 3                          # 2 conceptos del libro 1 y 1 del libro 2


def test_la_cobertura_dice_de_que_trata_cada_tema_segun_openalex():
    """2026-11-24 (§9.20): las materias de OpenAlex (caché de `lib/temas_openalex.py`, solo lectura) dicen de qué trata
    un tema aunque ninguno de sus libros se haya leído; se muestran las tres que más se repiten."""
    from biblioteca_app.servicios import mapa_lectura as m
    libros = [{"id": "1", "etiquetas": ["macroeconomia"], "ko_estado": "", "ko_progreso": None},
              {"id": "2", "etiquetas": ["macroeconomia"], "ko_estado": "", "ko_progreso": None},
              {"id": "3", "etiquetas": ["legislacion"], "ko_estado": "", "ko_progreso": None}]
    materias = {1: ["Monetary Policy and Economic Impact", "Economic Theory and Policy"],
                2: ["Monetary Policy and Economic Impact", "Inflation dynamics"]}
    c = m.cobertura(libros, {"conceptos": []}, materias)
    macro = next(t for t in c["temas"] if t["tema"] == "macroeconomia")
    assert macro["con_materias"] == 2 and macro["materias"][0] == "Monetary Policy and Economic Impact"
    assert len(macro["materias"]) == 3 and macro["conceptos"] == 0      # ningún libro leído con guía, y aun así se sabe de qué trata
    legislacion = next(t for t in c["temas"] if t["tema"] == "legislacion")
    assert legislacion["con_materias"] == 0 and legislacion["materias"] == []
    assert c["con_materias"] == 2
