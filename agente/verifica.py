"""Controllo serale: com'è andata ogni previsione."""
import logging
from datetime import date
from typing import Callable

import pandas as pd

from agente.dati import DatiNonDisponibili

log = logging.getLogger(__name__)


def registra_esiti(prev: pd.DataFrame,
                   prezzi_giorno: Callable[[list[str], date], dict[str, tuple[float, float]]],
                   oggi: date) -> pd.DataFrame:
    prev = prev.copy()
    in_attesa = prev["salito"].isna() & (prev["data"] <= oggi.isoformat())
    for data, gruppo in prev[in_attesa].groupby("data"):
        try:
            prezzi = prezzi_giorno(list(gruppo["simbolo"]), date.fromisoformat(data))
        except DatiNonDisponibili:
            log.warning("Esiti del %s non disponibili: riprovo domani", data)
            continue
        for indice, simbolo in gruppo["simbolo"].items():
            if simbolo not in prezzi:
                log.warning("Esito di %s del %s non ancora disponibile", simbolo, data)
                continue
            apertura, chiusura = prezzi[simbolo]
            prev.loc[indice, ["apertura", "chiusura", "rend"]] = [apertura, chiusura, chiusura / apertura - 1]
            prev.loc[indice, "salito"] = chiusura > apertura
    return prev
