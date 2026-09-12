"""España · Plataforma de Contratación del Sector Público (datos abiertos, Atom/CODICE).
Dos sindicaciones: perfiles alojados en PLACSP (643) y plataformas autonómicas
agregadas (Euskadi, Navarra, Cataluña…). Conserva servicios de arquitectura y
urbanismo (CPV 712/714 o palabras clave) y concursos de proyectos; guarda los
enlaces a los pliegos para la descarga directa."""
import os, re, datetime as dt, requests
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
FEEDS = [("PLACE", "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"),
         ("PLACE (CCAA)", "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1044/PlataformasAgregadasSinMenores.atom")]
MAX_PAGES = 60
ARCH = re.compile(r"arquitect|redacci[oó]n (del |de )?(ante)?proyecto|proyecto b[aá]sico|direcci[oó]n (facultativa|de (las )?obras?)|urbanis|"
                  r"plan (general|especial|parcial|b[aá]sico)|ordenaci[oó]n|paisaj|rehabilitaci[oó]n|edificio|edificaci|"
                  r"redacci[oó] (del |de )?projecte|arquitectura", re.I)
CONCURSO = re.compile(r"concurso (p[úu]blico |restringido |abierto |internacional )?de (proyectos|ideas|anteproyectos|arquitectura)|concurs de projectes|concurso de proxectos", re.I)
EXCL = re.compile(r"suministro|limpieza|mantenimiento|seguridad y salud$|CSS\b|obras? de (reforma|construcci|urbanizaci|mejora)|ejecuci[oó]n de (las )?obras|"
                  r"ingenier[ií]a de caminos|instalaciones (el[eé]ctricas|t[eé]rmicas)|inventario|topogr|geot[eé]cn|auditor|desamiant|asistencia t[eé]cnica a la direcci[oó]n", re.I)
PROC = {"1": "Abierto", "2": "Restringido", "3": "Negociado sin publicidad", "4": "Negociado con publicidad", "5": "Diálogo competitivo",
        "6": "Contrato menor", "7": "Derivado de acuerdo marco", "8": "Concurso de proyectos", "9": "Abierto simplificado",
        "10": "Asociación para la innovación", "11": "Diálogo competitivo", "12": "Basado en acuerdo marco", "13": "Abierto simplificado abreviado"}
TIPO = {"1": "Suministros", "2": "Servicios", "3": "Obras", "21": "Gestión de servicios públicos", "31": "Concesión de obras", "32": "Concesión de servicios"}


def _t(el, path):
    """Texto del primer descendiente cuyo nombre local coincide con la ruta (sin namespaces)."""
    partes = path.split("/")
    cur = [el]
    for p in partes:
        nxt = []
        for c in cur:
            for ch in c:
                if ch.tag.split("}")[-1] == p:
                    nxt.append(ch)
        cur = nxt
        if not cur:
            return ""
    return (cur[0].text or "").strip()


def _all(el, name):
    return [x for x in el.iter() if x.tag.split("}")[-1] == name]


def _entry(e, fuente):
    link = next((l.get("href") for l in _all(e, "link") if l.get("href")), "")
    updated = _t(e, "updated")[:10]
    cfs = next((x for x in _all(e, "ContractFolderStatus")), None)
    if cfs is None:
        return None
    status = _t(cfs, "ContractFolderStatusCode")
    if status not in ("PUB", "EV", "PRE") and status:
        return None                     # adjudicadas, resueltas, anuladas
    pp = next((x for x in _all(cfs, "ProcurementProject")), None)
    if pp is None:
        return None
    name = _t(pp, "Name")
    tipo = TIPO.get(_t(pp, "TypeCode"), _t(pp, "TypeCode"))
    cpvs = [c.text.strip() for c in _all(pp, "ItemClassificationCode") if c.text]
    es_arch = any(c.startswith(("712", "714", "7122", "7124", "7125")) for c in cpvs) or bool(ARCH.search(name))
    if not es_arch or (EXCL.search(name) and not CONCURSO.search(name)):
        return None
    if tipo == "Obras" and not CONCURSO.search(name):
        return None
    proc_code = ""
    tp = next((x for x in _all(cfs, "TenderingProcess")), None)
    if tp is not None:
        proc_code = _t(tp, "ProcedureCode")
    proc = PROC.get(proc_code, proc_code)
    if proc_code == "6":
        return None                     # menores fuera
    buyer = ""
    lcp = next((x for x in _all(cfs, "LocatedContractingParty")), None)
    if lcp is not None:
        buyer = _t(lcp, "Party/PartyName/Name") or next((n.text for n in _all(lcp, "Name") if n.text), "")
    valor = _t(pp, "BudgetAmount/TaxExclusiveAmount") or _t(pp, "BudgetAmount/EstimatedOverallContractAmount")
    lugar = ""
    rl = next((x for x in _all(pp, "RealizedLocation")), None)
    if rl is not None:
        lugar = _t(rl, "CountrySubentity") or _t(rl, "Address/CityName")
    dl = ""
    if tp is not None:
        d, h = _t(tp, "TenderSubmissionDeadlinePeriod/EndDate"), _t(tp, "TenderSubmissionDeadlinePeriod/EndTime")
        dl = (d + (" " + h[:5] if h else "")).strip()
    if dl and dl[:10] < dt.date.today().isoformat():
        return None                     # plazo vencido (actualización posterior)
    docs = []
    for ref in ("LegalDocumentReference", "TechnicalDocumentReference", "AdditionalDocumentReference"):
        for r in _all(cfs, ref):
            u = _t(r, "Attachment/ExternalReference/URI") or next((x.text for x in _all(r, "URI") if x.text), "")
            if u and u not in docs:
                docs.append(u)
    cid = _t(cfs, "ContractFolderID")
    es_concurso = proc_code == "8" or bool(CONCURSO.search(name))
    acc = "abierto" if proc_code in ("1", "9", "13") or (es_concurso and proc_code != "2") else "seleccion" if proc_code in ("2", "4", "5", "11") else ""
    return {"num": f"PLACE-{cid}" if cid else "PLACE-" + re.sub(r"\W", "", name)[:30], "title": name[:220], "buyer": buyer,
            "country": "ESP", "pub": updated, "deadline": dl, "place": lugar, "url": link, "source": fuente,
            "proc": acc, "kind": "concurso" if es_concurso else "licitación", "value": valor.split(".")[0] if valor else "",
            "cur": "EUR" if valor else "", "docs": docs,
            "desc": " · ".join(x for x in [proc, tipo, ("CPV " + ", ".join(cpvs[:4])) if cpvs else ""] if x)}


def _feed(fuente, url):
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).isoformat()
    out, vistos = {}, set()
    for _ in range(MAX_PAGES):
        try:
            r = requests.get(url, headers=UA, timeout=120)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except Exception as e:
            print(fuente, ":", e)
            break
        entries = _all(root, "entry")
        old = False
        for e in entries:
            upd = _t(e, "updated")[:10]
            if upd and upd < since:
                old = True
                continue
            it = _entry(e, fuente)
            if it and it["num"] not in vistos:
                vistos.add(it["num"])
                out.setdefault(it["num"], it)
        nxt = next((l.get("href") for l in _all(root, "link") if l.get("rel") == "next"), "")
        if old or not nxt or not entries:
            break
        url = nxt
    return list(out.values())


def fetch():
    res = []
    for fuente, url in FEEDS:
        res += _feed(fuente, url)
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=1))
