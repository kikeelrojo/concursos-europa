"""Cellule architecture (Fédération Wallonie-Bruxelles): marchés d'architecture
en cours. Lista https://cellule.archi/fr/marches/appels y ficha de cada uno."""
import re, requests
from bs4 import BeautifulSoup

LIST = "https://cellule.archi/fr/marches/appels"
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
MAX = 15
DATE = re.compile(r"(\d{1,2})\s*/\s*(\d{2})\s*/\s*(\d{4})(?:[^\d\n]{0,12}(\d{1,2})\s*h\s*(\d{2})?)?", re.I)


def _campo(lines, etiqueta):
    for i, l in enumerate(lines[:-1]):
        if l.lower() == etiqueta.lower():
            vals = []
            for x in lines[i + 1:i + 4]:
                if x.lower() in ("type d'opération", "typologies", "type de procédure", "adresse") \
                        or x.startswith("##") or x.startswith("Intégrations"):
                    break
                vals.append(x)
            return " ".join(vals)
    return ""


def _ficha(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    h1 = soup.find("h1")
    title = " ".join(h1.get_text(" ", strip=True).split()) if h1 else url
    place, _, t = title.partition(",")
    if not t:
        place, t = "", title
    sub = ""
    if h1:
        for h in h1.find_all_next("h2"):
            t = " ".join(h.get_text(" ", strip=True).split())
            if 3 < len(t) < 120 and not re.search(r"menu|recherche|cellule\.archi|intégrations", t, re.I):
                sub = t
                break
    lines = [" ".join(l.split()) for l in soup.get_text("\n").split("\n") if l.strip()]
    texto = "\n".join(lines)
    dl = ""
    m = re.search(r"(?:pour le|avant le|au plus tard|jusqu.au|le)\s*\**\s*" + DATE.pattern, texto, re.I) or DATE.search(texto)
    if m:
        g = m.groups()
        dl = f"{g[2]}-{g[1]}-{int(g[0]):02d}" + (f" {int(g[3]):02d}:{g[4] or '00'}" if g[3] else "")
    proc = _campo(lines, "Type de procédure")
    acc = "abierto" if re.search(r"ouvert", proc, re.I) else "seleccion" if re.search(r"restreint|négociation|sélection|concurrentielle", proc, re.I) else ""
    desc = ""
    try:
        i = lines.index(sub) if sub in lines else lines.index(title)
        desc = " ".join(lines[i + 1:i + 5])[:900]
    except ValueError:
        pass
    extra = " · ".join(x for x in [proc, _campo(lines, "Typologies"), _campo(lines, "Type d'opération"), desc] if x)
    return {"num": "CA-" + url.rstrip("/").rsplit("/", 1)[-1][:50], "title": f"{t.strip()} — {sub}" if sub else t.strip(),
            "buyer": "Cellule architecture FWB", "country": "BEL", "pub": "", "deadline": dl,
            "place": place.strip() or _campo(lines, "Adresse"), "url": url, "source": "cellule.archi",
            "proc": acc, "desc": extra}


def fetch():
    out = []
    try:
        r = requests.get(LIST, headers=UA, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("cellule lista:", e)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    urls, cerrado = [], False
    for el in soup.find_all(["h2", "h3", "h4", "a"]):
        if el.name != "a":
            if re.search(r"cl[ôo]tur", el.get_text(), re.I):
                cerrado = True
            continue
        if cerrado:
            break
        h = el.get("href", "")
        if h.startswith("/"):
            h = "https://cellule.archi" + h
        if re.match(r"https://cellule\.archi/(fr/)?marches/[^/?#]+$", h) and not re.search(r"/marches/(appels|termines|guide|prix|modul|cartographie|actualites)", h):
            if h not in urls:
                urls.append(h)
    for u in urls[:MAX]:
        try:
            out.append(_ficha(u))
        except Exception as e:
            print("cellule ficha:", u, e)
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
