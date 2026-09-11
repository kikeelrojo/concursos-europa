"""Polonia: agregador architektura.info (konkursy architektoniczne) + lista
«Bieżące» del SARP Oddział Warszawski."""
import os, re, datetime as dt, requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
AI = "https://architektura.info/wiadomosci/konkursy_architektoniczne"
SARP_W = "https://sarp.warszawa.pl/konkurs_stan/biezace/"
MESES = {"styczeń": 1, "stycznia": 1, "luty": 2, "lutego": 2, "marzec": 3, "marca": 3, "kwiecień": 4, "kwietnia": 4,
         "maj": 5, "maja": 5, "czerwiec": 6, "czerwca": 6, "lipiec": 7, "lipca": 7, "sierpień": 8, "sierpnia": 8,
         "wrzesień": 9, "września": 9, "październik": 10, "października": 10, "listopad": 11, "listopada": 11,
         "grudzień": 12, "grudnia": 12}
FECHA_PL = re.compile(r"^([A-Za-zżźćńółęąśŻŹĆŃÓŁĘĄŚ]+)\s+(\d{1,2}),\s+(\d{4})$")
DMY = re.compile(r"(\d{1,2})[./](\d{2})[./](\d{4})")
EXCL = re.compile(r"award|prize|nagroda|studenc|student|dyplom|festival", re.I)


def _iso(m):
    return f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}"


def _acceso(t):
    t = t.lower()
    if "nieograniczon" in t or "otwart" in t:
        return "abierto"
    if "ograniczon" in t or "zaproszen" in t or "dopuszczenie" in t:
        return "seleccion"
    return ""


def architektura_info():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out = []
    for url in (AI, AI + "/(offset)/6", AI + "/(offset)/12"):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
        except Exception as e:
            print("architektura.info:", e)
            break
        soup = BeautifulSoup(r.text, "html.parser")
        links = {a.get_text(" ", strip=True): a["href"] for a in soup.find_all("a", href=True)
                 if "/konkursy_architektoniczne/" in a["href"] and a.get_text(strip=True)
                 and not a.get_text(strip=True).startswith("Czytaj")}
        lines = [" ".join(l.split()) for l in soup.get_text("\n").split("\n") if l.strip()]
        old = False
        i = 0
        while i < len(lines):
            m = FECHA_PL.match(lines[i])
            if m and m.group(1).lower() in MESES and i + 1 < len(lines) and lines[i + 1] in links:
                pub = f"{m.group(3)}-{MESES[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
                title = lines[i + 1]
                block = lines[i + 2:i + 8]
                reg = next((_iso(DMY.search(x)) for x in block if "rejestracji" in x and DMY.search(x)), "")
                ent = next((_iso(DMY.search(x)) for x in block if "składania" in x and DMY.search(x)), "")
                city = next((x.split(":", 1)[1].strip() for x in block if x.startswith("Miasto")), "")
                desc = next((x for x in block if len(x) > 60 and ":" not in x[:25]), "")
                i += 2
                if pub < since:
                    old = True
                    continue
                if EXCL.search(title) or "międzynarodow" in city.lower():
                    continue
                href = links[title]
                if href.startswith("/"):
                    href = "https://architektura.info" + href
                out.append({"num": "PL-" + href.rstrip("/").rsplit("/", 1)[-1][:50], "title": title, "buyer": "",
                            "country": "POL", "pub": pub, "deadline": reg or ent, "place": city, "url": href,
                            "source": "architektura.info", "proc": _acceso(title + " " + desc),
                            "desc": (f"Entrega de trabajos: {ent} · " if ent and reg else "") + desc})
                continue
            i += 1
        if old:
            break
    return out


def sarp_warszawa():
    out = []
    try:
        r = requests.get(SARP_W, headers=UA, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("sarp warszawa:", e)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    for h in soup.find_all(["h2", "h3"]):
        a = h.find("a", href=True)
        if not a or "/sarp_konkurs/" not in a["href"]:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        # texto del bloque: hermanos hasta el siguiente encabezado
        parts, node = [], h
        while True:
            node = node.find_next_sibling()
            if node is None or node.name in ("h2", "h3"):
                break
            parts.append(node.get_text("\n", strip=True))
        texto = "\n".join(parts)
        if not texto:
            cont = h.find_parent(["article", "div"])
            texto = cont.get_text("\n", strip=True) if cont else ""
        fechas = [(DMY.search(l), l) for l in texto.split("\n") if DMY.search(l)]
        wn = next((_iso(m) for m, l in fechas if re.search(r"wniosk|dopuszczen", l, re.I)), "")
        pr = next((_iso(m) for m, l in fechas if re.search(r"prac konkursow|składania prac", l, re.I)), "")
        num = re.search(r"Konkurs SARP nr\s*(\d+)", texto, re.I)
        m2 = re.search(r"([\d\s.,]+)\s*m[²2]", texto)
        nag = re.search(r"I Nagrod[ay][^\n]*?([\d\s]+)\s*zł", texto, re.I)
        desc = " ".join(texto.split("\n")[:4])[:700]
        out.append({"num": "SARP-" + (num.group(1) if num else a["href"].rstrip("/").rsplit("/", 1)[-1][:40]),
                    "title": title, "buyer": "", "country": "POL", "pub": "", "deadline": wn or pr,
                    "place": "", "url": a["href"], "source": "sarp.warszawa.pl", "proc": _acceso(title + " " + texto[:600]),
                    "desc": " · ".join(x for x in [
                        f"Entrega de trabajos: {pr}" if pr and wn else "",
                        f"1er premio: {nag.group(1).strip()} zł" if nag else "",
                        f"{m2.group(0).strip()}" if m2 else "", desc] if x)})
    return out


def fetch():
    items = architektura_info() + sarp_warszawa()
    vistos, res = set(), []
    for c in items:
        if c["num"] not in vistos:
            vistos.add(c["num"]); res.append(c)
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
