"""Lettura e scrittura dello storico (previsioni.csv) e della pagina del giorno (oggi.json)."""
import dataclasses
import json
from datetime import date
from pathlib import Path

import pandas as pd

from agente.scelta import Scelta

COLONNE = ["data", "mercato", "simbolo", "nome", "prob", "casi", "rend_medio_storico", "situazione",
           "giudizio_notizie", "apertura", "chiusura", "rend", "salito"]
TIPI = {"data": "string", "mercato": "string", "simbolo": "string", "nome": "string",
        "prob": "float64", "casi": "Int64", "rend_medio_storico": "float64", "situazione": "string",
        "giudizio_notizie": "string", "apertura": "float64", "chiusura": "float64",
        "rend": "float64", "salito": "boolean"}


def _vuoto() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=TIPI[c]) for c in COLONNE})


def leggi_previsioni(percorso) -> pd.DataFrame:
    if not Path(percorso).exists():
        return _vuoto()
    return pd.read_csv(percorso, dtype=TIPI)[COLONNE]


def aggiungi_previsioni(prev: pd.DataFrame, giorno: date, scelte: list[Scelta]) -> pd.DataFrame:
    data = giorno.isoformat()
    mercati = {s.mercato for s in scelte}
    restanti = prev[~((prev["data"] == data) & prev["mercato"].isin(mercati))]
    nuove = pd.DataFrame([{
        "data": data, "mercato": s.mercato, "simbolo": s.simbolo, "nome": s.nome, "prob": s.prob,
        "casi": s.casi, "rend_medio_storico": s.rend_medio, "situazione": s.situazione,
        "giudizio_notizie": s.giudizio_notizie,
    } for s in scelte if s.simbolo], columns=COLONNE)
    if nuove.empty:
        return restanti.reset_index(drop=True)
    nuove = nuove.astype(TIPI)
    return pd.concat([restanti, nuove], ignore_index=True).sort_values(["data", "mercato"]).reset_index(drop=True)


def salva_previsioni(prev: pd.DataFrame, percorso) -> None:
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    prev[COLONNE].to_csv(percorso, index=False)


def _serializza(valore):
    if dataclasses.is_dataclass(valore):
        return dataclasses.asdict(valore)
    return str(valore)


def leggi_oggi(percorso) -> dict | None:
    if not Path(percorso).exists():
        return None
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def salva_oggi(percorso, contenuto: dict) -> None:
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    testo = json.dumps(contenuto, ensure_ascii=False, indent=2, default=_serializza)
    Path(percorso).write_text(testo, encoding="utf-8")
