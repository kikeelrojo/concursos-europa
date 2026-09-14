"""BMA · bouwmeester maître architecte de Bruselas: appels à candidatures.
Lista https://bma.brussels/news/ y ficha de cada appel (maître d'ouvrage,
programa, presupuesto, honorarios, indemnización y fecha límite)."""
import os, re, datetime as dt, requests
from bs4 import BeautifulSoup

LIST = "https://bma.brussels/news/"
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
MAX = 10
DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def _campo(texto, *etiquetas):
    for e in etiquetas:
        m = re.search(e + r"\s*:\s*(.+)", texto, re.I)
        if m:
            return m.group(1).strip()
    return ""


def _ficha(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    meta = soup.find("meta", property="article:published_time")
    pub = meta["content"][:10] if meta and meta.get("content") else ""
    h1 = soup.find_all("h1")
    title = h1[-1].get_text(strip=True) if h1 else url
    sub = soup.find("h2")
    sub = sub.get_text(strip=True) if sub else ""
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    texto = "\n".join(lines)
    buyer = _campo(texto, "MAÎTRE D.OUVRAGE", "OPDRACHTGEVER", "CLIENT")
    prog = _campo(texto, "PROGRAMME", "PROGRAMMA")
    budget = _campo(texto, "BUDGET")
    hon = _campo(texto, "HONORAIRES", "ERELOON", "FEES")
    defr = _campo(texto, "DÉFRAIEMENT", "DEFRAIEMENT", "VERGOEDING", "COMPENSATION")
    addr = _campo(texto, "ADRESSE", "ADRES", "ADDRESS")
    dl = ""
    m = re.search(r"DATE LIMITE[^\d]{0,80}?(\d{2})\.(\d{2})\.(\d{4})(?:\s*à\s*(\d{1,2})\s*[Hh]\s*(\d{2})?)?", texto, re.I | re.S) \
        or re.search(r"(?:UITERSTE|DEADLINE)[^\d]{0,80}?(\d{2})\.(\d{2})\.(\d{4})", texto, re.I | re.S)
    if m:
        dl = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        if m.lastindex and m.lastindex >= 4 and m.group(4):
            dl += f" {int(m.group(4)):02d}:{m.group(5) or '00'}"
    val = ""
    mv = re.search(r"€\s*([\d.\s]+)", budget)
    if mv:
        val = re.sub(r"[.\s]", "", mv.group(1))
    # descripción: primeros párrafos entre el h1 y «APPEL À CANDIDATURES»
    desc = ""
    try:
        i = lines.index(title)
        j = next(k for k, l in enumerate(lines) if k > i and re.match(r"APPEL|OPROEP|CALL", l))
        desc = " ".join(lines[i + 1:j])[:900]
    except (ValueError, StopIteration):
        pass
    extra = " · ".join(x for x in [f"Presupuesto: {budget}" if budget else "",
                                   f"Honorarios: {hon}" if hon else "",
                                   f"Retribución: {defr}" if defr else "", desc] if x)
    return {"num": "BMA-" + url.rstrip("/").rsplit("/", 1)[-1][:50],
            "title": f"{title} — {sub}" if sub else title, "buyer": buyer, "country": "BEL",
            "pub": pub, "deadline": dl, "place": addr or "Bruselas", "url": url, "source": "bma.brussels",
            "proc": "seleccion", "value": val, "cur": "EUR" if val else "", "desc": extra}


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out = []
    try:
        r = requests.get(LIST, headers=UA, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("bma lista:", e)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith("https://bma.brussels/") and "APPELS" in a.get_text(" ", strip=True).upper() \
                and h not in urls:
            urls.append(h)
    for u in urls[:MAX]:
        if re.search(r"/news/?$|/appels/?$|/oproepen/?$|/calls/?$", u):
            continue                                   # página de listado, no un appel
        try:
            it = _ficha(u)
        except Exception as e:
            print("bma ficha:", u, e)
            continue
        if not it["deadline"] and not it["buyer"]:
            continue                                   # sin fecha límite ni maître d'ouvrage: no es una ficha de appel
        hoy = dt.date.today().isoformat()
        if it["deadline"] and it["deadline"][:10] < hoy:
            continue                                   # plazo vencido
        if not it["deadline"] and it["pub"] and it["pub"] < since:
            continue                                   # sin plazo y antiguo
        out.append(it)                                 # abierto: entra aunque se publicara hace semanas
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
