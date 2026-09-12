"""Cada módulo expone fetch() -> lista de dicts con las claves:
num, title, buyer, country, pub, deadline, place, url, source (+ proc, desc, value, cur, docs opcionales)"""
from . import bouwmeester, boletines, konkurado, bma, cellule, polonia, nordicos, italia, portugal, francia, holanda, espana
FUENTES = [bouwmeester, boletines, konkurado, bma, cellule, polonia, nordicos, italia, portugal, francia, holanda, espana]
