# Concursos de arquitectura · Europa · aviso semanal

Cada lunes a las 08:00 consulta el TED (boletín oficial UE + Suiza vía simap.ch),
filtra los *concursos de proyectos* (design contest) con CPV 71 (arquitectura /
ingeniería) de los países elegidos y te manda un mail con título, convocante,
lugar, plazo y enlace. Reenviable tal cual.

## Puesta en marcha (10 min, gratis)

1. Crea un repositorio en GitHub (privado vale) y sube estos tres archivos
   respetando la carpeta `.github/workflows/`.
2. En Gmail: cuenta → Seguridad → Verificación en dos pasos → **Contraseñas de
   aplicación** → crea una para "concursos". Copia los 16 caracteres.
3. En el repo: Settings → Secrets and variables → Actions → New repository secret:
   - `MAIL_FROM`  tu gmail
   - `SMTP_USER`  tu gmail
   - `SMTP_PASS`  la contraseña de aplicación
   - `MAIL_TO`    destinatarios separados por coma (p. ej. info@arrova.eu,koldo@...)
4. Actions → "concursos semanales" → **Run workflow** para probar. Llega el mail
   y además queda el HTML como artefacto descargable.

## Ajustes

- Países: lista `COUNTRIES` en `concursos.py` (ISO-3). Quita ESP si no lo quieres.
- Ventana: `DAYS_BACK` (7 por defecto). Para la primera vez pon 30 y verás fondo.
- Hora: la línea `cron` del workflow.
- Filtro de estudiantes: lista `EXCLUDE`.

## Límites conocidos

- El TED solo recoge concursos por encima del umbral europeo o publicados
  voluntariamente. Lo pequeño (Bouwmeester Open Oproep, concursos municipales
  alemanes en competitionline, Konkurado suizo) queda fuera; está previsto como
  fuente secundaria en una v2.
- Si el TED cambia nombres de campo, el script reintenta con un juego mínimo de
  campos. Si un lunes no llega mail, mira el log en Actions.

## Fuentes nacionales (v2)

Carpeta `fuentes/`: un módulo por portal, cada uno con `fetch()`. Para probar
uno suelto: `python -m fuentes.bouwmeester`.

- `bouwmeester.py` — Vlaams Bouwmeester: Open Oproep (OO) y Oproep aan
  geïnteresseerden (OAG). Las OAG no salen en el TED. Excluye Meesterproef
  (solo recién titulados).

## Base acumulada y buscador web

Cada ejecución añade lo nuevo a `docs/concursos.json` (no se borra nada; lo ya
visto se refresca) y el workflow lo commitea. `docs/index.html` es un buscador
estático que lee esa base: filtros por país, plazo, tipo, presupuesto estimado,
fuente y fecha de aparición; casilla para marcar lo que interesa (se guarda en
el navegador) y botón para copiar lo marcado y pegarlo en un mail.

Se publica con GitHub Pages desde la carpeta `docs/` (el repo tiene que ser
público para Pages gratuito; no contiene secretos, están aparte). La dirección
queda en https://USUARIO.github.io/concursos-europa/ y el mail semanal la
enlaza.

Para que Actions pueda hacer push: Settings → Actions → General → Workflow
permissions → "Read and write permissions".

## Boletines por correo (`fuentes/boletines.py`)

Lee el buzón de Google indicado en los secretos `IMAP_USER` / `IMAP_PASS`
(contraseña de aplicación) y analiza los boletines de los remitentes dados de
alta en `PARSERS`. Hoy: newsfeed de architekturwettbewerb.at. Para añadir otro
boletín: guardar un `.eml` de muestra, escribir su analizador y registrarlo.
Prueba local con un mensaje: `python3 -m fuentes.boletines mensaje.eml`.

## Konkurado (`fuentes/konkurado.py`)

Lee la lista pública de procedimientos actuales de konkurado.ch (Suiza), se
queda con concursos de proyectos, Planerwahlverfahren, Studienaufträge y
Gesamtleistungswettbewerbe (descarta las «Offerte»), y abre cada ficha para
sacar plazo, descripción, anonimato y restricción regional (WTO/GPA = abierto a
extranjeros). Prueba: `python3 -m fuentes.konkurado`.

## BMA Bruselas (`fuentes/bma.py`)

Appels à candidatures del bouwmeester maître architecte de Bruselas
(bma.brussels/news). De cada ficha saca maître d'ouvrage, programa,
presupuesto, honorarios, retribución por participar y fecha límite. Prueba:
`python3 -m fuentes.bma`.

## Polonia (`fuentes/polonia.py`)

Agregador architektura.info (konkursy architektoniczne: fecha de registro,
entrega, ciudad; descarta premios e internacionales) y lista «Bieżące» del
SARP Oddział Warszawski (plazos, premios, m²). Prueba:
`python3 -m fuentes.polonia`.

## Nórdicos (`fuentes/nordicos.py`)

Suecia: tävlingar aprobadas por Sveriges Arkitekter (solo estado «Ej
påbörjad» / «Påbörjad», sin estudiantes ni markanvisningar), con plazo y tipo
desde la ficha. Finlandia: kilpailukalenteri de SAFA (yleiset = abiertos,
kutsukilpailut = invitación; estados próximo / en curso). Dinamarca y Noruega
solo por TED y boletines. Prueba: `python3 -m fuentes.nordicos`.

## Italia (`fuentes/italia.py`)

Piattaforma concorsi del CNAPPC (concorsiawn.it): concorsi di progettazione a
due fasi y concorsi di idee activos, con ente, ciudad y plazo de inscripción
de primera fase. Descarta los premios. Prueba: `python3 -m fuentes.italia`.

## Portugal (`fuentes/portugal.py`)

Tres piezas: plataforma da encomenda de la Secção Sul (encomenda.oasrs.org,
concursos en curso con promotor, plazo, premios y valor de obra); lista de la
Secção Norte (oasrn.org, solo «Concurso de Conceção» e ideias, descartando
conceção-construção y licitaciones); y vigilante de la página nacional de la
Ordem (en construcción), que avisa en el mail el día que se active. Prueba: `python3 -m fuentes.portugal`.

## Francia · BOAMP (`fuentes/francia.py`)

API abierta del BOAMP (Opendatasoft, licencia Etalab). Filtra los avisos de la
semana y conserva concours de maîtrise d'œuvre / d'architecture y marchés de
maîtrise d'œuvre con esquisse o jurado; descarta AMO, OPC, diagnósticos,
redes, etc. Complementa al TED con lo que está por debajo del umbral europeo.
Prueba: `python3 -m fuentes.francia`.
