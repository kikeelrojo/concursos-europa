"""Cada módulo expone fetch() -> lista de dicts con las claves:
num, title, buyer, country, pub, deadline, place, url, source (+ proc, desc opcionales)"""
from . import bouwmeester, boletines
FUENTES = [bouwmeester, boletines]
