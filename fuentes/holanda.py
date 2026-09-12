"""Países Bajos · TenderNed, webservice pública TNS (JSON, sin credenciales).
Lee las publicaciones recientes y conserva prijsvragen, ontwerpwedstrijden,
architectenselecties y opdrachten de arquitectura (CPV 712)."""
import os, re, json, datetime as dt, requests

API = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)", "Accept": "application/json"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
KEY = re.compile(r"prijsvraag|ontwerpwedstrijd|ontwerpcompetitie|architectenselectie|architect(en)?keuze|"
                 r"selectie (van )?(een )?architect|ontwerpteam|ontwerpend onderzoek|stedenbouwkundig ontwerp|"
                 r"landschapsontwerp|ontwerpopdracht|design competition", re.I)
EXCL = re.compile(r"marktconsultatie|rectificatie|gunning|aankondiging van een gegunde|installatie|onderhoud|"
                  r"schoonmaak|ict\b|software|catering", re.I)


def _first(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return ""


def _txt(v):
    if isinstance(v, dict):
        return " ".join(str(x) for x in v.values())
    if isinstance(v, list):
        return " ".join(_txt(x) for x in v)
    return str(v)


def _code(v):
    return (v or {}).get("code", "") if isinstance(v, dict) else str(v or "")


def _oms(v):
    return (v or {}).get("omschrijving", "") if isinstance(v, dict) else str(v or "")


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out, vistos = [], set()
    for page in range(0, 25):                       # ~100 publicaciones/día
        try:
            r = requests.get(API, params={"page": page, "size": 100}, headers=UA, timeout=60)
            r.raise_for_status()
            pubs = r.json().get("content", [])
        except Exception as e:
            print("tenderned:", e)
            break
        if not pubs:
            break
        old = False
        for p in pubs:
            pid = str(p.get("publicatieId", ""))
            pub = str(p.get("publicatieDatum", ""))[:10]
            if pub and pub < since:
                old = True
                continue
            if not pid or pid in vistos:
                continue
            vistos.add(pid)
            tpub = _code(p.get("typePublicatie"))          # AAO aviso, AGO adjudicada, REC rectificación...
            pcode = _code(p.get("publicatiecode"))          # EF23 / EF24 = concurso de proyectos
            topd = _code(p.get("typeOpdracht"))             # D servicios, W obras, L suministros
            title = str(p.get("aanbestedingNaam", ""))
            desc = str(p.get("opdrachtBeschrijving", "") or "")
            es_concurso = pcode in ("EF23", "EF24") or "prijsvraag" in _oms(p.get("typePublicatie")).lower()
            if not es_concurso:
                if tpub not in ("AAO", "VAA") or topd != "D":
                    continue
                if not KEY.search(title + " " + desc[:600]) or EXCL.search(title):
                    continue
            proc = _oms(p.get("procedure"))
            acc = "abierto" if re.search(r"^openbaar|prijsvraag", proc, re.I) or (es_concurso and _code(p.get("procedure")) == "OPE") else \
                  "seleccion" if re.search(r"niet-openbaar|selectie|onderhandel|concurrentie", proc, re.I) else ""
            out.append({"num": "TN-" + pid, "title": title[:200], "buyer": str(p.get("opdrachtgeverNaam", "")),
                        "country": "NLD", "pub": pub,
                        "deadline": str(p.get("sluitingsDatum", "") or "")[:16].replace("T", " "),
                        "place": "", "url": f"https://www.tenderned.nl/aankondigingen/overzicht/{pid}",
                        "source": "TenderNed", "proc": acc, "kind": "concurso" if es_concurso else "licitación con concurso",
                        "desc": " · ".join(x for x in [_oms(p.get("typePublicatie")), proc, desc[:300]] if x)})
        if old:
            break
    return out


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
