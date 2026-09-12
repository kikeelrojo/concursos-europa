"""Lee boletines por correo (IMAP de Google) y saca concursos.
Un analizador por remitente; añadir nuevos en PARSERS."""
import os, re, imaplib, email, email.policy, datetime as dt
from bs4 import BeautifulSoup

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
DAYS_BACK = int(os.getenv("DAYS_BACK", "7")) + 1


def _abierto(texto):
    t = texto.lower()
    if re.search(r"geladen|nicht ?offen|beschränkt|begrenzt|einladung", t):
        return "seleccion"
    if "offen" in t:
        return "abierto"
    return ""


def parse_architekturwettbewerb(msg, html):
    """Newsfeed de www.architekturwettbewerb.at (Kammer, Austria)."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    h2 = soup.find(lambda t: t.name == "h2" and "Ausschreibung" in t.get_text())
    if not h2:
        return out
    for p in h2.find_all_next("p"):
        a = p.find("a", href=True)
        if not a or "/competition/" not in a["href"]:
            continue
        lines = [l.strip() for l in p.get_text("\n").split("\n") if l.strip()]
        title = a.get_text(strip=True)
        rest = [l for l in lines if l != title]
        tipo = rest[0] if rest else ""
        region = rest[1] if len(rest) > 1 else ""
        m = re.search(r"/(\d+)/?$", a["href"])
        num = "AW-" + (m.group(1) if m else re.sub(r"\W", "", title)[:30])
        out.append({"num": num, "title": f"{title} ({tipo})" if tipo else title,
                    "buyer": "", "country": "AUT", "pub": _fecha(msg), "deadline": "",
                    "place": region, "url": a["href"], "source": "architekturwettbewerb.at",
                    "proc": _abierto(tipo), "desc": " · ".join(rest[2:])})
    return out


import html as htmlmod

CAMPO = re.compile(r"^(N[ºo°]\s*Registro|Localizaci[oó]n|Objeto|Organismo|Presupuesto|Licitaci[oó]n|Publicado(?: en)?|Plazo|Enlace|Observaciones)\s*:\s*(.*)$", re.I)
DMY = re.compile(r"(\d{1,2})/(\d{2})/(\d{4})(?:\D{0,12}(\d{1,2})[:.](\d{2}))?")
CONCURSO_ES = re.compile(r"concurso (p[úu]blico |restringido |abierto |internacional )?de (proyectos|ideas|anteproyectos|arquitectura|direcci[oó]n de obra)|"
                         r"concurso (de arquitectura|arquitect[oó]nico)|concurs (p[úu]blic )?de projectes|concurso de proxectos", re.I)
PAISES_INT = {"francia": "FRA", "france": "FRA", "alemania": "DEU", "germany": "DEU", "italia": "ITA", "portugal": "PRT",
              "suiza": "CHE", "switzerland": "CHE", "austria": "AUT", "bélgica": "BEL", "belgica": "BEL", "belgium": "BEL",
              "holanda": "NLD", "países bajos": "NLD", "netherlands": "NLD", "polonia": "POL", "suecia": "SWE",
              "dinamarca": "DNK", "noruega": "NOR", "finlandia": "FIN", "luxemburgo": "LUX", "reino unido": "GBR", "uk": "GBR"}


def _texto_html(html_):
    t = re.sub(r"<style.*?</style>", "", html_, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</(p|div|tr|li|h\d|td)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmlmod.unescape(t)
    return [" ".join(l.split()) for l in t.split("\n") if l.strip()]


def parse_coavn(msg, html_):
    """Oficina de Concursos del COAVN: boletín Euskadi-Navarra y boletín
    estatal/internacional (mismo remitente, distinto asunto)."""
    asunto = str(msg.get("Subject", ""))
    estatal = re.search(r"estatal|internacional", asunto, re.I) is not None
    lines = _texto_html(html_)
    # hrefs reales de las fichas, indexados por número de registro
    hrefs = {}
    for m in re.finditer(r'href="([^"]*fichaConcurso[^"]*numeroRegistro=([A-Za-z0-9]+)[^"]*)"', html_):
        hrefs[m.group(2)] = htmlmod.unescape(m.group(1))
    out, cur, seccion = [], None, ""
    def cerrar():
        if not cur or not cur.get("Objeto"):
            return
        if re.search(r"actualizad", seccion, re.I):
            return
        loc = cur.get("Localización", "")
        if estatal:
            internacional = re.search(r"internacional", seccion, re.I) is not None
            country = "ESP"
            if internacional:
                country = next((v for k, v in PAISES_INT.items() if k in loc.lower()), "INT")
            source = "COAVN internacional" if internacional else "COAVN estatal"
        else:
            country, source = "ESP", "COAVN Euskadi-Navarra"
        m = DMY.search(cur.get("Plazo", ""))
        dl = f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}" + (f" {int(m.group(4)):02d}:{m.group(5)}" if m.group(4) else "") if m else ""
        mp = DMY.search(cur.get("Publicado", ""))
        pub = f"{mp.group(3)}-{mp.group(2)}-{int(mp.group(1)):02d}" if mp else _fecha(msg)
        presu = cur.get("Presupuesto") or cur.get("Licitación") or ""
        mv = re.search(r"([\d.\s]+(?:,\d{2})?)\s*euros", presu)
        val = re.sub(r"[.\s]", "", mv.group(1)).split(",")[0] if mv else ""
        objeto = cur["Objeto"]
        reg = cur.get("Nº Registro", "")
        num = "COAVN-" + (reg or re.sub(r"\W", "", objeto)[:30])
        if reg in hrefs:
            cur["Enlace"] = hrefs[reg]
        out.append({"num": num, "title": objeto[:220], "buyer": cur.get("Organismo", ""), "country": country,
                    "pub": pub, "deadline": dl, "place": loc, "url": cur.get("Enlace", ""), "coavn_url": cur.get("Enlace", ""), "source": source,
                    "proc": "seleccion" if re.search(r"restringido|invitaci[oó]n", objeto, re.I) else "abierto" if CONCURSO_ES.search(objeto) else "",
                    "kind": "concurso" if CONCURSO_ES.search(objeto) else "licitación",
                    "value": val, "cur": "EUR" if val else "",
                    "desc": " · ".join(x for x in [f"Presupuesto: {presu}" if presu else "", f"Publicado en: {cur.get('Publicado','')}" if cur.get("Publicado") else ""] if x)})
    i = 0
    while i < len(lines):
        l = lines[i]
        i += 1
        ms = re.match(r"^(Nuevos Concursos|Concursos Actualizados|Concursos Estatales|Concursos Internacionales)\s*:?\s*(.*)$", l, re.I)
        if ms:
            cerrar(); cur = None
            seccion = ms.group(1)
            l = ms.group(2)
            if not l:
                continue
        m = CAMPO.match(l)
        if not m:
            if cur is not None and "Objeto" in cur and not any(k in cur for k in ("Organismo", "Enlace")):
                cur["Objeto"] += " " + l        # objeto de varias líneas (lotes)
            continue
        campo, valor = m.group(1), m.group(2).strip()
        if not valor and i < len(lines) and not CAMPO.match(lines[i]) \
                and not re.match(r"^(Nuevos Concursos|Concursos Actualizados|Concursos Estatales|Concursos Internacionales)", lines[i], re.I):
            valor = lines[i]                    # etiqueta y valor en líneas separadas
            i += 1
        campo = re.sub(r"^N.\s*Registro$", "Nº Registro", campo, flags=re.I)
        campo = {"localizacion": "Localización", "licitacion": "Licitación"}.get(campo.lower(), campo)
        campo = "Publicado" if campo.lower().startswith("publicado") else campo
        if campo == "Nº Registro":
            cerrar(); cur = {}
        if cur is None:
            cur = {}
        cur[campo] = valor
    cerrar()
    return out


PARSERS = {
    "noreply@architekturwettbewerb.at": parse_architekturwettbewerb,
    "decanatoconcursos@coavn.org": parse_coavn,
}


def _fecha(msg):
    try:
        return email.utils.parsedate_to_datetime(msg["Date"]).date().isoformat()
    except Exception:
        return ""


def _html(msg):
    body = msg.get_body(preferencelist=("html", "plain"))
    return body.get_content() if body else ""


def fetch():
    user, pw = os.getenv("IMAP_USER"), os.getenv("IMAP_PASS")
    if not user or not pw:
        print("boletines: IMAP_USER/IMAP_PASS no definidos, se omite")
        return []
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).strftime("%d-%b-%Y")
    out = []
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST)
        M.login(user, pw)
        M.select('"[Gmail]/All Mail"' if IMAP_HOST == "imap.gmail.com" else "INBOX", readonly=True)
        for sender, parser in PARSERS.items():
            typ, data = M.search(None, f'(SINCE {since} FROM "{sender}")')
            ids = data[0].split() if typ == "OK" else []
            for i in ids:
                typ, d = M.fetch(i, "(RFC822)")
                if typ != "OK":
                    continue
                msg = email.message_from_bytes(d[0][1], policy=email.policy.default)
                try:
                    out += parser(msg, _html(msg))
                except Exception as e:
                    print("boletines:", sender, e)
            print(f"boletines: {sender}: {len(ids)} mensajes")
        M.logout()
    except Exception as e:
        print("boletines: error IMAP", e)
    # sin duplicados dentro de la semana
    vistos, res = set(), []
    for c in out:
        if c["num"] not in vistos:
            vistos.add(c["num"]); res.append(c)
    return res


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1:   # prueba local con un .eml
        msg = email.message_from_binary_file(open(sys.argv[1], "rb"), policy=email.policy.default)
        sender = email.utils.parseaddr(msg["From"])[1]
        print(json.dumps(PARSERS[sender](msg, _html(msg)), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(fetch(), ensure_ascii=False, indent=1))
