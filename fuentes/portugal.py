"""Portugal · Ordem dos Arquitectos.
Vigilante de la página «Concursos › Nacional» (hoy en construcción): el día que
tenga contenido, emite un aviso en el mail para escribir el lector definitivo.
(La función bolsa() queda disponible pero no se usa: la Bolsa de Emprego solo
trae plazas de funcionario.)"""
import os, re, json, datetime as dt, requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
BOLSA = "https://www.ordemdosarquitectos.org/bolsa_emprego?type=CONCURSOS&p={p}"
NACIONAL = "https://www.ordemdosarquitectos.org/servicos/concursos/nacional"
DISENO = re.compile(r"concurso de (conce[pç]ç?ão|ideias|projeto)|concurso p[úu]blico de conce", re.I)
DMY = re.compile(r"(\d{1,2})[./](\d{2})[./](\d{4})")


def _fecha(s):
    s = s or ""
    m = DMY.search(s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}"
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else ""


def bolsa():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out = []
    for p in (1, 2):
        try:
            r = requests.get(BOLSA.format(p=p), headers=UA, timeout=60)
            r.raise_for_status()
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            data = json.loads(m.group(1))["props"]["pageProps"]["empregos"]["data"]
        except Exception as e:
            print("ordem bolsa:", e)
            break
        old = False
        for e in data:
            pub = _fecha(e.get("data_publicacao")) or (e.get("publishedAt") or "")[:10]
            if pub and pub < since:
                old = True
                continue
            texto = re.sub(r"<[^>]+>", " ", e.get("descricao") or "")
            if not DISENO.search(e.get("titulo", "") + " " + texto):
                continue
            out.append({"num": f"OA-{e.get('id')}", "title": e.get("titulo", ""), "buyer": "",
                        "country": "PRT", "pub": pub, "deadline": "", "place": "",
                        "url": f"https://www.ordemdosarquitectos.org/bolsa_emprego/concursos/{e.get('slug')}",
                        "source": "ordemdosarquitectos.org", "proc": "", "desc": " ".join(texto.split())[:600]})
        if old:
            break
    return out


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
    return [{"num": "OA-NACIONAL-ACTIVA", "title": "AVISO: la Ordem dos Arquitectos ha activado su página de concursos; hay que escribir el lector",
             "buyer": "Ordem dos Arquitectos", "country": "PRT", "pub": dt.date.today().isoformat(), "deadline": "",
             "place": "", "url": NACIONAL, "source": "ordemdosarquitectos.org", "proc": "", "desc": ""}]


def fetch():
    return vigilante()          # la Bolsa de Emprego queda fuera: solo plazas de funcionario


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
