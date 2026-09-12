#!/usr/bin/env python3
"""Resumen de una página de las bases de un concurso.
Lee los documentos de una carpeta (PDF, DOCX, TXT; descomprime ZIP), pide a la
API de Anthropic un resumen estructurado y lo maqueta en un A4 apaisado con
texto vivo (Helvetica, blanco y negro, marcas de registro).
Uso: python3 resumen.py <carpeta> [ficha.json]
Clave: variable ANTHROPIC_API_KEY o archivo ~/.concursos-api-key"""
import os, re, sys, json, zipfile, io, requests

MODELO = os.getenv("MODELO_RESUMEN", "claude-sonnet-5")
MAX_CHARS = 140_000
PRIORIDAD = re.compile(r"bases|pliego|reglement|règlement|programme|programma|wedstrijd|leidraad|ausschreib|auslob|wettbewerb|"
                       r"program|regolamento|regulamento|caderno|selectie|brief|competition|concours|konkurs|kilpailuohjelma|tävlingsprogram", re.I)


def clave():
    k = os.getenv("ANTHROPIC_API_KEY", "")
    if not k:
        try:
            k = open(os.path.expanduser("~/.concursos-api-key")).read().strip()
        except Exception:
            pass
    return k


def texto_pdf(ruta):
    from pypdf import PdfReader
    try:
        r = PdfReader(ruta)
        return "\n".join((p.extract_text() or "") for p in r.pages[:120])
    except Exception as e:
        return ""


def texto_docx(ruta):
    try:
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    except Exception:
        return ""


def descomprimir(carpeta):
    for f in list(os.listdir(carpeta)):
        if f.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(os.path.join(carpeta, f)) as z:
                    z.extractall(os.path.join(carpeta, f[:-4]))
            except Exception:
                pass


def recoger_texto(carpeta):
    descomprimir(carpeta)
    piezas = []
    for raiz, _, files in os.walk(carpeta):
        for f in files:
            ruta = os.path.join(raiz, f)
            low = f.lower()
            if low.endswith(".pdf"):
                t = texto_pdf(ruta)
            elif low.endswith(".docx"):
                t = texto_docx(ruta)
            elif low.endswith((".txt", ".md")) and not f.startswith("_"):
                t = open(ruta, encoding="utf-8", errors="ignore").read()
            else:
                continue
            t = re.sub(r"[ \t]+", " ", t)
            if len(t.strip()) > 200:
                piezas.append((0 if PRIORIDAD.search(f) else 1, f, t))
    piezas.sort(key=lambda x: (x[0], -len(x[2])))
    out, total = [], 0
    for _, f, t in piezas:
        cupo = MAX_CHARS - total
        if cupo <= 0:
            break
        out.append(f"=== DOCUMENTO: {f} ===\n{t[:cupo]}")
        total += min(len(t), cupo)
    return "\n\n".join(out), [f for _, f, _ in piezas]


PROMPT = """Eres un arquitecto que prepara la ficha interna de un concurso de arquitectura para decidir si el estudio se presenta.
A partir de la documentación adjunta (bases, pliegos, programa), responde SOLO con un JSON válido, en español, con estas claves
(cadena vacía o lista vacía si el dato no aparece; nada de suposiciones):
{
 "titulo": "nombre corto del concurso",
 "convocante": "",
 "lugar": "",
 "tipo": "concurso abierto / restringido con precalificación / ideas / licitación… y si es anónimo o en fases",
 "objeto": "qué se pide, en 2-4 frases claras",
 "programa": "programa funcional resumido con superficies si las hay",
 "superficie": "superficie construida o de ámbito, con unidades",
 "presupuesto": "presupuesto de obra (PEM o equivalente) con moneda",
 "honorarios": "honorarios previstos o forma de cálculo",
 "retribucion": "premios, indemnizaciones o retribución por participar",
 "calendario": ["hito: fecha", "..."],
 "entregables": ["qué hay que entregar y en qué formato (paneles, maqueta, memoria…)"],
 "participantes": "quién puede presentarse: titulación, colegiación, equipo, solvencia, restricciones geográficas",
 "criterios": ["criterios de valoración con pesos si los hay"],
 "idioma": "idioma de la documentación y de la entrega",
 "observaciones": "riesgos o particularidades relevantes (coste de la maqueta, exclusiones, cesión de derechos, etc.)"
}
Sé concreto y breve: todo el resumen tiene que caber en una página A4."""


def resumir(texto):
    k = clave()
    if not k:
        raise SystemExit("Falta la clave: ANTHROPIC_API_KEY o ~/.concursos-api-key")
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers={"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": MODELO, "max_tokens": 2500,
                            "messages": [{"role": "user", "content": PROMPT + "\n\nDOCUMENTACIÓN:\n" + texto}]},
                      timeout=300)
    r.raise_for_status()
    out = "".join(b.get("text", "") for b in r.json().get("content", []))
    out = re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.M).strip()
    return json.loads(out)


# ---------------- maquetación ----------------
def maquetar(d, ruta_pdf, ficha=None):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Frame
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT

    W, H = landscape(A4)
    M = 14 * mm                      # margen exterior
    aspa_x, aspa_y = W - M, H - M    # el aspa: elemento más exterior, arriba a la derecha
    cx0, cy0, cx1, cy1 = M + 4 * mm, M + 4 * mm, W - M - 4 * mm, H - M - 7 * mm   # caja de contenido
    FINO = 0.05 * mm
    PUNTO = 0.07 * mm

    def marcas(c):
        c.setLineWidth(FINO)
        c.setFont("Helvetica", 11)
        c.drawRightString(aspa_x, aspa_y - 3, "×")
        L = 4 * mm
        c.line(cx0, cy1, cx0 + L, cy1); c.line(cx0, cy1, cx0, cy1 - L)          # escuadra arriba-izquierda
        c.line(cx1, cy0, cx1 - L, cy0); c.line(cx1, cy0, cx1, cy0 + L)          # escuadra abajo-derecha

    def punteado(c, x0, x1, y):
        c.saveState(); c.setLineWidth(PUNTO); c.setLineCap(1); c.setDash([0.01, 2.2]); c.line(x0, y, x1, y); c.restoreState()

    def esc(t):
        t = str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return t.replace("m²", "m<super>2</super>").replace("m³", "m<super>3</super>").replace("²", "<super>2</super>")

    def bloque(label, valor, st, stb):
        if isinstance(valor, list):
            valor = "<br/>".join(esc(v) for v in valor if v)
        else:
            valor = esc(valor)
        if not valor:
            return []
        return [Paragraph(label.upper(), stb), Paragraph(valor, st)]

    for size in (8.6, 8.2, 7.8, 7.4, 7.0, 6.6, 6.2):
        lead = size * 1.32
        st = ParagraphStyle("t", fontName="Helvetica", fontSize=size, leading=lead, alignment=TA_LEFT, spaceAfter=lead * 0.8)
        stb = ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=size, leading=lead, spaceAfter=lead * 0.15)
        sth = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=size + 3, leading=(size + 3) * 1.25)
        sts = ParagraphStyle("s", fontName="Helvetica", fontSize=size, leading=lead)

        c = canvas.Canvas(ruta_pdf, pagesize=(W, H))
        c.setTitle(d.get("titulo", "Resumen de concurso")); c.setAuthor("arrova")
        marcas(c)
        # cabecera
        y = cy1 - 2 * mm
        cab = [Paragraph(esc(d.get("titulo", "")), sth),
               Paragraph(" · ".join(esc(x) for x in [d.get("convocante"), d.get("lugar"), d.get("tipo")] if x), sts)]
        fr = Frame(cx0, y - 16 * mm, cx1 - cx0, 16 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
        fr.addFromList(cab, c)
        y_top = y - 17 * mm
        punteado(c, cx0, cx1, y_top + 1.5 * mm)
        # tres columnas: la más larga primero
        gap = 8 * mm
        colw = (cx1 - cx0 - 2 * gap) / 3
        col1 = bloque("Objeto", d.get("objeto"), st, stb) + bloque("Programa", d.get("programa"), st, stb) + bloque("Observaciones", d.get("observaciones"), st, stb)
        col2 = bloque("Superficie", d.get("superficie"), st, stb) + bloque("Presupuesto de obra", d.get("presupuesto"), st, stb) + \
               bloque("Honorarios", d.get("honorarios"), st, stb) + bloque("Retribución", d.get("retribucion"), st, stb) + \
               bloque("Participantes", d.get("participantes"), st, stb) + bloque("Idioma", d.get("idioma"), st, stb)
        col3 = bloque("Calendario", d.get("calendario"), st, stb) + bloque("Entregables", d.get("entregables"), st, stb) + bloque("Criterios de valoración", d.get("criterios"), st, stb)
        cols = sorted([col1, col2, col3], key=lambda L: -sum(len(p.text) for p in L))
        sobrante = 0
        for i, L in enumerate(cols):
            x = cx0 + i * (colw + gap)
            f = Frame(x, cy0 + 6 * mm, colw, y_top - cy0 - 6 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
            resto = list(L)
            f.addFromList(resto, c)
            sobrante += len(resto)
            if i < 2:
                c.saveState(); c.setLineWidth(PUNTO); c.setLineCap(1); c.setDash([0.01, 2.2])
                c.line(x + colw + gap / 2, cy0 + 6 * mm, x + colw + gap / 2, y_top); c.restoreState()
        # pie
        pie = " · ".join(x for x in [ficha.get("num", "") if ficha else "", ficha.get("source", "") if ficha else "", "resumen automático: verificar siempre contra las bases"] if x)
        c.setFont("Helvetica", 6.5); c.drawString(cx0, cy0 + 1.5 * mm, pie)
        c.save()
        if sobrante == 0:
            return True
    return False


def main():
    if len(sys.argv) < 2:
        print("uso: resumen.py <carpeta> [ficha.json]")
        return
    carpeta = sys.argv[1]
    ficha = {}
    fj = sys.argv[2] if len(sys.argv) > 2 else os.path.join(carpeta, "_ficha.txt")
    try:
        ficha = json.load(open(fj, encoding="utf-8"))
    except Exception:
        pass
    texto, archivos = recoger_texto(carpeta)
    if len(texto) < 500:
        print("sin texto legible en la documentación (¿PDF escaneado?)")
        return
    cabecera = "FICHA DEL BUSCADOR: " + json.dumps({k: ficha.get(k) for k in ("title", "buyer", "place", "deadline", "value", "cur", "proc", "desc") if ficha.get(k)}, ensure_ascii=False)
    d = resumir(cabecera + "\n\n" + texto)
    json.dump(d, open(os.path.join(carpeta, "_resumen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = maquetar(d, os.path.join(carpeta, "resumen.pdf"), ficha)
    print("resumen.pdf" + ("" if ok else " (no cupo entero en una página; se ha reducido al mínimo)"), "| documentos leídos:", ", ".join(archivos[:8]))


if __name__ == "__main__":
    main()
