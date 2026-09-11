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


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    hoy = dt.date.today().isoformat()
    items = {}
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
