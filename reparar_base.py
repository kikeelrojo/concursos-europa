#!/usr/bin/env python3
"""Repara docs/concursos.json si quedó roto por una fusión de git:
1) quita marcas de conflicto y prueba; 2) si no, recupera del historial la
versión válida más reciente. Uso: python3 reparar_base.py"""
import json, re, subprocess, sys

BASE = "docs/concursos.json"


def valido(txt):
    try:
        d = json.loads(txt)
        return isinstance(d, list) and len(d) > 0
    except Exception:
        return False


txt = open(BASE, encoding="utf-8").read()
if valido(txt):
    print("la base es válida:", len(json.loads(txt)), "registros")
    sys.exit(0)
limpio = "\n".join(l for l in txt.split("\n") if not re.match(r"^(<<<<<<<|=======|>>>>>>>)", l))
if valido(limpio):
    open(BASE, "w", encoding="utf-8").write(limpio)
    print("reparada quitando marcas de conflicto:", len(json.loads(limpio)), "registros")
    sys.exit(0)
commits = subprocess.run(["git", "log", "--format=%H", "-n", "40", "--", BASE], capture_output=True, text=True).stdout.split()
for h in commits:
    t = subprocess.run(["git", "show", f"{h}:{BASE}"], capture_output=True, text=True).stdout
    if valido(t):
        open(BASE, "w", encoding="utf-8").write(t)
        print("recuperada de", h[:8], ":", len(json.loads(t)), "registros")
        sys.exit(0)
print("no se ha encontrado ninguna versión válida; el próximo workflow la reconstruye desde cero")
