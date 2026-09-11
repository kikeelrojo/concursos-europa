"""Nórdicos. Por ahora Suecia: tävlingar aprobadas por Sveriges Arkitekter
(arkitekt.se/tavlingar/sok-tavlingar), solo con estado «Ej påbörjad» o
«Påbörjad»; ficha para fecha de publicación y plazos."""
import os, re, datetime as dt, requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
SE_LIST = "https://www.arkitekt.se/tavlingar/sok-tavlingar/"
ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")
EXCL = re.compile(r"student|markanvisning", re.I)


def _se_ficha(url):
    d = {"pub": "", "deadline": "", "desc": "", "proc": ""}
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [" ".join(l.split()) for l in soup.get_text("\n").split("\n") if l.strip()]
    texto = "\n".join(lines)
    m = re.search(r"Publicerad:\s*(\d{4}-\d{2}-\d{2})", texto)
    if m:
        d["pub"] = m.group(1)
    hoy = dt.date.today().isoformat()
    cands = []
    for l in lines:
        if ISO.search(l) and re.search(r"inlämning|senast|sista dag|deadline", l, re.I) \
                and not re.search(r"frågor|svar rörande|questions", l, re.I):
            for x in ISO.findall(l):
                if x >= hoy:
                    cands.append(x)
    if cands:
        d["deadline"] = min(cands)
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    d["desc"] = meta["content"][:600] if meta and meta.get("content") else ""
    t = texto.lower()
    d["proc"] = "abierto" if re.search(r"allmän|öppen", t) else "seleccion" if re.search(r"inbjuden|prekvalificering", t) else ""
    return d


def suecia():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out = []
    try:
        r = requests.get(SE_LIST, headers=UA, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("sveriges arkitekter:", e)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    links = {}
    for a in soup.find_all("a", href=True):
        if "/tavling/" in a["href"] and a.get_text(strip=True):
            links.setdefault(" ".join(a.get_text(" ", strip=True).split()), a["href"])
    lines = [" ".join(l.split()) for l in soup.get_text("\n").split("\n") if l.strip()]
    for i, l in enumerate(lines):
        if l not in links:
            continue
        block = lines[i + 1:i + 6]
        status = ""
        for k, x in enumerate(block):
            if x.startswith("Status"):
                status = x.split(":", 1)[1].strip() or (block[k + 1] if k + 1 < len(block) else "")
                break
        if status not in ("Ej påbörjad", "Påbörjad") or EXCL.search(l):
            continue
        tipo = block[0] if block and block[0] in ("Allmän tävling", "Tävling", "Parallellt uppdrag", "Markanvisning") else ""
        desc = next((x for x in block if len(x) > 50 and not x.startswith("Status")), "")
        url = links[l]
        if any(o["url"] == url for o in out):
            continue
        try:
            f = _se_ficha(url)
        except Exception as e:
            print("sveriges arkitekter ficha:", url, e)
            f = {"pub": "", "deadline": "", "desc": desc, "proc": ""}
        if f["pub"] and f["pub"] < since and not f["deadline"]:
            continue
        out.append({"num": "SE-" + url.rstrip("/").rsplit("/", 1)[-1][:50],
                    "title": f"{l} ({tipo})" if tipo else l, "buyer": "", "country": "SWE",
                    "pub": f["pub"], "deadline": f["deadline"], "place": "", "url": url,
                    "source": "arkitekt.se", "proc": f["proc"], "desc": f["desc"] or desc})
    return out


def fetch():
    return suecia()


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
