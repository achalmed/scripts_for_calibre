#!/usr/bin/env luajit
--[[--
Pruebas de la lógica pura del complemento «Ecosistema» (`ecosistema.koplugin/ecosistema_logica.lua`).

    luajit koreader-plugin/pruebas.lua        # o el de KOReader: /usr/lib/koreader/luajit

Corre sobre datos de ejemplo y, si existe, sobre el índice real (solo lo lee). No abre KOReader ni toca
su configuración. Los temporales van a `$XDG_CACHE_HOME/ecosistema-koplugin-pruebas/` (el disco, no
/tmp) y se borran al terminar. Sale 0 si todo pasa y 1 si algo falla.
--]]--

local aqui = (arg and arg[0] or ""):match("^(.*)/[^/]*$") or "."
package.path = aqui .. "/ecosistema.koplugin/?.lua;" .. package.path
local L = require("ecosistema_logica")

local fallos, pasadas = 0, 0

local function prueba(nombre, fn)
    local ok, err = pcall(fn)
    if ok then
        pasadas = pasadas + 1
        print("  ✓ " .. nombre)
    else
        fallos = fallos + 1
        print("  ✗ " .. nombre .. "\n      " .. tostring(err))
    end
end

local function igual(obtenido, esperado, que)
    if obtenido ~= esperado then
        error(string.format("%s: se esperaba %q y salió %q", que or "valor", tostring(esperado), tostring(obtenido)), 2)
    end
end

local function cierto(v, que)
    if not v then error(que or "se esperaba verdadero", 2) end
end

local cache = os.getenv("XDG_CACHE_HOME")
if not cache or cache == "" then cache = (os.getenv("HOME") or ".") .. "/.cache" end
local tmp = cache .. "/ecosistema-koplugin-pruebas"
os.execute("rm -rf " .. L.citar_shell(tmp) .. " && mkdir -p " .. L.citar_shell(tmp))

local function escribir(ruta, contenido)
    local f = assert(io.open(ruta, "wb"))
    f:write(contenido)
    f:close()
end

-- Un índice de ejemplo (la forma que deja lib/indice.py).
local INDICE_EJEMPLO = [[
{"esquema": 1, "generado": "2026-10-31T23:03:09-0500", "biblioteca": "/datos/Mi biblioteca",
 "repo": "/datos/biblioteca-studio", "notas": "/datos/notas",
 "libros": {
   "48": {"titulo": "Cien años después 😀", "autores": ["Solbes, Mira", "Otro, Autor"],
          "carpeta": "Solbes, Mira/Cien años después (48)",
          "formatos": ["Solbes, Mira/Cien años después (48)/Cien años - Solbes.pdf"],
          "zotero_key": "XKNFW94X", "clave": "solbesmira60AnosDespues2004", "apuntes": "",
          "fichas": ["catalogacion/fichas/48_x.md", "catalogacion/fichas/48_y.md"],
          "nota": "/datos/notas/solbesmira60anosdespues2004.md"},
   "7": {"titulo": "Sin Zotero", "autores": [], "carpeta": "Anónimo/Sin Zotero (7)", "formatos": [],
         "zotero_key": "", "clave": "", "apuntes": "<div>…</div>", "fichas": [], "nota": "", "extra": null,
         "numeros": [1, -2.5, 3e2, true, false]}
 }}
]]

print("Lógica pura")

prueba("calibre_id de la ruta del documento", function()
    igual(L.calibre_id("/b/Autor/Título (48)/archivo.pdf"), "48")
    igual(L.calibre_id("/b/Autor/Título (2) (1234)/x (9).epub"), "1234", "el id es el de la carpeta")
    igual(L.calibre_id("/b/Autor/Título (48)/sub/archivo.pdf"), nil, "un nivel de más")
    igual(L.calibre_id("/b/Autor/Título/archivo.pdf"), nil, "sin id")
    igual(L.calibre_id(nil), nil, "sin ruta")
end)

prueba("hexadecimal y enlace de Calibre", function()
    igual(L.hex("biblioteca"), "6269626c696f74656361")
    igual(L.hex("é"), "c3a9", "UTF-8 tal cual")
    igual(L.id_biblioteca("/datos/Mi biblioteca/"), "Mi_biblioteca", "espacios como «_», como Calibre")
    igual(L.url_calibre("/datos/biblioteca", "48"), "calibre://show-book/_hex_-6269626c696f74656361/48")
    igual(L.url_zotero("XKNFW94X"), "zotero://select/library/items/XKNFW94X")
    igual(L.url_studio("48"), "biblioteca-studio://libro/48")
end)

prueba("entrecomillado para la terminal (ida y vuelta por sh)", function()
    local raro = "a'b \"c\" $HOME `id` ; (48) ñ"
    local p = assert(io.popen("printf '%s' " .. L.citar_shell(raro)))
    local salida = p:read("*a")
    p:close()
    igual(salida, raro)
    igual(L.orden({ "xdg-open", "x y" }), "'xdg-open' 'x y'")
end)

prueba("ruta del índice por XDG_STATE_HOME o HOME", function()
    local function entorno(t) return function(k) return t[k] end end
    igual(L.ruta_indice(entorno{ XDG_STATE_HOME = "/e/estado/", HOME = "/h" }), "/e/estado/biblioteca/indice.json")
    igual(L.ruta_indice(entorno{ HOME = "/h" }), "/h/.local/state/biblioteca/indice.json")
    igual(L.ruta_indice(entorno{ XDG_STATE_HOME = "", HOME = "/h" }), "/h/.local/state/biblioteca/indice.json")
end)

prueba("decodificador JSON", function()
    local v = assert(L.decodificar_json(INDICE_EJEMPLO))
    igual(v.esquema, 1)
    igual(v.libros["48"].titulo, "Cien años después 😀", "\\u y pares sustitutos")
    igual(#v.libros["48"].autores, 2)
    igual(v.libros["7"].extra, nil, "null")
    local n = v.libros["7"].numeros
    igual(n[1], 1); igual(n[2], -2.5); igual(n[3], 300); igual(n[4], true); igual(n[5], false)
    local e = assert(L.decodificar_json([["a\"b\\c\/d\n\tñ"]]))
    igual(e, "a\"b\\c/d\n\tñ")
    local malo, err = L.decodificar_json('{"a": 1,}')
    igual(malo, nil, "JSON roto")
    cierto(err and err:find("JSON inválido"), "mensaje del error")
    igual((L.decodificar_json('{"a":1} x')), nil, "texto sobrante")
end)

prueba("leer el índice: falta, roto, otro esquema y bueno", function()
    local indice, err = L.leer_indice(tmp .. "/no-existe.json")
    igual(indice, nil)
    cierto(err:find("No encuentro el índice") and err:find("indice.py"), "mensaje claro si falta")
    escribir(tmp .. "/roto.json", "{")
    indice, err = L.leer_indice(tmp .. "/roto.json")
    igual(indice, nil); cierto(err:find("no se pudo leer"), "mensaje si está roto")
    escribir(tmp .. "/esquema.json", '{"esquema": 2, "libros": {}}')
    indice, err = L.leer_indice(tmp .. "/esquema.json")
    igual(indice, nil); cierto(err:find("esquema 2"), "mensaje si cambia el esquema")
    escribir(tmp .. "/indice.json", INDICE_EJEMPLO)
    indice = assert(L.leer_indice(tmp .. "/indice.json"))
    igual(indice.libros["48"].clave, "solbesmira60AnosDespues2004")
end)

local indice = assert(L.decodificar_json(INDICE_EJEMPLO))

prueba("identificar el documento abierto", function()
    local ruta = "/datos/Mi biblioteca/Solbes, Mira/Cien años después (48)/Cien años - Solbes.pdf"
    local id, libro = L.identificar(ruta, indice)
    igual(id, "48"); igual(libro.zotero_key, "XKNFW94X")
    -- otra ruta a la misma carpeta (un enlace simbólico, otro punto de montaje)
    id = L.identificar("/mnt/copia/Solbes, Mira/Cien años después (48)/x.epub", indice)
    igual(id, "48", "la carpeta del libro basta")
    local _, _, err = L.identificar("/descargas/Otro (48)/x.pdf", indice)
    cierto(err and err:find("no es la del libro 48"), "un «(48)» fuera de la biblioteca no basta")
    _, _, err = L.identificar("/datos/Mi biblioteca/A/B (999)/x.pdf", indice)
    cierto(err and err:find("no figura en el índice"), "id ausente")
    _, _, err = L.identificar("/otra/carpeta/libro.pdf", indice)
    cierto(err and err:find("no está en la biblioteca Calibre"), "fuera de la biblioteca")
end)

prueba("resumen de «Qué es este libro»", function()
    local r = L.resumen("48", indice.libros["48"], false)
    cierto(r:find("Libro 48", 1, true), "id")
    cierto(r:find("Clave de Zotero: XKNFW94X", 1, true), "clave de Zotero")
    cierto(r:find("Clave para citar: solbesmira60AnosDespues2004", 1, true), "clave para citar")
    cierto(r:find("Lo citan 2 fichas.", 1, true), "fichas")
    cierto(r:find("(aún no existe)", 1, true), "nota ausente")
    local s = L.resumen("7", indice.libros["7"], false)
    cierto(s:find("sin ítem en Zotero", 1, true) and s:find("sin clave todavía", 1, true), "vacíos")
    cierto(s:find("Lo citan 0 fichas.", 1, true) and s:find("enlazados", 1, true), "cero fichas, apuntes")
end)

-- Anotaciones con la forma de ReaderAnnotation (KOReader 2026.03).
local ANOTACIONES = {
    { datetime = "2026-10-01 10:00:00", drawer = "lighten", text = "Primer resaltado\ncon dos líneas.",
      note = "Mi nota sobre él.", pageno = 12, page = 12 },
    { datetime = "2026-10-01 10:05:00", text = "Marcador de página", pageno = 13, page = 13 },  -- sin drawer
    { datetime = "2026-10-01 10:06:00", drawer = "underscore", text = "Segundo, con página de referencia.",
      pageno = 40, pageref = "xii", page = "/body/DocFragment[3]" },
    { datetime = "2026-10-01 10:07:00", drawer = "lighten", text = "", pageno = 50 },          -- recorte sin texto
    { datetime = "2026-10-01 10:08:00", drawer = "lighten", text = "Primer   resaltado con dos líneas.",
      pageno = 12 },                                                                            -- repetido
}

prueba("resaltados de las anotaciones", function()
    local r = L.resaltados(ANOTACIONES)
    igual(#r, 3, "fuera los marcadores y los recortes")
    igual(r[1].pagina, "12"); igual(r[1].nota, "Mi nota sobre él.")
    igual(r[2].pagina, "xii", "pageref antes que pageno")
    igual(r[2].nota, "")
end)

local BLOQUE_ESPERADO = table.concat({
    "## Resaltados de KOReader · 2026-10-31",
    "",
    "> Primer resaltado",
    "> con dos líneas.",
    "> — p. 12",
    "",
    "**Nota:** Mi nota sobre él.",
    "",
    "> Segundo, con página de referencia.",
    "> — p. xii",
    "",
}, "\n")

prueba("bloque Markdown sin duplicados", function()
    local r = L.resaltados(ANOTACIONES)
    local bloque, nuevos, repetidos = L.bloque(r, "", "2026-10-31")
    igual(bloque, BLOQUE_ESPERADO, "bloque")
    igual(nuevos, 2); igual(repetidos, 1, "el repetido dentro del mismo lote")
    -- repetir: nada nuevo
    local otra, n2, rep2 = L.bloque(r, "# Notas\n\n" .. bloque, "2026-11-01")
    igual(otra, nil, "al repetir no hay bloque"); igual(n2, 0); igual(rep2, 3)
    -- un resaltado nuevo después: solo ese
    local mas = { r[1], r[2], { texto = "Tercero, nuevo.", pagina = "77", nota = "" } }
    local b3, n3, rep3 = L.bloque(mas, bloque, "2026-11-02")
    igual(n3, 1); igual(rep3, 2)
    igual(b3, "## Resaltados de KOReader · 2026-11-02\n\n> Tercero, nuevo.\n> — p. 77\n")
    -- el resaltado ya copiado a mano en otra forma (sin «>», con otros saltos) también cuenta
    local _, n4 = L.bloque({ r[2] }, "Copié: Segundo, con\npágina de referencia. Fin.", "2026-11-02")
    igual(n4, 0, "reconoce el texto aunque cambien los saltos")
    -- sin página
    local b5 = L.bloque({ { texto = "Sin página" } }, "", "2026-11-03")
    cierto(b5:find("> — p. ?", 1, true), "página desconocida")
end)

prueba("encabezado de una nota nueva y lo que se añade", function()
    local libro = indice.libros["48"]
    local enc = L.encabezado("48", libro)
    igual(enc, "---\ntipo: lectura\ncalibre_id: 48\nzotero_key: XKNFW94X\n" ..
        "clave_bibtex: solbesmira60AnosDespues2004\n---\n# Cien años después 😀\n")
    igual(L.encabezado("7", indice.libros["7"]):match("zotero_key:[^\n]*"), "zotero_key: ", "vacío")
    local b = "## B\n"
    igual(L.texto_a_anadir("", false, b, "48", libro), enc .. "\n" .. b, "archivo nuevo")
    igual(L.texto_a_anadir("x", true, b), "\n\n" .. b, "sin salto final")
    igual(L.texto_a_anadir("x\n", true, b), "\n" .. b, "con un salto")
    igual(L.texto_a_anadir("x\n\n", true, b), b, "con línea en blanco")
    igual(L.texto_a_anadir("", true, b), b, "archivo vacío")
end)

prueba("añadir dos veces al mismo archivo no duplica ni reescribe", function()
    local ruta = tmp .. "/nota.md"
    local libro = indice.libros["48"]
    local r = L.resaltados(ANOTACIONES)
    for vuelta = 1, 2 do
        local f = io.open(ruta, "rb")
        local contenido, existe = "", false
        if f then contenido, existe = f:read("*a"), true; f:close() end
        local bloque = L.bloque(r, contenido, "2026-10-31")
        if vuelta == 2 then igual(bloque, nil, "segunda vuelta") break end
        local g = assert(io.open(ruta, "ab"))
        g:write(L.texto_a_anadir(contenido, existe, bloque, "48", libro))
        g:close()
    end
    local f = assert(io.open(ruta, "rb")); local final = f:read("*a"); f:close()
    igual(final, L.encabezado("48", libro) .. "\n" .. BLOQUE_ESPERADO, "archivo final")
end)

-- ---------------------------------------------------------------------------------------------------
print("Índice real (solo lectura)")

local ruta_real = L.ruta_indice()
local f_real = io.open(ruta_real, "rb")
if not f_real then
    print("  · no hay índice real en " .. ruta_real .. ": se omite")
else
    f_real:close()
    local t0 = os.clock()
    local real, err = L.leer_indice(ruta_real)
    local segundos = os.clock() - t0
    prueba("se lee con el decodificador del módulo", function()
        cierto(real, err)
        local n = 0
        for _ in pairs(real.libros) do n = n + 1 end
        cierto(n > 0, "sin libros")
        print(string.format("      %d libros en %.2f s; generado %s", n, segundos, L.texto(real.generado)))
    end)
    if real then
        prueba("cada formato del índice se identifica como su propio libro", function()
            local biblioteca = L.texto(real.biblioteca):gsub("/+$", "")
            local formatos, malos = 0, {}
            for id, libro in pairs(real.libros) do
                for _, formato in ipairs(libro.formatos or {}) do
                    formatos = formatos + 1
                    local obtenido, _, e = L.identificar(biblioteca .. "/" .. formato, real)
                    if obtenido ~= id and #malos < 5 then malos[#malos + 1] = id .. ": " .. tostring(e) end
                end
            end
            print(string.format("      %d formatos comprobados", formatos))
            cierto(#malos == 0, table.concat(malos, "; "))
        end)
        prueba("enlace de Calibre de la biblioteca real", function()
            local url = L.url_calibre(real.biblioteca, "1")
            cierto(url:match("^calibre://show%-book/_hex_%-%x+/1$"), url)
        end)
        prueba("el resumen de cada libro se arma sin errores", function()
            for id, libro in pairs(real.libros) do
                local r = L.resumen(id, libro, false)
                cierto(r:find("Libro " .. id, 1, true), id)
            end
        end)
        -- Si KOReader trae rapidjson, ambos decodificadores deben dar lo mismo.
        local ok_rj, rapidjson = pcall(function()
            package.cpath = "/usr/lib/koreader/common/?.so;" .. package.cpath
            return require("rapidjson")
        end)
        if ok_rj and rapidjson then
            prueba("rapidjson de KOReader y el decodificador del módulo coinciden", function()
                local otro = assert(L.leer_indice(ruta_real, rapidjson.decode))
                for id, libro in pairs(real.libros) do
                    local b = otro.libros[id]
                    cierto(b, "falta " .. id)
                    for _, campo in ipairs({ "titulo", "carpeta", "zotero_key", "clave", "apuntes", "nota" }) do
                        igual(L.texto(b[campo]), L.texto(libro[campo]), id .. "." .. campo)
                    end
                    igual(#(b.fichas or {}), #(libro.fichas or {}), id .. ".fichas")
                end
            end)
        else
            print("  · rapidjson de KOReader no se pudo cargar desde luajit: se omite la comparación")
        end
    end
end

os.execute("rm -rf " .. L.citar_shell(tmp))
print(string.format("\n%d pruebas en verde, %d en rojo", pasadas, fallos))
os.exit(fallos == 0 and 0 or 1)
