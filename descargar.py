#!/usr/bin/env python3
"""Descarga la documentación de un concurso de la base a ~/Downloads/concursos-docs/<num>/
y abre la carpeta; si no hay documentos descargables (portal con cuenta, JavaScript…),
abre el enlace de la plataforma en el navegador. Uso: python3 descargar.py <num>"""
import os, re, sys, json, subprocess, urllib.parse, requests
from bs4 import BeautifulSoup

PAGE_JSON = "https://kikeelrojo.github.io/concursos-europa/concursos.json"
LOCAL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "concursos.json")
DEST = os.path.expanduser("~/Downloads/concursos-docs")
UA = {"User-Agent": "Mozilla/5.0 (concursos-arrova)"}
EXT = re.compile(r"\.(pdf|zip|docx?|xlsx?|pptx?|dwg|dxf|ifc|rtf|odt|7z|rar)(\?|$)", re.I)
MAX_FILES, MAX_MB = 60, 400


def base():
    try:
        r = requests.get(PAGE_JSON, headers=UA, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return json.load(open(LOCAL_JSON, encoding="utf-8"))


def abrir(x):
    subprocess.run(["open", x])


def nombre(url, resp):
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    n = urllib.parse.unquote(m.group(1)) if m else os.path.basename(urllib.parse.urlparse(url).path) or "documento"
    return re.sub(r"[^\w.\-() áéíóúñüÁÉÍÓÚÑÜ]", "_", n)[:120]


def bajar(urls, carpeta, referer=None):
    os.makedirs(carpeta, exist_ok=True)
    n, total = 0, 0
    for u in urls[:MAX_FILES]:
        try:
            h = dict(UA)
            if referer:
                h["Referer"] = referer
            r = requests.get(u, headers=h, timeout=120, stream=True, allow_redirects=True)
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "text/html" in ct and not EXT.search(u):
                continue
            fn = nombre(u, r)
            if not EXT.search(fn) and "pdf" in ct:
                fn += ".pdf"
            ruta = os.path.join(carpeta, fn)
            if os.path.exists(ruta):
                ruta = os.path.join(carpeta, f"{n}_{fn}")
            with open(ruta, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    total += len(chunk)
                    if total > MAX_MB << 20:
                        break
            n += 1
        except Exception as e:
            print("no descargado:", u, e)
    return n


def docs_tenderned(pid):
    r = requests.get(f"https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties/{pid}/documenten", headers=UA, timeout=60)
    r.raise_for_status()
    out = []
    for d in r.json().get("documenten", []):
        href = (d.get("links") or {}).get("download", {}).get("href", "")
        if href:
            out.append(href if href.startswith("http") else "https://www.tenderned.nl" + href)
    return out


def docs_pagina(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        h = urllib.parse.urljoin(url, a["href"])
        t = a.get_text(" ", strip=True).lower()
        if EXT.search(h) or re.search(r"download|descarg|télécharg|herunterladen|documenten|pliego|bases|programme|reglement|règlement|unterlagen", h.lower() + " " + t):
            if h not in out and not h.startswith("mailto:"):
                out.append(h)
    return out


def main():
    if len(sys.argv) < 2:
        print("uso: descargar.py <num>")
        return
    num = sys.argv[1].strip()
    item = next((c for c in base() if c.get("num") == num), None)
    if not item:
        print("no encontrado:", num)
        return
    carpeta = os.path.join(DEST, re.sub(r"[^\w\-]", "_", num))
    url = item.get("url", "")
    urls = []
    try:
        if num.startswith("TN-"):
            urls = docs_tenderned(num[3:])
        elif url:
            urls = docs_pagina(url)
    except Exception as e:
        print("error buscando documentos:", e)
    n = bajar(urls, carpeta, referer=url) if urls else 0
    if n:
        with open(os.path.join(carpeta, "_ficha.txt"), "w", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False, indent=1))
        abrir(carpeta)
        # resumen de una página si hay clave de API
        try:
            import resumen
            if resumen.clave():
                texto, _ = resumen.recoger_texto(carpeta)
                if len(texto) >= 500:
                    d = resumen.resumir("FICHA DEL BUSCADOR: " + json.dumps({k: item.get(k) for k in ("title", "buyer", "place", "deadline", "value", "cur", "proc", "desc") if item.get(k)}, ensure_ascii=False) + "\n\n" + texto)
                    json.dump(d, open(os.path.join(carpeta, "_resumen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                    resumen.maquetar(d, os.path.join(carpeta, "resumen.pdf"), item)
                    abrir(os.path.join(carpeta, "resumen.pdf"))
                else:
                    print("sin texto legible para resumir")
        except Exception as e:
            print("resumen no generado:", e)
    else:
        for u in [url] + [a.get("url") for a in item.get("alt", [])]:
            if u:
                abrir(u)
                break


if __name__ == "__main__":
    main()
