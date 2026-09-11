"""Francia · BOAMP (Bulletin officiel des annonces des marchés publics),
API Opendatasoft abierta. Recoge avisos recientes de servicios y se queda con
concours de maîtrise d'œuvre y marchés de maîtrise d'œuvre con concurso /
esquisse (por debajo del umbral europeo, que no llegan al TED)."""
import os, re, json, datetime as dt, requests

API = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
CONCOURS = re.compile(r"concours (restreint |ouvert )?(de |d')?ma[iî]trise d.{0,3}uvre|concours d.?architecture|concours de ma[iî]trise|"
                      r"concours restreint|concours d.?id[ée]es|jury de concours", re.I)
MOE = re.compile(r"ma[iî]trise d.{0,3}uvre", re.I)
EXCL = re.compile(r"assistance|AMO\b|ordonnancement|OPC\b|contr[ôo]le technique|CSPS|diagnostic|g[ée]otechni|"
                  r"voirie|r[ée]seaux|assainissement|eau potable|chauff|ascenseur|d[ée]samiantage|"
                  r"maintenance|entretien|accord-cadre.*travaux", re.I)


def _get(k, r):
    v = r.get(k)
    if isinstance(v, list):
        v = v[0] if v else ""
    return v if v is not None else ""


def fetch():
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out = []
    # varias formulaciones del filtro por si cambia el nombre del campo
    wheres = [f'dateparution >= "{since}" AND (objet LIKE "concours" OR objet LIKE "maîtrise d\'oeuvre" OR objet LIKE "maîtrise d\'œuvre" OR procedure_libelle LIKE "concours")',
              f'dateparution >= "{since}"']
    for where in wheres:
        try:
            recs, offset = [], 0
            while offset < 1000:
                r = requests.get(API, params={"where": where, "limit": 100, "offset": offset,
                                              "order_by": "dateparution desc"}, headers=UA, timeout=60)
                r.raise_for_status()
                page = r.json().get("results", [])
                recs += page
                if len(page) < 100:
                    break
                offset += 100
            break
        except Exception as e:
            print("boamp:", e)
            recs = []
    for r in recs:
        objet = str(_get("objet", r))
        proc = str(_get("procedure_libelle", r) or _get("type_procedure", r))
        desc = str(_get("descripteur_libelle", r))
        texto = " ".join([objet, proc, desc])
        if not (CONCOURS.search(texto) or (MOE.search(objet) and re.search(r"esquisse|concours|jury", texto, re.I))):
            continue
        if EXCL.search(objet) and not CONCOURS.search(texto):
            continue
        idw = str(_get("idweb", r) or _get("id", r))
        dl = str(_get("datelimitereponse", r) or "")[:16].replace("T", " ")
        pub = str(_get("dateparution", r) or "")[:10]
        dep = str(_get("code_departement", r) or "")
        url = str(_get("url_avis", r) or "") or (f"https://www.boamp.fr/pages/avis/?q=idweb:{idw}" if idw else "https://www.boamp.fr")
        acc = "seleccion" if re.search(r"restreint|candidature", texto, re.I) else "abierto" if re.search(r"ouvert", texto, re.I) else ""
        out.append({"num": "BOAMP-" + (idw or objet[:30]), "title": objet[:200], "buyer": str(_get("nomacheteur", r)),
                    "country": "FRA", "pub": pub, "deadline": dl, "place": f"dép. {dep}" if dep else "",
                    "url": url, "source": "BOAMP", "proc": acc, "desc": " · ".join(x for x in [proc, desc] if x)[:400]})
    return out


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
