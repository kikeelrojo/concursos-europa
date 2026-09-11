#!/usr/bin/env python3
"""
Buscador semanal de concursos de arquitectura en Europa (TED).
Consulta la Search API pública del TED (sin clave), filtra concursos de
proyectos (design contest) de los países elegidos y envía un mail HTML.
"""
import os, re, sys, smtplib, datetime as dt, json
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
          "deadline-receipt-tender-date-lot", "place-of-performance", "classification-cpv"]
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
        "place": lang(n.get("place-of-performance")),
        "url": f"https://ted.europa.eu/es/notice/-/detail/{n.get('publication-number','')}",
        "source": "TED",
    }


def html(items):
    today = dt.date.today().strftime("%d.%m.%Y")
    css = ("font-family:Helvetica,Arial,sans-serif;color:#000;"
           "font-size:13px;line-height:1.4")
    rows = []
    for c in sorted(items, key=lambda x: (x["country"], x["deadline"] or "z")):
        rows.append(
            f"<tr><td style='padding:6px 8px 6px 0;vertical-align:top'><b>{c['country']}</b></td>"
            f"<td style='padding:6px 8px;vertical-align:top'><a href='{c['url']}' "
            f"style='color:#000'>{c['title']}</a><br>{c['buyer']}"
            f"{(' · ' + c['place']) if c['place'] else ''}</td>"
            f"<td style='padding:6px 0 6px 8px;vertical-align:top;white-space:nowrap'>"
            f"{'límite ' + c['deadline'] if c['deadline'] else ('pub. ' + c['pub'] if c['pub'] else 'en cartera')}</td></tr>")
    table = ("<table style='border-collapse:collapse'>" + "".join(rows) + "</table>"
             if rows else "<p>Sin concursos nuevos esta semana.</p>")
    return (f"<div style='{css}'><p><b>CONCURSOS DE ARQUITECTURA · EUROPA</b><br>"
            f"semana del {today} · {len(items)} nuevos · TED + fuentes nacionales</p>{table}"
            f"<p style='margin-top:24px'>×</p></div>")


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


SEEN = "vistos.json"


def load_seen():
    try:
        return set(json.load(open(SEEN)))
    except Exception:
        return set()


if __name__ == "__main__":
    raw = fetch()
    items = [c for c in (clean(n) for n in raw) if c]
    print(f"TED: {len(raw)} avisos, {len(items)} tras filtro")
    for f in FUENTES:
        extra = f.fetch()
        print(f"{f.__name__}: {len(extra)}")
        items += extra
    seen = load_seen()
    items = [c for c in items if c["num"] not in seen]
    json.dump(sorted(seen | {c["num"] for c in items}), open(SEEN, "w"))
    out = html(items)
    with open("ultimo_listado.html", "w", encoding="utf-8") as f:
        f.write(out)
    if os.getenv("MAIL_TO"):
        send(f"Concursos arquitectura Europa · {len(items)} nuevos", out)
    else:
        print(json.dumps(items, ensure_ascii=False, indent=1))
