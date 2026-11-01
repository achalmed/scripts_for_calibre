--[[--
Complemento «Ecosistema» de KOReader: el libro abierto en el ecosistema de la biblioteca.

Añade al menú de herramientas del lector un submenú «Ecosistema» con: qué es este libro, abrirlo en
Calibre, en Zotero o en Biblioteca Studio, copiar la clave para citar, pasar los resaltados a la nota
de lectura y sincronizar con Calibre.

Lee (solo lectura) el índice que genera `lib/indice.py --aplicar` de biblioteca-studio. No escribe en
la base de Calibre: el enlace de los apuntes lo pide a `koreader/main.sh --apuntes`, que escribe por
la puerta. Lo único que escribe este complemento es la nota de lectura del libro, y solo añadiendo al
final. Las órdenes externas corren en segundo plano: nada bloquea la interfaz.

La lógica pura vive en `ecosistema_logica.lua` (la prueba `koreader-plugin/pruebas.lua`).

@module koplugin.ecosistema
--]]--

local DataStorage = require("datastorage")
local Device = require("device")
local InfoMessage = require("ui/widget/infomessage")
local TextViewer = require("ui/widget/textviewer")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local lfs = require("libs/libkoreader-lfs")
local logger = require("logger")

local L = require("ecosistema_logica")

-- rapidjson (de serie en KOReader) es mucho más rápido que el decodificador en Lua puro del módulo.
local decodificar
do
    local ok, rapidjson = pcall(require, "rapidjson")
    if ok and rapidjson and rapidjson.decode then
        decodificar = function(texto)
            local valor, err = rapidjson.decode(texto)
            if valor == nil then return nil, err end
            return valor
        end
    end
end

-- Cada cuánto se mira si terminó una orden en segundo plano, y cuántas veces como mucho.
local INTERVALO_SONDEO = 1
local SONDEOS_MAXIMOS = 600

local MENSAJE_ENLACE_DIFERIDO = "La nota se enlazará desde Biblioteca Studio cuando Calibre esté cerrado."

local Ecosistema = WidgetContainer:extend{
    name = "ecosistema",
    is_doc_only = true,
}

function Ecosistema:init()
    self._contador = 0
    self.ui.menu:registerToMainMenu(self)
end

-- ---------------------------------------------------------------------------------------------------
-- Avisos y órdenes externas
-- ---------------------------------------------------------------------------------------------------

function Ecosistema:avisar(texto, segundos)
    UIManager:show(InfoMessage:new{ text = texto, timeout = segundos })
end

--- Lanza una orden en segundo plano y se olvida de ella.
function Ecosistema:lanzar(args)
    local orden = L.orden(args) .. " </dev/null >/dev/null 2>&1 &"
    logger.dbg("Ecosistema: lanzar", orden)
    os.execute(orden)
end

--- Lanza una orden en segundo plano y, cuando termina, llama a `al_terminar(codigo, ultima_linea)`.
-- El código de salida llega por un archivo en la caché de KOReader, que se sondea sin bloquear.
function Ecosistema:ejecutar(args, al_terminar)
    self._contador = self._contador + 1
    local base = string.format("%s/cache/ecosistema-%d-%d", DataStorage:getDataDir(), os.time(), self._contador)
    local rc, rc_tmp, log = base .. ".rc", base .. ".rc.tmp", base .. ".log"
    local orden = string.format("(%s >%s 2>&1; echo $? >%s; mv %s %s) </dev/null >/dev/null 2>&1 &",
        L.orden(args), L.citar_shell(log), L.citar_shell(rc_tmp), L.citar_shell(rc_tmp), L.citar_shell(rc))
    logger.dbg("Ecosistema: ejecutar", orden)
    os.execute(orden)

    local sondeos = 0
    local function comprobar()
        sondeos = sondeos + 1
        local f = io.open(rc, "r")
        if not f then
            if sondeos < SONDEOS_MAXIMOS then
                UIManager:scheduleIn(INTERVALO_SONDEO, comprobar)
            else
                al_terminar(nil, "la orden no terminó a tiempo")
            end
            return
        end
        local codigo = tonumber(f:read("*l") or "")
        f:close()
        local ultima = ""
        local g = io.open(log, "r")
        if g then
            for linea in g:lines() do
                if L.recortar(linea) ~= "" then ultima = L.recortar(linea) end
            end
            g:close()
        end
        os.remove(rc)
        os.remove(log)
        al_terminar(codigo, ultima)
    end
    UIManager:scheduleIn(INTERVALO_SONDEO, comprobar)
end

-- ---------------------------------------------------------------------------------------------------
-- El índice y el libro abierto
-- ---------------------------------------------------------------------------------------------------

--- El índice, releído solo si cambió en el disco. Devuelve la tabla, o nil y el mensaje.
function Ecosistema:indice()
    local ruta = L.ruta_indice()
    local modificado = lfs.attributes(ruta, "modification")
    if not modificado then
        self._indice, self._indice_modificado = nil, nil
        return L.leer_indice(ruta)   -- da el mensaje de «no encuentro el índice»
    end
    if self._indice and self._indice_modificado == modificado then
        return self._indice
    end
    local indice, err = L.leer_indice(ruta, decodificar)
    if not indice and decodificar then
        indice, err = L.leer_indice(ruta)   -- por si rapidjson no pudo con él
    end
    self._indice, self._indice_modificado = indice, indice and modificado or nil
    return indice, err
end

--- El libro abierto: id, entrada del índice e índice; o nada, tras avisar por qué.
function Ecosistema:libroActual()
    local ruta = self.ui.document and self.ui.document.file or ""
    if not L.calibre_id(ruta) then
        local _, _, err = L.identificar(ruta, { libros = {} })
        self:avisar(err)
        return
    end
    local indice, err = self:indice()
    if not indice then
        self:avisar(err)
        return
    end
    local id, libro, err_libro = L.identificar(ruta, indice)
    if not id then
        self:avisar(err_libro)
        return
    end
    return id, libro, indice
end

local function existe(ruta)
    return lfs.attributes(ruta, "mode") ~= nil
end

local function leer_archivo(ruta)
    local f = io.open(ruta, "rb")
    if not f then return "", false end
    local contenido = f:read("*a") or ""
    f:close()
    return contenido, true
end

-- ---------------------------------------------------------------------------------------------------
-- Las acciones del menú
-- ---------------------------------------------------------------------------------------------------

function Ecosistema:queEs()
    local id, libro = self:libroActual()
    if not id then return end
    local nota = L.texto(libro.nota)
    self:avisar(L.resumen(id, libro, nota ~= "" and existe(nota)))
end

function Ecosistema:abrirCalibre()
    local id, _, indice = self:libroActual()
    if not id then return end
    if L.texto(indice.biblioteca) == "" then
        self:avisar("El índice no dice cuál es la carpeta de la biblioteca Calibre: vuelva a generarlo.")
        return
    end
    self:lanzar({ "xdg-open", L.url_calibre(indice.biblioteca, id) })
    self:avisar("Abriendo el libro " .. id .. " en Calibre…", 3)
end

function Ecosistema:abrirZotero()
    local id, libro = self:libroActual()
    if not id then return end
    if L.texto(libro.zotero_key) == "" then
        self:avisar("El libro " .. id .. " no tiene ítem en Zotero todavía.")
        return
    end
    self:lanzar({ "xdg-open", L.url_zotero(libro.zotero_key) })
    self:avisar("Abriendo el ítem " .. libro.zotero_key .. " en Zotero…", 3)
end

function Ecosistema:abrirStudio()
    local id = self:libroActual()
    if not id then return end
    self:lanzar({ "xdg-open", L.url_studio(id) })
    self:avisar("Abriendo el libro " .. id .. " en Biblioteca Studio…", 3)
end

function Ecosistema:copiarClave()
    local id, libro = self:libroActual()
    if not id then return end
    local clave = L.texto(libro.clave)
    if clave == "" then
        self:avisar("El libro " .. id .. " no tiene clave para citar todavía (se la da Zotero con Better BibTeX).")
        return
    end
    if not (Device.input and Device.input.setClipboardText) then
        self:avisar("Este dispositivo no tiene portapapeles. La clave es:\n\n" .. clave)
        return
    end
    Device.input.setClipboardText(clave)
    self:avisar("Clave copiada al portapapeles:\n\n" .. clave, 3)
end

--- Pasar mis resaltados a los apuntes: vista previa y, si se confirma, añadir al final de la nota.
function Ecosistema:pasarResaltados()
    local id, libro, indice = self:libroActual()
    if not id then return end
    local ruta = L.texto(libro.nota)
    if ruta == "" then
        self:avisar("El índice no trae la ruta de la nota de lectura del libro " .. id .. ".")
        return
    end
    local anotacion = self.ui.annotation
    if not (anotacion and anotacion.annotations) then
        self:avisar("Esta versión de KOReader no expone las anotaciones del libro.")
        return
    end
    if anotacion.updatePageNumbers then anotacion:updatePageNumbers(true) end
    local resaltados = L.resaltados(anotacion.annotations)
    if #resaltados == 0 then
        self:avisar("Este libro no tiene resaltados todavía.")
        return
    end

    local contenido, ya_existe = leer_archivo(ruta)
    local bloque, nuevos, repetidos = L.bloque(resaltados, contenido, os.date("%Y-%m-%d"))
    if not bloque then
        self:avisar(string.format("Los %d resaltados ya están en los apuntes (%s).", repetidos, L.nombre_base(ruta)))
        return
    end

    local titulo = string.format("Añadir %d %s a %s", nuevos, nuevos == 1 and "resaltado" or "resaltados",
        L.nombre_base(ruta))
    local cabecera = {}
    if not ya_existe then cabecera[#cabecera + 1] = "La nota no existe: se creará con su encabezado." end
    if repetidos > 0 then
        cabecera[#cabecera + 1] = string.format("%d ya %s en la nota y no se repite%s.", repetidos,
            repetidos == 1 and "estaba" or "estaban", repetidos == 1 and "" or "n")
    end
    local vista = L.texto_a_anadir(contenido, ya_existe, bloque, id, libro)
    if #cabecera > 0 then vista = table.concat(cabecera, "\n") .. "\n\n" .. vista end

    local visor
    visor = TextViewer:new{
        title = titulo,
        text = vista,
        buttons_table = {
            {
                {
                    text = "Cancelar",
                    callback = function() UIManager:close(visor) end,
                },
                {
                    text = "Añadir a los apuntes",
                    callback = function()
                        UIManager:close(visor)
                        self:anadirResaltados(id, libro, indice, ruta, resaltados)
                    end,
                },
            },
        },
    }
    UIManager:show(visor)
end

--- Añade al final de la nota (la crea con su encabezado si no existe); nunca reescribe lo que hay.
function Ecosistema:anadirResaltados(id, libro, indice, ruta, resaltados)
    -- Se relee justo antes de escribir, por si la nota cambió mientras se miraba la vista previa.
    local contenido, ya_existe = leer_archivo(ruta)
    local bloque, nuevos = L.bloque(resaltados, contenido, os.date("%Y-%m-%d"))
    if not bloque then
        self:avisar("Los resaltados ya están en los apuntes: no se añadió nada.")
        return
    end
    if not ya_existe and lfs.attributes(L.carpeta_de(ruta), "mode") ~= "directory" then
        self:avisar("No existe la carpeta de la nota:\n" .. L.carpeta_de(ruta))
        return
    end
    local f, err = io.open(ruta, "ab")
    if not f then
        self:avisar("No se pudo abrir la nota para añadir:\n" .. tostring(err))
        return
    end
    local ok, err_escritura = f:write(L.texto_a_anadir(contenido, ya_existe, bloque, id, libro))
    f:close()
    if not ok then
        self:avisar("No se pudo escribir en la nota:\n" .. tostring(err_escritura))
        return
    end
    local hecho = string.format("%d %s añadido%s a %s.", nuevos, nuevos == 1 and "resaltado" or "resaltados",
        nuevos == 1 and "" or "s", L.nombre_base(ruta))

    if L.texto(libro.apuntes) ~= "" then
        self:avisar(hecho, 4)
        return
    end
    -- El libro no tenía apuntes enlazados en Calibre: se pide por la puerta (koreader/main.sh --apuntes).
    local orden = L.texto(indice.repo):gsub("/+$", "") .. "/koreader/main.sh"
    if L.texto(indice.repo) == "" or not existe(orden) then
        self:avisar(hecho .. "\n\nNo encuentro koreader/main.sh de biblioteca-studio. " .. MENSAJE_ENLACE_DIFERIDO)
        return
    end
    self:avisar(hecho .. "\n\nEnlazando la nota en Calibre…", 3)
    self:ejecutar({ orden, "--apuntes", id, ruta, "Apuntes de lectura" }, function(codigo, ultima)
        if codigo == 0 then
            libro.apuntes = "enlazado"   -- en memoria, hasta que se regenere el índice
            self:avisar("La nota quedó enlazada en Calibre (#apuntes del libro " .. id .. ").", 4)
        elseif codigo == 75 or ultima:lower():find("abierto", 1, true) then
            self:avisar("Calibre está abierto u ocupado. " .. MENSAJE_ENLACE_DIFERIDO)
        else
            logger.warn("Ecosistema: --apuntes salió con", codigo, ultima)
            self:avisar("No se pudo enlazar la nota en Calibre (código " .. tostring(codigo) .. ": " ..
                ultima .. "). " .. MENSAJE_ENLACE_DIFERIDO)
        end
    end)
end

function Ecosistema:sincronizar()
    -- Que KOReader vuelque progreso y estadísticas antes de que el sincronizador los lea.
    if self.ui.saveSettings then self.ui:saveSettings() end
    self:ejecutar({ "systemctl", "--user", "start", "--no-block", "koreader-calibre-sync.service" },
        function(codigo, ultima)
            if codigo == 0 then
                self:avisar("Sincronización con Calibre pedida: corre en segundo plano y, si Calibre " ..
                    "está abierto, la pasada se salta y reintenta en el siguiente turno del timer.", 5)
            else
                self:avisar("systemd no pudo empezar koreader-calibre-sync.service (código " ..
                    tostring(codigo) .. "): " .. ultima)
            end
        end)
end

-- ---------------------------------------------------------------------------------------------------
-- El menú
-- ---------------------------------------------------------------------------------------------------

function Ecosistema:addToMainMenu(menu_items)
    menu_items.ecosistema = {
        text = "Ecosistema",
        sorting_hint = "tools",
        sub_item_table = {
            { text = "Qué es este libro", callback = function() self:queEs() end },
            { text = "Abrir en Calibre", callback = function() self:abrirCalibre() end },
            { text = "Abrir en Zotero", callback = function() self:abrirZotero() end },
            { text = "Abrir en Biblioteca Studio", callback = function() self:abrirStudio() end },
            { text = "Copiar la clave para citar", callback = function() self:copiarClave() end,
              separator = true },
            { text = "Pasar mis resaltados a los apuntes", callback = function() self:pasarResaltados() end,
              separator = true },
            { text = "Sincronizar con Calibre ahora", callback = function() self:sincronizar() end },
        },
    }
end

return Ecosistema
