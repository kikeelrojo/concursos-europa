"""Italia: piattaforma concorsiawn.it del CNAPPC (concorsi di progettazione a
due fasi e concorsi di idee). Lee «concorsi attivi» y la portada; descarta
los premios."""
import os, re, datetime as dt, requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
URLS = ["https://concorsiawn.it/concorsi-attivi/", "https://concorsiawn.it/"]
DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
ISO2 = re.compile(r"(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\s+(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2}")


def _parse(html):
    soup = BeautifulSoup(html, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True) if "Vai al concorso" in a.get_text()]
    lines = [" ".join(l.split()) for l in soup.get_text("\n").split("\n") if l.strip()]
    out, k = [], 0
    for i, l in enumerate(lines):
        if l != "Vai al concorso":
            continue
        url = links[k] if k < len(links) else ""
        k += 1
        block = lines[max(0, i - 12):i]
        tipo = next((x for x in reversed(block) if x in ("Concorso di Progettazione", "Concorso di idee", "Concorso di Idee", "Premio di Architettura")), "")
        if not tipo or tipo == "Premio di Architettura" or not url or "premi." in url:
            continue
        ti = block.index(tipo)
        ente = block[ti + 1] if ti + 1 < len(block) else ""
        title = block[ti + 2] if ti + 2 < len(block) else url
        iso = next((ISO2.search(x) for x in block if ISO2.search(x)), None)
        pub = iso.group(1) if iso else ""
        dl1 = next((x for x in block if x.startswith("Scadenza iscrizioni di prima fase") or x.startswith("Scadenza iscrizioni:")), "")
        m = DMY.search(dl1)
        dl = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else (f"{iso.group(2)} {iso.group(3)}" if iso else "")
        dl2 = next((x for x in block if x.startswith("Scadenza iscrizioni di seconda fase")), "")
        city, _, buyer = ente.partition(",")
        out.append({"num": "IT-" + url.rstrip("/").rsplit("/", 1)[-1][:50], "title": f"{title} ({tipo})",
                    "buyer": buyer.strip() or ente, "country": "ITA", "pub": pub, "deadline": dl,
                    "place": city.strip(), "url": url, "source": "concorsiawn.it",
                    "proc": "abierto", "desc": " · ".join(x for x in ["dos fases", dl2, "primera fase abierta, segunda con premio a los seleccionados"] if x)})
    return out


PA_TAGS = ["https://www.professionearchitetto.it/key/concorsi-di-progettazione/",
           "https://www.professionearchitetto.it/key/concorsi-di-idee/"]
PA_EXCL = re.compile(r"student|neolaureat|giovani progettisti|design|grafica|fotograf|premio|award|call for (cover|papers)|tesi", re.I)
PA_DATE = re.compile(r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})", re.I)
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
        "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
REGIONI = ("Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia", "Friuli", "Lazio", "Liguria", "Lombardia", "Marche", "Molise",
           "Piemonte", "Puglia", "Sardegna", "Sicilia", "Toscana", "Trentino", "Umbria", "Valle d'Aosta", "Veneto")


def professionearchitetto():
    """Agregador p+A: concorsi di progettazione e di idee (páginas por etiqueta).
    Cada concurso es un <article> con clase nonscaduta/scaduta."""
    out = {}
    for url in PA_TAGS:
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
        except Exception as e:
            print("professionearchitetto:", e)
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for art in soup.find_all("article"):
            cls = " ".join(art.get("class", []))
            h2 = art.find("h2")
            a = h2.find("a", href=True) if h2 else None
            if not a or "/concorsi/notizie/" not in a["href"] or "scaduta" in cls.split() and "nonscaduta" not in cls.split():
                continue
            if "nonscaduta" not in cls.split():
                continue
            lines = [" ".join(l.split()) for l in art.get_text("\n").split("\n") if l.strip() and l.strip() != "•"]
            title = " ".join(a.get_text(" ", strip=True).split())
            m = next((re.search(r"(\d{2})\.(\d{2})\.(\d{4})", l) for l in lines[:6] if re.search(r"\d{2}\.\d{2}\.\d{4}", l)), None)
            pub = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
            cab = " ".join(lines[:lines.index(title)] if title in lines else lines[:6])
            if PA_EXCL.search(title + " " + cab):
                continue
            h3 = art.find("h3")
            sub = " ".join(h3.get_text(" ", strip=True).split()) if h3 else ""
            after = lines[lines.index(title) + 1:] if title in lines else lines
            desc = next((l for l in after if len(l) > 80), "")
            plazo = next((l for l in after if re.search(r"consegna|scadenza|entro|iscrizion|candidatur", l, re.I) and PA_DATE.search(l)), "")
            md = PA_DATE.search(plazo)
            dl = f"{md.group(3)}-{MESI[md.group(2).lower()]:02d}-{int(md.group(1)):02d}" if md else ""
            region = next((x for x in REGIONI if x.lower() in cab.lower()), "")
            tipo = "concorso di idee" if "idee" in (sub + " " + cab).lower() else "concorso di progettazione"
            href = a["href"] if a["href"].startswith("http") else "https://www.professionearchitetto.it" + a["href"]
            num = "PA-" + href.rstrip("/").split("/notizie/")[-1].split("/")[0]
            out.setdefault(num, {"num": num, "title": title, "buyer": "", "country": "ITA" if region else "INT", "pub": pub, "deadline": dl,
                                 "place": region, "url": href, "source": "professionearchitetto.it",
                                 "proc": "abierto" if re.search(r"aperta|aperto", sub + " " + cab, re.I) else "",
                                 "kind": "concurso", "desc": " · ".join(x for x in [tipo, sub, plazo, desc] if x)})
    return list(out.values())


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    hoy = dt.date.today().isoformat()
    items = {}
    for c in professionearchitetto():
        items.setdefault(c["num"], c)
    for u in URLS:
        try:
            r = requests.get(u, headers=UA, timeout=60)
            r.raise_for_status()
            for c in _parse(r.text):
                if c["deadline"] and c["deadline"][:10] < hoy:
                    continue                     # ya cerrada la primera fase
                items.setdefault(c["num"], c)
        except Exception as e:
            print("concorsiawn:", u, e)
    return list(items.values())


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
