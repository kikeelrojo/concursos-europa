"""Cada módulo expone fetch() -> lista de dicts con las claves:
num, title, buyer, country, pub, deadline, place, url, source (+ proc, desc, value, cur opcionales)"""
from . import bouwmeester, boletines, konkurado, bma, cellule, polonia, nordicos
FUENTES = [bouwmeester, boletines, konkurado, bma, cellule, polonia, nordicos]
