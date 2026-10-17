"""Scelta dell'operazione del giorno per un mercato: la situazione con la resa storica più alta in R."""
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from agente.config import Mercato
from agente.dati import Notizia
from agente.operazione import Livelli, calcola_livelli
from agente.segnali import calcola_indicatori, calcola_situazione
from agente.storico_r import cerca


@dataclass
class Scelta:
    mercato: str
    simbolo: str | None = None
    nome: str | None = None
    resa: float | None = None
    casi: int | None = None
    pct_stop: float | None = None
    pct_2r: float | None = None
    situazione: str | None = None
    livelli: Livelli | None = None
    giudizio_notizie: str | None = None
    notizie: list[Notizia] = field(default_factory=list)
    scartati: list[str] = field(default_factory=list)
    sotto_soglia: bool = False
    nota: str = ""


def _r_it(valore: float) -> str:
    return f"{valore:+.2f}R".replace(".", ",")


def scegli(mercato: Mercato, prezzi: dict[str, pd.DataFrame], tabella: pd.DataFrame,
           trova_notizie: Callable[[str, str], list[Notizia]],
           giudica: Callable[[str, list[Notizia]], str | None],
           soglia: float, atr_mult: float, max_candidati: int = 5, studio: bool = False) -> Scelta:
    candidati = []
    for simbolo, df in prezzi.items():
        situazione = calcola_situazione(calcola_indicatori(df)).iloc[-1]
        if pd.isna(situazione):
            continue
        trovato = cerca(tabella, situazione)
        if not trovato or not (studio or trovato["resa"] >= soglia):
            continue
        livelli = calcola_livelli(df, atr_mult)
        if livelli is not None:
            candidati.append((simbolo, situazione, trovato, livelli))
    candidati.sort(key=lambda c: c[2]["resa"], reverse=True)

    scelta = Scelta(mercato=mercato.codice)
    if not candidati:
        scelta.nota = f"Oggi nessun titolo ha una resa storica di almeno {_r_it(soglia)}: meglio stare fermi."
        return scelta

    for simbolo, situazione, trovato, livelli in candidati[:max_candidati]:
        nome = mercato.titoli.get(simbolo, simbolo)
        notizie = trova_notizie(nome, simbolo)
        giudizio = giudica(nome, notizie)
        if giudizio == "negativo":
            scelta.scartati.append(simbolo)
            continue
        scelta.simbolo, scelta.nome, scelta.situazione, scelta.livelli = simbolo, nome, situazione, livelli
        scelta.resa, scelta.casi = trovato["resa"], trovato["casi"]
        scelta.pct_stop, scelta.pct_2r = trovato["pct_stop"], trovato["pct_2r"]
        scelta.giudizio_notizie, scelta.notizie = giudizio, notizie
        scelta.sotto_soglia = trovato["resa"] < soglia
        note = []
        if scelta.sotto_soglia:
            note.append("Sotto soglia: solo per studio, non per investire.")
        if giudizio is None:
            note.append("Filtro notizie non disponibile oggi.")
        scelta.nota = " ".join(note)
        return scelta

    scelta.nota = ("Oggi i titoli migliori avevano notizie negative e sono stati scartati: "
                   "meglio stare fermi.")
    return scelta
