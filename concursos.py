#!/usr/bin/env python3
"""
Buscador semanal de concursos de arquitectura en Europa (TED).
Consulta la Search API pública del TED (sin clave), filtra concursos de
proyectos (design contest) de los países elegidos y envía un mail HTML.
"""
import os, re, sys, smtplib, datetime as dt, json, urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from fuentes import FUENTES

TED_URL = "https://api.ted.europa.eu/v3/notices/search"

# Países (ISO-3). Suiza entra porque simap.ch republica en TED.
COUNTRIES = ["FRA", "BEL", "CHE", "DEU", "AUT", "NLD", "DNK", "SWE",
             "NOR", "FIN", "ITA", "PRT", "POL", "LUX", "ESP"]
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
# Palabras que suelen delatar concursos de estudiantes o ideas sin encargo
EXCLUDE = ["student", "étudiant", "studenten", "studenti", "estudiante",
           "estudantes", "studenc"]

FIELDS = ["publication-number", "notice-title", "buyer-name", "buyer-country",
          "publication-date", "notice-type", "deadline", "deadline-receipt-request",
          "deadline-receipt-tender-date-lot", "place-of-performance", "classification-cpv",
          "estimated-value-proc", "estimated-value-cur-proc", "procedure-type", "description-proc"]
# Palabras que delatan un concurso aunque el aviso no sea "cn-desg"
KEYWORDS = ["concours", "wettbewerb", "concurso", "concorso", "prijsvraag",
            "wedstrijd", "konkurs", "tävling", "konkurrence", "konkurranse",
            "kilpailu", "competition"]

def lang(v):
    """Campos multilingües llegan como {"eng":[..],"fra":[..]}; coge el 1º."""
    if isinstance(v, dict):
        for k in ("spa", "eng", "fra", "deu", "ita", "por", "nld", "pol"):
            if v.get(k):
                return v[k][0] if isinstance(v[k], list) else v[k]
        for k in v:
            x = v[k]
            return x[0] if isinstance(x, list) else x
    if isinstance(v, list):
        return v[0] if v else ""
    return v or ""


def _search(q):
    body = {"query": q + " SORT BY publication-date DESC", "fields": FIELDS,
            "limit": 100, "scope": "ALL", "paginationMode": "PAGE_NUMBER", "page": 1}
    out = []
    while True:
        r = requests.post(TED_URL, json=body, timeout=60)
        r.raise_for_status()
        page = r.json().get("notices", [])
        out += page
        if len(page) < 100 or body["page"] >= 5:
            return out
        body["page"] += 1


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).strftime("%Y%m%d")
    cc = "buyer-country IN (" + " ".join(COUNTRIES) + ")"
    # 1) concursos de proyectos propiamente dichos
    q1 = f"notice-type=cn-desg AND {cc} AND PD>={since}"
    # 2) licitaciones de servicios (CPV 71) cuyo título huele a concurso
    kw = " ".join(KEYWORDS)
    q2 = (f"notice-type IN (cn-standard pin-cfc-standard) AND classification-cpv=71* "
          f"AND notice-title IN ({kw}) AND {cc} AND PD>={since}")
    desg = _search(q1)
    for n in desg:
        n["_kind"] = "concurso"
    seen = {n.get("publication-number") for n in desg}
    try:
        extra = [n for n in _search(q2) if n.get("publication-number") not in seen]
    except requests.HTTPError as e:
        print("segunda consulta rechazada:", e, file=sys.stderr)
        extra = []
    for n in extra:
        n["_kind"] = "licitación con concurso"
    return desg + extra


ARCH = re.compile(r"arquitect|architect|architekt|architet|arkitekt|arkkitehti|"
                  r"ma[iî]trise d.{0,3}uvre|urbanis|städtebau|stedenbouw|"
                  r"landschaft|paysag|paisaj|landscape|freiraum|"
                  r"realisierungswettbewerb|planungswettbewerb|ideenwettbewerb|"
                  r"concurso de (ante)?proyectos|concorso di progettazione|"
                  r"prijsvraag|ontwerpwedstrijd|projekttävling|projektkonkurrence", re.I)


def is_arch(n, title):
    cpv = n.get("classification-cpv") or []
    if isinstance(cpv, str):
        cpv = [cpv]
    return any(str(c).startswith("71") for c in cpv) or bool(ARCH.search(title))


def clean(n):
    title = lang(n.get("notice-title"))
    if any(w in title.lower() for w in EXCLUDE) or not is_arch(n, title):
        return None
    return {
        "num": n.get("publication-number", ""),
        "title": title,
        "buyer": lang(n.get("buyer-name")),
        "country": lang(n.get("buyer-country")),
        "pub": lang(n.get("publication-date"))[:10],
        "deadline": (lang(n.get("deadline")) or lang(n.get("deadline-receipt-request"))
                     or lang(n.get("deadline-receipt-tender-date-lot")))[:16],
        "kind": n.get("_kind", ""),
        "value": lang(n.get("estimated-value-proc")),
        "cur": lang(n.get("estimated-value-cur-proc")),
        "proc": lang(n.get("procedure-type")),
        "desc": lang(n.get("description-proc"))[:1500],
        "place": lang(n.get("place-of-performance")),
        "url": f"https://ted.europa.eu/es/notice/-/detail/{n.get('publication-number','')}",
        "source": "TED",
    }


def page_url():
    repo = os.getenv("GITHUB_REPOSITORY", "")      # owner/repo en Actions
    if "/" in repo:
        o, r = repo.split("/", 1)
        return f"https://{o}.github.io/{r}/"
    return os.getenv("PAGE_URL", "")


ISO2 = {"FRA": "FR", "BEL": "BE", "CHE": "CH", "DEU": "DE", "AUT": "AT", "NLD": "NL", "DNK": "DK",
        "SWE": "SE", "NOR": "NO", "FIN": "FI", "ITA": "IT", "PRT": "PT", "POL": "PL", "LUX": "LU", "ESP": "ES", "GBR": "UK"}


def pais(c):
    return ISO2.get(c.get("country", ""), c.get("country", ""))


def rango(c):
    """Orden: España primero (y dentro, País Vasco-Navarra), luego el resto por país."""
    if c.get("country") == "ESP":
        return (0, 0 if "euskadi" in str(c.get("source", "")).lower() or "navarra" in str(c.get("source", "")).lower() else 1)
    return (1, 0)


MODELO_TRAD = os.getenv("MODELO_TRADUCCION", "claude-haiku-4-5-20251001")


def traducir(items):
    """Traduce al español los títulos (y la descripción corta) de lo que no está en español.
    Guarda title_es / desc_es; necesita ANTHROPIC_API_KEY. Sin clave, no hace nada."""
    k = os.getenv("ANTHROPIC_API_KEY", "")
    pend = [c for c in items if c.get("country") != "ESP" and not c.get("title_es") and c.get("title")]
    if not k or not pend:
        return
    for i in range(0, len(pend), 40):
        lote = pend[i:i + 40]
        entrada = [{"i": j, "t": c["title"][:300], "d": (c.get("desc") or "")[:350]} for j, c in enumerate(lote)]
        prompt = ("Traduce al español estos títulos y descripciones de concursos y licitaciones de arquitectura. "
                  "Mantén nombres propios y de lugares; sé literal y breve. Responde SOLO con un JSON: "
                  "una lista de objetos {\"i\": n, \"t\": título en español, \"d\": descripción en español}.\n\n"
                  + json.dumps(entrada, ensure_ascii=False))
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                              headers={"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": MODELO_TRAD, "max_tokens": 8000,
                                    "messages": [{"role": "user", "content": prompt}]}, timeout=180)
            r.raise_for_status()
            out = "".join(b.get("text", "") for b in r.json().get("content", []))
            a, b = out.find("["), out.rfind("]")
            for t in json.loads(out[a:b + 1], strict=False):
                c = lote[int(t["i"])]
                if t.get("t"):
                    c["title_es"] = t["t"].strip()
                if t.get("d"):
                    c["desc_es"] = t["d"].strip()
        except Exception as e:
            print("traducción:", e, file=sys.stderr)


def titulo(c):
    return c.get("title_es") or c.get("title", "")


def es_open_oproep(c):
    t = (c.get("title", "") + " " + c.get("buyer", "")).lower()
    return "open oproep" in t or str(c.get("num", "")).startswith("OO")


def html(items):
    today = dt.date.today().strftime("%d.%m.%Y")
    oo = [c for c in items if es_open_oproep(c)]
    aviso = ""
    if oo:
        lineas = "".join(f"<br><a href='{c['url']}' style='color:#000'>{titulo(c)}</a>"
                         f"{(' · candidaturas hasta ' + c['deadline']) if c['deadline'] else ''}" for c in oo)
        aviso = (f"<p style='border:1px solid #000;padding:10px;margin:0 0 18px'><b>OPEN OPROEP · Vlaams Bouwmeester</b>"
                 f"<br>Convocatoria que solo sale una o dos veces al año.{lineas}</p>")
    css = ("font-family:Helvetica,Arial,sans-serif;color:#000;"
           "font-size:13px;line-height:1.4")
    rows = []
    for c in sorted(items, key=lambda x: (rango(x), x["country"], x["deadline"] or "z")):
        v = f" · {c['value']} {c['cur']}" if c.get("value") else ""
        rows.append(
            f"<tr><td style='padding:6px 8px 6px 0;vertical-align:top'><b>{pais(c)}</b></td>"
            f"<td style='padding:6px 8px;vertical-align:top'><a href='{c['url']}' "
            f"style='color:#000'>{titulo(c)}</a><br>{c['buyer']}"
            f"{(' · ' + c['place']) if c['place'] else ''}{v}"
            f"{(' · ' + c['source']) if c.get('source') and c['source'] != 'TED' else ''}"
            f"{''.join(' · también en <a href=' + chr(39) + a['url'] + chr(39) + ' style=' + chr(39) + 'color:#000' + chr(39) + '>' + (a['source'] or 'otra fuente') + '</a>' for a in c.get('alt', []))}</td>"
            f"<td style='padding:6px 0 6px 8px;vertical-align:top;white-space:nowrap'>"
            f"{'límite ' + c['deadline'] if c['deadline'] else ('pub. ' + c['pub'] if c['pub'] else 'en cartera')}</td></tr>")
    table = ("<table style='border-collapse:collapse'>" + "".join(rows) + "</table>"
             if rows else "<p>Sin concursos nuevos esta semana.</p>")
    link = page_url()
    return (f"<div style='{css}'>{aviso}<p><b>CONCURSOS DE ARQUITECTURA · EUROPA</b><br>"
            f"semana del {today} · {len(items)} nuevos</p>"
            + (f"<p><a href='{link}' style='color:#000'><b>Buscador con todo lo acumulado</b></a></p>" if link else "")
            + table + "<p style='margin-top:24px'>×</p></div>")


def send(subject, body_html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.environ["MAIL_FROM"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    with smtplib.SMTP_SSL(os.getenv("SMTP_HOST", "smtp.gmail.com"),
                          int(os.getenv("SMTP_PORT", "465"))) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.sendmail(msg["From"], msg["To"].split(","), msg.as_string())


BASE = "docs/concursos.json"
import unicodedata

STOP = set("de del la el los las en y a al para por con un una the of and for et le les des du der die das und für von im zum zur van het een voor en og i for til af på".split())


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]{3,}", t) if w not in STOP}


def _jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def duplicados(a, b):
    if a.get("country") != b.get("country"):
        return False
    da, db = (a.get("deadline") or "")[:10], (b.get("deadline") or "")[:10]
    plazo_ok = (not da or not db or da == db)
    ta, tb = _norm(a.get("title")) | _norm(a.get("place")), _norm(b.get("title")) | _norm(b.get("place"))
    ba, bb = _norm(a.get("buyer")), _norm(b.get("buyer"))
    if _jac(ta, tb) >= 0.5 and plazo_ok:
        return True
    if ba and bb and _jac(ba, bb) >= 0.5 and da and db and da == db:
        return True
    if ba and bb and _jac(ba, bb) >= 0.6 and _jac(ta, tb) >= 0.2 and plazo_ok:
        return True
    return False


def fusionar(dest, src):
    """Completa dest con lo que le falte de src y anota la fuente alternativa."""
    for k, v in src.items():
        if v and not dest.get(k) and k not in ("num", "source", "url", "first_seen", "alt"):
            dest[k] = v
    alt = dest.setdefault("alt", [])
    if src.get("url") and all(x.get("url") != src["url"] for x in alt):
        alt.append({"source": src.get("source", ""), "url": src["url"], "num": src.get("num", "")})
    return dest


DOMINIOS = {"arkitekt.se": "https://www.arkitekt.se", "safa.fi": "https://www.safa.fi", "bouwmeester": "https://www.vlaamsbouwmeester.be",
            "konkurado": "https://konkurado.ch", "bma.brussels": "https://bma.brussels", "cellule.archi": "https://cellule.archi",
            "concorsiawn.it": "https://concorsiawn.it", "architektura.info": "https://architektura.info", "sarp.warszawa.pl": "https://sarp.warszawa.pl",
            "arkitektforbundet.no": "https://arkitektforbundet.no", "oasrs encomenda": "https://encomenda.oasrs.org", "oasrn": "http://www.oasrn.org",
            "architekturwettbewerb.at": "https://www.architekturwettbewerb.at"}


NUTS_ES = {"ES111": "A Coruña", "ES112": "Lugo", "ES113": "Ourense", "ES114": "Pontevedra", "ES120": "Asturias", "ES130": "Cantabria",
           "ES211": "Álava", "ES212": "Gipuzkoa", "ES213": "Bizkaia", "ES220": "Navarra", "ES230": "La Rioja", "ES241": "Huesca",
           "ES242": "Teruel", "ES243": "Zaragoza", "ES300": "Madrid", "ES411": "Ávila", "ES412": "Burgos", "ES413": "León",
           "ES414": "Palencia", "ES415": "Salamanca", "ES416": "Segovia", "ES417": "Soria", "ES418": "Valladolid", "ES419": "Zamora",
           "ES421": "Albacete", "ES422": "Ciudad Real", "ES423": "Cuenca", "ES424": "Guadalajara", "ES425": "Toledo", "ES431": "Badajoz",
           "ES432": "Cáceres", "ES511": "Barcelona", "ES512": "Girona", "ES513": "Lleida", "ES514": "Tarragona", "ES521": "Alicante",
           "ES522": "Castellón", "ES523": "Valencia", "ES531": "Eivissa-Formentera", "ES532": "Mallorca", "ES533": "Menorca",
           "ES611": "Almería", "ES612": "Cádiz", "ES613": "Córdoba", "ES614": "Granada", "ES615": "Huelva", "ES616": "Jaén",
           "ES617": "Málaga", "ES618": "Sevilla", "ES620": "Murcia", "ES630": "Ceuta", "ES640": "Melilla", "ES703": "El Hierro",
           "ES704": "Fuerteventura", "ES705": "Gran Canaria", "ES706": "La Gomera", "ES707": "La Palma", "ES708": "Lanzarote",
           "ES709": "Tenerife", "ES11": "Galicia", "ES12": "Asturias", "ES13": "Cantabria", "ES21": "País Vasco", "ES22": "Navarra",
           "ES23": "La Rioja", "ES24": "Aragón", "ES30": "Madrid", "ES41": "Castilla y León", "ES42": "Castilla-La Mancha",
           "ES43": "Extremadura", "ES51": "Cataluña", "ES52": "Comunidad Valenciana", "ES53": "Baleares", "ES61": "Andalucía",
           "ES62": "Murcia", "ES63": "Ceuta", "ES64": "Melilla", "ES70": "Canarias", "ES": "España"}


def limpiar_lugar(c):
    p = str(c.get("place") or "").strip()
    if re.fullmatch(r"ES\d{0,3}", p):
        c["place"] = NUTS_ES.get(p, p)
    return c


def fix_url(c):
    u = str(c.get("url") or "").strip()
    if u and not u.lower().startswith("http"):
        dom = DOMINIOS.get(c.get("source", ""), "")
        u = (dom + ("" if u.startswith("/") else "/") + u) if dom else ""
    c["url"] = u
    if str(c.get("source", "")).startswith("COAVN"):
        # la ficha del COAVN pide sesión de colegiado; la búsqueda del anuncio va como alternativa
        if "coavn.org" not in c.get("url", "") and c.get("coavn_url"):
            c["url"] = c["coavn_url"]
        c["alt"] = [a for a in c.get("alt", []) if a.get("source") not in ("buscar el anuncio", "COAVN (con sesión)")]
    return c


def dedupe(items, base):
    """Fusiona repetidos entre fuentes; prefiere la fuente nacional al TED."""
    res = []
    for c in items:
        m = next((r for r in res if duplicados(r, c)), None)
        if m is None:
            m = next((r for r in base if duplicados(r, c)), None)
            if m is not None:
                fusionar(m, c)               # ya en la base de otra semana
                continue
            res.append(c)
            continue
        if (m.get("source") == "TED" and c.get("source") != "TED") or (c.get("docs") and not m.get("docs")):
            i = res.index(m)
            res[i] = fusionar(c, m)
        else:
            fusionar(m, c)
    return res


def load_base():
    try:
        return json.load(open(BASE, encoding="utf-8"))
    except Exception:
        return []


if __name__ == "__main__":
    raw = fetch()
    items = [c for c in (clean(n) for n in raw) if c]
    print(f"TED: {len(raw)} avisos, {len(items)} tras filtro")
    for f in FUENTES:
        extra = f.fetch()
        print(f"{f.__name__}: {len(extra)}")
        items += extra
    items = [limpiar_lugar(fix_url(c)) for c in items]
    base = [limpiar_lugar(c) for c in load_base()]
    known = {c["num"]: c for c in base}
    items = [c for c in items if c["num"] not in known] + [known[c["num"]] and c for c in items if c["num"] in known]
    items = dedupe(items, [b for b in base if all(b["num"] != c["num"] for c in items)])
    today = dt.date.today().isoformat()
    new = []
    for c in items:
        if c["num"] in known:
            known[c["num"]].update({k: v for k, v in c.items() if v})  # refresca plazo, etc.
        else:
            c["first_seen"] = today
            base.append(c)
            new.append(c)
    traducir(new)
    os.makedirs("docs", exist_ok=True)
    json.dump(base, open(BASE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"base: {len(base)} en total, {len(new)} nuevos")
    out = html(new)
    with open("ultimo_listado.html", "w", encoding="utf-8") as f:
        f.write(out)
    if os.getenv("MAIL_TO"):
        asunto = f"Concursos arquitectura Europa · {len(new)} nuevos"
        if any(es_open_oproep(c) for c in new):
            asunto = "OPEN OPROEP · " + asunto
        send(asunto, out)
        print("mail enviado a", os.environ["MAIL_TO"])
    else:
        print("MAIL_TO no definido: no se envía mail")
