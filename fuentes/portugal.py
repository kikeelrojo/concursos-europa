"""Portugal.
- OA Secção Regional Sul, plataforma da encomenda (encomenda.oasrs.org):
  concursos en curso, propios y de otros promotores.
- OA Secção Regional Norte (oasrn.org): lista de contratación; se conservan
  solo los «Concurso de Conceção» / ideias (no conceção-construção).
- Vigilante de «Concursos › Nacional» de la Ordem (en construcción)."""
import os, re, datetime as dt, requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
SUL = ["https://encomenda.oasrs.org/concursos/oasrs", "https://encomenda.oasrs.org/concursos/outros"]
NORTE = ["http://www.oasrn.org/concursos.php?pag=concursos&type=1", "http://www.oasrn.org/concursos.php?pag=concursos&type=3"]
NACIONAL = "https://www.ordemdosarquitectos.org/servicos/concursos/nacional"
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
DMY = re.compile(r"(\d{1,2})[-./](\d{2})[-./](\d{4})")
CONCECAO = re.compile(r"concurso (p[úu]blico )?de conce[pç]ç?[aã]o|concurso de ideias|concurso limitado por pr[ée]via qualifica[cç][aã]o.*conce", re.I)
EXCL = re.compile(r"conce[pç]ç?[aã]o[\s/–-]*constru|empreitada|concess[aã]o|revis[aã]o d[eo] projeto|levantamento|certificados|stand", re.I)
MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def _fecha_pt(s):
    m = re.search(r"(\d{1,2}) de ([a-zç]+) de (\d{4})", s or "", re.I)
    if m and m.group(2).lower() in MESES:
        return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = DMY.search(s or "")
    return f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}" if m else ""


def _acceso(t):
    t = t.lower()
    if "limitado por prévia qualificação" in t or "limitado por previa" in t:
        return "seleccion"
    if "público" in t or "publico" in t or "concurso de conceção" in t:
        return "abierto"
    return ""


def _ficha_sul(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [" ".join(l.split()) for l in soup.get_text("\n").split("\n") if l.strip()]
    texto = "\n".join(lines)
    d = {"deadline": "", "buyer": "", "place": "", "desc": "", "value": ""}
    m = re.search(r"conclu[ií]do\s*(\d{4}-\d{2}-\d{2})", texto)
    if m:
        d["deadline"] = m.group(1)
    m = re.search(r"Propostas at[ée] ([^\n]+)", texto)
    if m and not d["deadline"]:
        d["deadline"] = _fecha_pt(m.group(1))
    m = re.search(r"promotor\s*([^\n]+)", texto)
    d["buyer"] = m.group(1).strip() if m else ""
    m = re.search(r"localiza[cç][aã]o\s*([^\n]+)", texto)
    d["place"] = m.group(1).strip() if m else ""
    try:
        i = lines.index("descrição")
        d["desc"] = " ".join(lines[i + 1:i + 6])[:700]
    except ValueError:
        pass
    m = re.search(r"Valor (m[áa]ximo )?para o custo da obra[^\d€]*€?\s*([\d.]+,\d{2})", texto, re.I)
    if m:
        d["value"] = m.group(2).replace(".", "").split(",")[0]
    pr = re.search(r"Pr[ée]mios([^\n]*\n){1,4}", texto)
    if pr:
        d["desc"] = "Prémios: " + " ".join(pr.group(0).split("\n")[1:4]).strip()[:200] + " · " + d["desc"]
    return d


def sul():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    hoy = dt.date.today().isoformat()
    out = {}
    for lista in SUL:
        try:
            r = requests.get(lista, headers=UA, timeout=60)
            r.raise_for_status()
        except Exception as e:
            print("oasrs:", e)
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "/concursos/detalhe/" not in h:
                continue
            t = " ".join(a.get_text(" ", strip=True).split())
            if t.startswith("ANÁLISE") or "A decorrer" not in t:
                continue
            m = ISO.search(t)
            pub = m.group(0) if m else ""
            title = re.sub(r"\s*Concurso\s*•.*$", "", t).strip() or t.split("A decorrer", 1)[-1].strip() or t
            if pub and pub < since:
                # sigue en curso: lo dejamos entrar solo la primera vez (dedupe por num en la base)
                pass
            try:
                f = _ficha_sul(h)
            except Exception as e:
                print("oasrs ficha:", h, e)
                f = {"deadline": "", "buyer": "", "place": "", "desc": "", "value": ""}
            if f["deadline"] and f["deadline"] < hoy:
                continue
            num = "OASRS-" + h.rstrip("/").split("/detalhe/")[-1].split("/")[0]
            out.setdefault(num, {"num": num, "title": title, "buyer": f["buyer"], "country": "PRT", "pub": pub,
                                 "deadline": f["deadline"], "place": f["place"], "url": h, "source": "oasrs encomenda",
                                 "proc": "abierto", "value": f["value"], "cur": "EUR" if f["value"] else "", "desc": f["desc"]})
    return list(out.values())


def _ficha_norte(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    texto = " ".join(BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True).split())
    d = {"buyer": "", "pub": "", "deadline": "", "desc": "", "value": ""}
    m = re.search(r"Entidade Adjudicante:\s*(.+?)\s*Anúncio:", texto)
    d["buyer"] = m.group(1) if m else ""
    m = re.search(r"Data de envio do anúncio para publicação:\s*(\d{2}-\d{2}-\d{4})", texto)
    if m:
        d["pub"] = _fecha_pt(m.group(1))
    m = re.search(r"Prazo para apresenta[cç][aã]o d[oa]s? (?:trabalhos|propostas|candidaturas)[^:]*:\s*(\d+)\s*DIAS", texto, re.I)
    if m and d["pub"]:
        d["deadline"] = (dt.date.fromisoformat(d["pub"]) + dt.timedelta(days=int(m.group(1)))).isoformat()
        d["desc"] = f"Prazo: {m.group(1)} dias desde el anuncio (fecha estimada)"
    m = re.search(r"Preço Base:\s*([\d.]+,\d{2})", texto)
    if m:
        d["value"] = m.group(1).replace(".", "").split(",")[0]
    m = re.search(r"Prémios:\s*(.+?)(?:Acesso ao processo|\.{5,}|$)", texto)
    if m:
        d["desc"] = (d["desc"] + " · " if d["desc"] else "") + "Prémios: " + m.group(1).strip()[:200]
    m = re.search(r"Anúncio:\s*(D\.R\.[^A-Z]{0,60})", texto)
    if m:
        d["desc"] = (d["desc"] + " · " if d["desc"] else "") + m.group(1).strip()
    return d


def norte():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    hoy = dt.date.today().isoformat()
    out = {}
    for lista in NORTE:
        try:
            r = requests.get(lista, headers=UA, timeout=60)
            r.raise_for_status()
        except Exception as e:
            print("oasrn:", e)
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        n = 0
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "pag=detalhe" not in h:
                continue
            t = " ".join(a.get_text(" ", strip=True).split())
            if not CONCECAO.search(t) or EXCL.search(t):
                continue
            if h.startswith("/") or not h.startswith("http"):
                h = "http://www.oasrn.org/" + h.lstrip("/")
            n += 1
            if n > 15:
                break
            try:
                f = _ficha_norte(h)
            except Exception as e:
                print("oasrn ficha:", h, e)
                f = {"buyer": "", "pub": "", "deadline": "", "desc": "", "value": ""}
            if (f["deadline"] and f["deadline"] < hoy) or (f["pub"] and f["pub"] < since and not f["deadline"]):
                continue
            mid = re.search(r"id=(\d+)", h)
            num = "OASRN-" + (mid.group(1) if mid else h[-20:])
            out.setdefault(num, {"num": num, "title": t, "buyer": f["buyer"], "country": "PRT", "pub": f["pub"],
                                 "deadline": f["deadline"], "place": "Norte", "url": h, "source": "oasrn",
                                 "proc": _acceso(t), "value": f["value"], "cur": "EUR" if f["value"] else "", "desc": f["desc"]})
    return list(out.values())


def vigilante():
    try:
        r = requests.get(NACIONAL, headers=UA, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("ordem nacional:", e)
        return []
    txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    if re.search(r"em constru[cç][aã]o|n[aã]o encontrada", txt, re.I):
        return []
    return [{"num": "OA-NACIONAL-ACTIVA", "title": "AVISO: la Ordem dos Arquitectos ha activado su página nacional de concursos; hay que escribir el lector",
             "buyer": "Ordem dos Arquitectos", "country": "PRT", "pub": dt.date.today().isoformat(), "deadline": "",
             "place": "", "url": NACIONAL, "source": "ordemdosarquitectos.org", "proc": "", "desc": ""}]


def fetch():
    return sul() + norte() + vigilante()


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
