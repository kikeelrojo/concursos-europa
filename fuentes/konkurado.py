"""Konkurado (CH): concursos y procedimientos de selección de planificadores.
Lista https://konkurado.ch/de/wettbewerbe (paginada, más recientes primero) y
ficha de cada uno para plazo, descripción y restricción regional."""
import os, re, datetime as dt, requests
from bs4 import BeautifulSoup

BASE = "https://konkurado.ch"
LIST = BASE + "/de/wettbewerbe"
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
MAX_PAGES, MAX_DETAIL = 4, 20
TIPOS = re.compile(r"Projektwettbewerb|Planerwahl|Projektstudie|Studienauftrag|Gesamtleistungswettbewerb|"
                   r"Ideenwettbewerb|concours|mandats? d.?étude|concorso|mandati di studio", re.I)
EXCL = re.compile(r"^Offerte|Request for Information|Direktauftrag", re.I)
DATE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
SKIP_HREF = ("/content/", "/wettbewerbe", "/archiv", "/login", "/apply", "/get-modal", "/logo/", "/de/?$")


def _iso(m):
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _lista(page):
    r = requests.get(LIST, params={"page": page}, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    titles = {}
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(" ", strip=True)
        if not t or not h.startswith(BASE + "/de/") or any(re.search(s, h) for s in SKIP_HREF):
            continue
        if h.count("/") == 4:                      # https://konkurado.ch/de/<slug>
            titles.setdefault(t, h)
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    items, cur = [], None
    for l in lines:
        if l in titles:
            cur = {"title": l, "url": titles[l], "rest": []}
            items.append(cur)
        elif cur is not None and len(cur["rest"]) < 8:
            cur["rest"].append(l)
    out = []
    for it in items:
        rest = it["rest"]
        tipo = next((x for x in rest if re.search(r"Verfahren|procédure|procedura|Prozess", x)), "")
        status = next((x for x in rest if x in ("Veröffentlicht", "Angekündigt", "Publié", "Annoncé")), "")
        fecha = next((_iso(DATE.search(x)) for x in rest if DATE.search(x)), "")
        plz = next((x for x in rest if re.match(r"^\d{4}\s", x)), "")
        buyer = next((x for x in rest if x not in (tipo, status, plz) and not DATE.search(x)
                      and x not in ("S",) and not x.startswith("!")), "")
        out.append({"title": it["title"], "url": it["url"], "tipo": tipo, "status": status,
                    "pub": fecha, "place": plz, "buyer": buyer})
    return out


def _ficha(url):
    d = {"deadline": "", "desc": "", "region": "", "anon": ""}
    try:
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("konkurado ficha:", url, e)
        return d
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    # fechas: línea con fecha seguida de su etiqueta
    fechas = []
    for i, l in enumerate(lines[:-1]):
        m = DATE.fullmatch(l) or (DATE.search(l) if re.fullmatch(r"[\d.\s-]+", l) else None)
        if m:
            fechas.append((_iso(DATE.findall(l) and DATE.search(l)), lines[i + 1]))
    cand = [f for f, lab in fechas if re.search(r"einreich|abgabe|eingabe|bewerbung|remise|dépôt|candidature|consegna|inoltro", lab, re.I)
            and not re.search(r"frage|question|domand|unterlagen|documents", lab, re.I)]
    if cand:
        d["deadline"] = min(cand)
    # descripción y eckdaten
    nav = {"Beschreibung", "Prozess", "Eckdaten", "Jury", "Downloads"}
    for i, l in enumerate(lines[:-1]):
        if l == "Beschreibung" and lines[i + 1] not in nav:
            d["desc"] = " ".join(x for x in lines[i + 1:i + 4] if x not in nav)[:600]
            break
    for i, l in enumerate(lines[:-1]):
        if l == "Regionale Einschränkung":
            d["region"] = lines[i + 1]
        if l == "anonymes Verfahren":
            d["anon"] = lines[i + 1]
    return d


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out, detalles = [], 0
    for page in range(1, MAX_PAGES + 1):
        try:
            items = _lista(page)
        except Exception as e:
            print("konkurado lista:", e)
            break
        if not items:
            break
        old = False
        for it in items:
            if it["pub"] and it["pub"] < since:
                old = True
                continue
            if not TIPOS.search(it["tipo"] + " " + it["title"]) or EXCL.search(it["tipo"]):
                continue
            slug = it["url"].rsplit("/", 1)[-1]
            proc = "abierto" if re.search(r"offen|ouvert|apert", it["tipo"], re.I) else \
                   "seleccion" if re.search(r"selektiv|Einladung|sélectiv|invit", it["tipo"], re.I) else ""
            f = _ficha(it["url"]) if detalles < MAX_DETAIL else {"deadline": "", "desc": "", "region": "", "anon": ""}
            detalles += 1
            extra = " · ".join(x for x in [
                f"Restricción regional: {f['region']}" if f["region"] else "",
                "anónimo" if f["anon"].lower().startswith("ja") else "",
                f["desc"]] if x)
            out.append({"num": "KO-" + slug[:60], "title": f"{it['title']} ({it['tipo']})" if it["tipo"] else it["title"],
                        "buyer": it["buyer"], "country": "CHE", "pub": it["pub"], "deadline": f["deadline"],
                        "place": it["place"], "url": it["url"], "source": "konkurado",
                        "proc": proc, "desc": extra})
        if old:
            break
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
