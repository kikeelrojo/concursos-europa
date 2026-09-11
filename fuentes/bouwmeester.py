"""Vlaams Bouwmeester (BE): Open Oproep (OO) y Oproep aan geïnteresseerden (OAG).
Lee el bloque «Deadlines» de la portada (solo convocatorias abiertas, con plazo)
y completa con la lista de proyectos «Nog niet opgestart»."""
import re, requests
from bs4 import BeautifulSoup

HOME = "https://www.vlaamsbouwmeester.be/nl"
LIST = "https://www.vlaamsbouwmeester.be/nl/projecten"
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
CODE = re.compile(r"\b(OO|OAG)\s?(\d{4})\b")
DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2})\.(\d{2})\s*uur")
SKIP = ("Meesterproef", "MP")  # solo para recién titulados


def _item(code, title, url, deadline=""):
    tool = "Open Oproep" if code.startswith("OO") else "Oproep aan geïnteresseerden"
    return {"num": code, "title": f"{title} ({tool})", "buyer": "Vlaams Bouwmeester",
            "country": "BEL", "pub": "", "deadline": deadline,
            "place": "Vlaanderen", "url": url, "source": "bouwmeester"}


def _deadlines(soup):
    """Bloque «Deadlines» de la portada: div.deadline con fecha, título y enlace."""
    out = {}
    for d in soup.select("div.deadline"):
        date = d.select_one(".deadline__date")
        title = d.select_one(".deadline__title")
        a = d.find("a", href=True)
        if not (date and title):
            continue
        m = DATE.search(" ".join(date.get_text(" ", strip=True).split()))
        t = " ".join(title.get_text(" ", strip=True).split())
        c = CODE.search(t)
        if not c or t.startswith(SKIP):
            continue
        code = c.group(1) + c.group(2)
        dl = f"{m.group(3)}-{m.group(2)}-{m.group(1)} {m.group(4)}:{m.group(5)}" if m else ""
        url = a["href"] if a else HOME
        if url.startswith("/"):
            url = "https://www.vlaamsbouwmeester.be" + url
        out[code] = _item(code, CODE.sub("", t).strip(" -–"), url, dl)
    return out


def _open_list(soup):
    out = {}
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=True)
        if not a:
            continue
        card = h3.parent.get_text(" ", strip=True)
        if not CODE.search(card) and h3.parent.parent:
            card = h3.parent.parent.get_text(" ", strip=True)
        c = CODE.search(card)
        if not c or "Nog niet opgestart" not in card or any(s in card for s in SKIP):
            continue
        code = c.group(1) + c.group(2)
        href = a["href"] if a["href"].startswith("http") else "https://www.vlaamsbouwmeester.be" + a["href"]
        out[code] = _item(code, a.get_text(strip=True), href)
    return out


def fetch():
    items = {}
    for url, fn in ((HOME, _deadlines), (LIST, _open_list)):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            found = fn(BeautifulSoup(r.text, "html.parser"))
            for k, v in found.items():
                items.setdefault(k, v)           # la portada (con plazo) manda
        except Exception as e:                    # una fuente caída no tumba el mail
            print("bouwmeester:", url, e)
    return list(items.values())


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
