"""Controllo serale: com'è andata ogni previsione."""
import logging
from datetime import date
from typing import Callable

import pandas as pd

from agente.dati import DatiNonDisponibili

log = logging.getLogger(__name__)


def registra_esiti(prev: pd.DataFrame,
                   prezzi_giorno: Callable[[list[str], date], dict[str, tuple[float, float]]],
                   oggi: date, chiusa: Callable[[str, date], bool] = lambda mercato, giorno: True,
                   ) -> pd.DataFrame:
    """chiusa(mercato, giorno): vero se la seduta è finita; altrimenti la previsione resta in attesa."""
    prev = prev.copy()
    in_attesa = prev["salito"].isna() & (prev["data"] <= oggi.isoformat())
    for data, gruppo in prev[in_attesa].groupby("data"):
        gruppo = gruppo[[chiusa(m, date.fromisoformat(data)) for m in gruppo["mercato"]]]
        if gruppo.empty:
            continue
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
