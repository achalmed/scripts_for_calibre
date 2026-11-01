--[[--
Lógica pura del complemento «Ecosistema»: sin dependencias de KOReader.

Todo lo que se puede probar fuera del lector vive aquí (`koreader-plugin/pruebas.lua` lo prueba con
luajit): dónde está el índice y cómo se lee, qué libro es el documento abierto, los enlaces a Calibre,
Zotero y Biblioteca Studio, el entrecomillado para la terminal y el bloque Markdown de los resaltados
sin duplicados. El complemento (`main.lua`) solo pone la interfaz y las llamadas al sistema.

El índice lo genera `lib/indice.py --aplicar` del repo; aquí solo se lee.

@module ecosistema_logica
--]]--

local M = {}

-- Versión del esquema del índice que este módulo entiende.
M.ESQUEMA = 1

-- ---------------------------------------------------------------------------------------------------
-- Utilidades de texto
-- ---------------------------------------------------------------------------------------------------

--- Devuelve `v` si es una cadena; si no (nil, null de JSON, número), la cadena vacía.
function M.texto(v)
    if type(v) == "string" then return v end
    return ""
end

--- Quita los espacios de los extremos.
function M.recortar(s)
    return (M.texto(s):gsub("^%s+", ""):gsub("%s+$", ""))
end

--- Une los espacios, tabuladores y saltos de línea seguidos en un solo espacio y recorta.
function M.normalizar(s)
    return M.recortar((M.texto(s):gsub("%s+", " ")))
end

--- Entrecomilla un argumento para la terminal: comillas simples, con las internas escapadas.
function M.citar_shell(s)
    return "'" .. M.texto(s):gsub("'", "'\\''") .. "'"
end

--- Une varios argumentos entrecomillados en una sola orden.
function M.orden(args)
    local partes = {}
    for i, a in ipairs(args) do partes[i] = M.citar_shell(a) end
    return table.concat(partes, " ")
end

--- El último componente de una ruta (sin barras finales).
function M.nombre_base(ruta)
    local r = M.texto(ruta):gsub("/+$", "")
    return r:match("([^/]+)$") or r
end

--- La carpeta que contiene un archivo (sin barra final).
function M.carpeta_de(ruta)
    return M.texto(ruta):match("^(.*)/[^/]*$") or ""
end

-- ---------------------------------------------------------------------------------------------------
-- El índice
-- ---------------------------------------------------------------------------------------------------

--- Ruta del índice: `$XDG_STATE_HOME/biblioteca/indice.json` o, sin esa variable,
-- `$HOME/.local/state/biblioteca/indice.json`. `getenv` se inyecta para probarlo (por defecto, os.getenv).
function M.ruta_indice(getenv)
    getenv = getenv or os.getenv
    local estado = getenv("XDG_STATE_HOME")
    if not estado or estado == "" then
        local inicio = getenv("HOME") or ""
        estado = inicio .. "/.local/state"
    end
    return (estado:gsub("/+$", "")) .. "/biblioteca/indice.json"
end

-- Decodificador JSON mínimo en Lua puro (objetos, listas, cadenas con \uXXXX y pares sustitutos,
-- números, true, false; null se vuelve nil). Basta para el índice; en KOReader se prefiere rapidjson.

local function utf8_de(cp)
    if cp < 0x80 then
        return string.char(cp)
    elseif cp < 0x800 then
        return string.char(0xC0 + math.floor(cp / 0x40), 0x80 + cp % 0x40)
    elseif cp < 0x10000 then
        return string.char(0xE0 + math.floor(cp / 0x1000), 0x80 + math.floor(cp / 0x40) % 0x40,
                           0x80 + cp % 0x40)
    end
    return string.char(0xF0 + math.floor(cp / 0x40000), 0x80 + math.floor(cp / 0x1000) % 0x40,
                       0x80 + math.floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
end

local ESCAPES = { ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" }

local function error_json(s, pos, que)
    error(string.format("JSON inválido en la posición %d: %s", pos, que), 0)
end

local leer_valor

local function saltar(s, pos)
    return (s:find("[^ \t\r\n]", pos)) or (#s + 1)
end

local function leer_cadena(s, pos)
    -- s:sub(pos, pos) == '"'
    local partes, i = {}, pos + 1
    while true do
        local j = s:find('["\\]', i)
        if not j then error_json(s, pos, "cadena sin cerrar") end
        partes[#partes + 1] = s:sub(i, j - 1)
        if s:sub(j, j) == '"' then
            return table.concat(partes), j + 1
        end
        local c = s:sub(j + 1, j + 1)
        if c == "u" then
            local hex = s:sub(j + 2, j + 5)
            if not hex:match("^%x%x%x%x$") then error_json(s, j, "escape \\u incompleto") end
            local cp = tonumber(hex, 16)
            local siguiente = j + 6
            if cp >= 0xD800 and cp <= 0xDBFF and s:sub(siguiente, siguiente + 1) == "\\u" then
                local bajo = tonumber(s:sub(siguiente + 2, siguiente + 5), 16)
                if bajo and bajo >= 0xDC00 and bajo <= 0xDFFF then
                    cp = 0x10000 + (cp - 0xD800) * 0x400 + (bajo - 0xDC00)
                    siguiente = siguiente + 6
                end
            end
            partes[#partes + 1] = utf8_de(cp)
            i = siguiente
        elseif ESCAPES[c] then
            partes[#partes + 1] = ESCAPES[c]
            i = j + 2
        else
            error_json(s, j, "escape desconocido")
        end
    end
end

local function leer_objeto(s, pos)
    local obj = {}
    pos = saltar(s, pos + 1)
    if s:sub(pos, pos) == "}" then return obj, pos + 1 end
    while true do
        if s:sub(pos, pos) ~= '"' then error_json(s, pos, "se esperaba una clave") end
        local clave
        clave, pos = leer_cadena(s, pos)
        pos = saltar(s, pos)
        if s:sub(pos, pos) ~= ":" then error_json(s, pos, "se esperaba «:»") end
        local valor
        valor, pos = leer_valor(s, saltar(s, pos + 1))
        obj[clave] = valor
        pos = saltar(s, pos)
        local c = s:sub(pos, pos)
        if c == "}" then return obj, pos + 1 end
        if c ~= "," then error_json(s, pos, "se esperaba «,» o «}»") end
        pos = saltar(s, pos + 1)
    end
end

local function leer_lista(s, pos)
    local lista, n = {}, 0
    pos = saltar(s, pos + 1)
    if s:sub(pos, pos) == "]" then return lista, pos + 1 end
    while true do
        local valor
        valor, pos = leer_valor(s, pos)
        n = n + 1
        lista[n] = valor
        pos = saltar(s, pos)
        local c = s:sub(pos, pos)
        if c == "]" then return lista, pos + 1 end
        if c ~= "," then error_json(s, pos, "se esperaba «,» o «]»") end
        pos = saltar(s, pos + 1)
    end
end

leer_valor = function(s, pos)
    pos = saltar(s, pos)
    local c = s:sub(pos, pos)
    if c == "{" then return leer_objeto(s, pos)
    elseif c == "[" then return leer_lista(s, pos)
    elseif c == '"' then return leer_cadena(s, pos)
    elseif s:sub(pos, pos + 3) == "true" then return true, pos + 4
    elseif s:sub(pos, pos + 4) == "false" then return false, pos + 5
    elseif s:sub(pos, pos + 3) == "null" then return nil, pos + 4
    end
    local num = s:match("^-?%d+%.?%d*[eE]?[%+%-]?%d*", pos)
    if num and num ~= "" and tonumber(num) then return tonumber(num), pos + #num end
    error_json(s, pos, "valor inesperado")
end

--- Decodifica un texto JSON. Devuelve el valor, o nil y el mensaje de error.
function M.decodificar_json(texto)
    local ok, valor, pos = pcall(leer_valor, texto, 1)
    if not ok then return nil, valor end
    if saltar(texto, pos) <= #texto then return nil, "JSON inválido: sobra texto al final" end
    return valor
end

--- Lee el índice (solo lectura). `decodificar` es opcional (por defecto, el decodificador de aquí).
-- Devuelve la tabla, o nil y un mensaje claro para mostrar.
function M.leer_indice(ruta, decodificar)
    local f = io.open(ruta, "rb")
    if not f then
        return nil, "No encuentro el índice del ecosistema en:\n" .. ruta ..
            "\n\nGenérelo con «lib/indice.py --aplicar» en scripts-biblioteca."
    end
    local contenido = f:read("*a")
    f:close()
    local ok, indice, err = pcall(decodificar or M.decodificar_json, contenido)
    if not ok then indice, err = nil, indice end
    if type(indice) ~= "table" then
        return nil, "El índice del ecosistema no se pudo leer (" .. tostring(err) .. ").\n" ..
            "Vuelva a generarlo con «lib/indice.py --aplicar»."
    end
    if indice.esquema ~= M.ESQUEMA then
        return nil, "El índice tiene el esquema " .. tostring(indice.esquema) ..
            " y este complemento entiende el " .. M.ESQUEMA .. ": actualice uno de los dos."
    end
    if type(indice.libros) ~= "table" then
        return nil, "El índice no trae la lista de libros: vuelva a generarlo con «lib/indice.py --aplicar»."
    end
    return indice
end

-- ---------------------------------------------------------------------------------------------------
-- El libro abierto
-- ---------------------------------------------------------------------------------------------------

--- El calibre_id de una ruta `<biblioteca>/<Autor>/<Título> (<id>)/<archivo>`, como cadena, o nil.
function M.calibre_id(ruta)
    return M.texto(ruta):match("%((%d+)%)/[^/]*$")
end

--- Identifica el documento abierto en el índice.
-- Devuelve id, libro; o nil, nil y el mensaje para mostrar.
function M.identificar(ruta, indice)
    local id = M.calibre_id(ruta)
    if not id then
        return nil, nil, "Este documento no está en la biblioteca Calibre: su carpeta no termina en " ..
            "«(<calibre_id>)».\n\n" .. M.texto(ruta)
    end
    local libro = indice.libros[id]
    if type(libro) ~= "table" then
        return nil, nil, "El libro " .. id .. " no figura en el índice (generado " ..
            M.texto(indice.generado) .. ").\nVuelva a generarlo con «lib/indice.py --aplicar»."
    end
    -- La carpeta debe ser la del libro (o estar dentro de la biblioteca): un «(48)» cualquiera no basta.
    local carpeta = M.carpeta_de(ruta)
    local propia = M.texto(libro.carpeta)
    local biblioteca = M.texto(indice.biblioteca):gsub("/+$", "")
    local en_su_carpeta = propia ~= "" and (carpeta == propia or carpeta:sub(-(#propia + 1)) == "/" .. propia)
    local en_biblioteca = biblioteca ~= "" and ruta:sub(1, #biblioteca + 1) == biblioteca .. "/"
    if not en_su_carpeta and not en_biblioteca then
        return nil, nil, "La carpeta de este documento termina en «(" .. id .. ")», pero no es la del libro " ..
            id .. " de la biblioteca Calibre («" .. propia .. "»)."
    end
    return id, libro
end

--- Cuántas fichas citan el libro.
function M.cuantas_fichas(libro)
    if type(libro.fichas) ~= "table" then return 0 end
    local n = 0
    for _ in pairs(libro.fichas) do n = n + 1 end
    return n
end

--- Texto de «Qué es este libro». `nota_existe` dice si la nota de lectura ya está en el disco.
function M.resumen(id, libro, nota_existe)
    local lineas = {}
    local function agregar(s) lineas[#lineas + 1] = s end
    agregar("Libro " .. id .. " de la biblioteca Calibre")
    agregar("")
    agregar("Título: " .. (M.texto(libro.titulo) ~= "" and libro.titulo or "(sin título)"))
    if type(libro.autores) == "table" and #libro.autores > 0 then
        local autores = {}
        for i, a in ipairs(libro.autores) do autores[i] = M.texto(a) end
        agregar("Autores: " .. table.concat(autores, "; "))
    end
    agregar("Clave de Zotero: " .. (M.texto(libro.zotero_key) ~= "" and libro.zotero_key or "sin ítem en Zotero"))
    agregar("Clave para citar: " .. (M.texto(libro.clave) ~= "" and libro.clave or "sin clave todavía"))
    local n = M.cuantas_fichas(libro)
    if n == 1 then
        agregar("Lo cita 1 ficha.")
    else
        agregar("Lo citan " .. n .. " fichas.")
    end
    agregar("Apuntes en Calibre: " .. (M.texto(libro.apuntes) ~= "" and "enlazados" or "sin enlazar"))
    if M.texto(libro.nota) ~= "" then
        agregar("Nota de lectura: " .. M.nombre_base(libro.nota) .. (nota_existe and "" or " (aún no existe)"))
    end
    return table.concat(lineas, "\n")
end

-- ---------------------------------------------------------------------------------------------------
-- Enlaces
-- ---------------------------------------------------------------------------------------------------

--- Hexadecimal en minúsculas de los bytes de una cadena (UTF-8 tal cual).
function M.hex(s)
    return (M.texto(s):gsub(".", function(c) return string.format("%02x", c:byte()) end))
end

--- El identificador de biblioteca que usa Calibre: el nombre de la carpeta con los espacios como «_»
-- (`calibre.srv.library_broker.library_id_from_path`).
function M.id_biblioteca(biblioteca)
    return (M.nombre_base(biblioteca):gsub(" ", "_"))
end

function M.url_calibre(biblioteca, id)
    return "calibre://show-book/_hex_-" .. M.hex(M.id_biblioteca(biblioteca)) .. "/" .. id
end

function M.url_zotero(zotero_key)
    return "zotero://select/library/items/" .. zotero_key
end

function M.url_studio(id)
    return "biblioteca-studio://libro/" .. id
end

-- ---------------------------------------------------------------------------------------------------
-- Resaltados → apuntes
-- ---------------------------------------------------------------------------------------------------

--- Los resaltados de las anotaciones de KOReader (`self.ui.annotation.annotations`), en su orden.
-- Como `exporter.koplugin`, un resaltado es la anotación con `drawer`; los marcadores de página no
-- lo tienen. Los resaltados sin texto (recortes de imagen de un PDF) se dejan fuera.
-- Devuelve una lista de { texto, pagina, nota }.
function M.resaltados(anotaciones)
    local lista = {}
    for _, a in ipairs(anotaciones or {}) do
        if type(a) == "table" and a.drawer and M.normalizar(a.text) ~= "" then
            local pagina = a.pageref or a.pageno
            if type(pagina) ~= "string" and type(pagina) ~= "number" then pagina = nil end
            lista[#lista + 1] = {
                texto = M.recortar(a.text),
                pagina = pagina and tostring(pagina) or nil,
                nota = M.recortar(a.note),
            }
        end
    end
    return lista
end

--- El contenido de un archivo de apuntes normalizado para buscar: sin los «>» de las citas y con los
-- espacios unidos, de modo que un resaltado ya pasado se encuentra aunque ocupe varias líneas.
function M.normalizar_apuntes(contenido)
    local lineas = {}
    for linea in (M.texto(contenido) .. "\n"):gmatch("([^\n]*)\n") do
        lineas[#lineas + 1] = (linea:gsub("^%s*>+%s?", ""))
    end
    return M.normalizar(table.concat(lineas, " "))
end

--- Arma el bloque Markdown fechado con los resaltados que aún no están en `contenido` (el archivo
-- de apuntes actual, o "" si no existe). Devuelve el bloque (o nil si no hay nada nuevo), cuántos
-- son nuevos y cuántos ya estaban.
function M.bloque(resaltados, contenido, fecha)
    local existente = M.normalizar_apuntes(contenido)
    local vistos = {}
    local partes, nuevos, repetidos = {}, 0, 0
    for _, r in ipairs(resaltados) do
        local clave = M.normalizar(r.texto)
        if vistos[clave] or existente:find(clave, 1, true) then
            repetidos = repetidos + 1
        else
            vistos[clave] = true
            nuevos = nuevos + 1
            local cita = {}
            for linea in (r.texto .. "\n"):gmatch("([^\n]*)\n") do
                cita[#cita + 1] = M.recortar(linea) == "" and ">" or ("> " .. M.recortar(linea))
            end
            cita[#cita + 1] = "> — p. " .. (r.pagina or "?")
            local trozo = table.concat(cita, "\n")
            if M.texto(r.nota) ~= "" then
                trozo = trozo .. "\n\n**Nota:** " .. r.nota
            end
            partes[#partes + 1] = trozo
        end
    end
    if nuevos == 0 then return nil, 0, repetidos end
    local bloque = "## Resaltados de KOReader · " .. fecha .. "\n\n" .. table.concat(partes, "\n\n") .. "\n"
    return bloque, nuevos, repetidos
end

--- El encabezado de una nota de lectura nueva (el tipo «lectura» del vault).
function M.encabezado(id, libro)
    return table.concat({
        "---",
        "tipo: lectura",
        "calibre_id: " .. id,
        "zotero_key: " .. M.texto(libro.zotero_key),
        "clave_bibtex: " .. M.texto(libro.clave),
        "---",
        "# " .. (M.texto(libro.titulo) ~= "" and libro.titulo or ("Libro " .. id)),
        "",
    }, "\n")
end

--- Lo que se añade al final del archivo: el bloque, precedido del encabezado si el archivo no
-- existe y de los saltos de línea necesarios para dejar una línea en blanco antes del «##».
function M.texto_a_anadir(contenido, existe, bloque, id, libro)
    if not existe then
        return M.encabezado(id, libro) .. "\n" .. bloque
    end
    contenido = M.texto(contenido)
    if contenido == "" then return bloque end
    if contenido:sub(-2) == "\n\n" then return bloque end
    if contenido:sub(-1) == "\n" then return "\n" .. bloque end
    return "\n\n" .. bloque
end

return M
