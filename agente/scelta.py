"""Scelta del titolo del giorno per un mercato."""
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from agente.config import Mercato
from agente.dati import Notizia
from agente.probabilita import cerca
from agente.segnali import calcola_indicatori, calcola_situazione


@dataclass
class Scelta:
    mercato: str
    simbolo: str | None = None
    nome: str | None = None
    prob: float | None = None
    casi: int | None = None
    rend_medio: float | None = None
    situazione: str | None = None
    giudizio_notizie: str | None = None
    notizie: list[Notizia] = field(default_factory=list)
    scartati: list[str] = field(default_factory=list)
    nota: str = ""


def scegli(mercato: Mercato, prezzi: dict[str, pd.DataFrame], tabella: pd.DataFrame,
           trova_notizie: Callable[[str, str], list[Notizia]],
           giudica: Callable[[str, list[Notizia]], str | None],
           soglia: float, max_candidati: int = 5) -> Scelta:
    candidati = []
    for simbolo, df in prezzi.items():
        situazione = calcola_situazione(calcola_indicatori(df)).iloc[-1]
        if pd.isna(situazione):
            continue
        trovato = cerca(tabella, situazione)
        if trovato and trovato["prob"] >= soglia:
            candidati.append((simbolo, situazione, trovato))
    candidati.sort(key=lambda c: c[2]["prob"], reverse=True)

    scelta = Scelta(mercato=mercato.codice)
    if not candidati:
        scelta.nota = (f"Oggi nessun titolo supera il {soglia * 100:.0f}% di probabilità storica: "
                       "meglio stare fermi.")
        return scelta

    for simbolo, situazione, trovato in candidati[:max_candidati]:
        nome = mercato.titoli.get(simbolo, simbolo)
        notizie = trova_notizie(nome, simbolo)
        giudizio = giudica(nome, notizie)
        if giudizio == "negativo":
            scelta.scartati.append(simbolo)
            continue
        scelta.simbolo, scelta.nome, scelta.situazione = simbolo, nome, situazione
        scelta.prob, scelta.casi, scelta.rend_medio = trovato["prob"], trovato["casi"], trovato["rend_medio"]
        scelta.giudizio_notizie, scelta.notizie = giudizio, notizie
        if giudizio is None:
            scelta.nota = "Filtro notizie non disponibile oggi."
        return scelta

    scelta.nota = ("Oggi i titoli migliori avevano notizie negative e sono stati scartati: "
                   "meglio stare fermi.")
    return scelta
