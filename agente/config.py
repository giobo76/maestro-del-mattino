"""Lettura delle impostazioni da config.yaml."""
import os
from dataclasses import dataclass

import yaml


@dataclass
class Mercato:
    codice: str
    nome: str
    calendario: str
    indice: str
    valuta: str
    lingua_notizie: str
    titoli: dict[str, str]


@dataclass
class Config:
    mercati: dict[str, Mercato]
    soglia_r: float
    atr_mult: float
    email_destinatario: str
    modalita_studio: bool
    casi_minimi: int
    casi_virtuali: int
    anni_storico: int
    gemini_modello: str
    costi: dict
    conto_simulato_eur: float
    ibkr_capitale_eur: float
    ibkr_mercati: list[str]


def carica_config(percorso: str = "config.yaml") -> Config:
    with open(percorso, encoding="utf-8") as f:
        dati = yaml.safe_load(f)
    mercati = {
        codice: Mercato(codice=codice, **valori)
        for codice, valori in dati.pop("mercati").items()
    }
    # l'indirizzo sta nel Secret EMAIL_DESTINATARIO, non nel repo pubblico
    dati["email_destinatario"] = os.environ.get("EMAIL_DESTINATARIO", "")
    return Config(mercati=mercati, **dati)
