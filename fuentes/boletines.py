"""Lee boletines por correo (IMAP de Google) y saca concursos.
Un analizador por remitente; añadir nuevos en PARSERS."""
import os, re, imaplib, email, email.policy, datetime as dt
from bs4 import BeautifulSoup

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
DAYS_BACK = int(os.getenv("DAYS_BACK", "7")) + 1


def _abierto(texto):
    t = texto.lower()
    if re.search(r"geladen|nicht ?offen|beschränkt|begrenzt|einladung", t):
        return "seleccion"
    if "offen" in t:
        return "abierto"
    return ""


def parse_architekturwettbewerb(msg, html):
    """Newsfeed de www.architekturwettbewerb.at (Kammer, Austria)."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    h2 = soup.find(lambda t: t.name == "h2" and "Ausschreibung" in t.get_text())
    if not h2:
        return out
    for p in h2.find_all_next("p"):
        a = p.find("a", href=True)
        if not a or "/competition/" not in a["href"]:
            continue
        lines = [l.strip() for l in p.get_text("\n").split("\n") if l.strip()]
        title = a.get_text(strip=True)
        rest = [l for l in lines if l != title]
        tipo = rest[0] if rest else ""
        region = rest[1] if len(rest) > 1 else ""
        m = re.search(r"/(\d+)/?$", a["href"])
        num = "AW-" + (m.group(1) if m else re.sub(r"\W", "", title)[:30])
        out.append({"num": num, "title": f"{title} ({tipo})" if tipo else title,
                    "buyer": "", "country": "AUT", "pub": _fecha(msg), "deadline": "",
                    "place": region, "url": a["href"], "source": "architekturwettbewerb.at",
                    "proc": _abierto(tipo), "desc": " · ".join(rest[2:])})
    return out


PARSERS = {
    "noreply@architekturwettbewerb.at": parse_architekturwettbewerb,
}


def _fecha(msg):
    try:
        return email.utils.parsedate_to_datetime(msg["Date"]).date().isoformat()
    except Exception:
        return ""


def _html(msg):
    body = msg.get_body(preferencelist=("html", "plain"))
    return body.get_content() if body else ""


def fetch():
    user, pw = os.getenv("IMAP_USER"), os.getenv("IMAP_PASS")
    if not user or not pw:
        print("boletines: IMAP_USER/IMAP_PASS no definidos, se omite")
        return []
    since = (dt.date.today() - dt.timedelta(days=DAYS_BACK)).strftime("%d-%b-%Y")
    out = []
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST)
        M.login(user, pw)
        M.select('"[Gmail]/All Mail"' if IMAP_HOST == "imap.gmail.com" else "INBOX", readonly=True)
        for sender, parser in PARSERS.items():
            typ, data = M.search(None, f'(SINCE {since} FROM "{sender}")')
            ids = data[0].split() if typ == "OK" else []
            for i in ids:
                typ, d = M.fetch(i, "(RFC822)")
                if typ != "OK":
                    continue
                msg = email.message_from_bytes(d[0][1], policy=email.policy.default)
                try:
                    out += parser(msg, _html(msg))
                except Exception as e:
                    print("boletines:", sender, e)
            print(f"boletines: {sender}: {len(ids)} mensajes")
        M.logout()
    except Exception as e:
        print("boletines: error IMAP", e)
    # sin duplicados dentro de la semana
    vistos, res = set(), []
    for c in out:
        if c["num"] not in vistos:
            vistos.add(c["num"]); res.append(c)
    return res


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1:   # prueba local con un .eml
        msg = email.message_from_binary_file(open(sys.argv[1], "rb"), policy=email.policy.default)
        sender = email.utils.parseaddr(msg["From"])[1]
        print(json.dumps(PARSERS[sender](msg, _html(msg)), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(fetch(), ensure_ascii=False, indent=1))
