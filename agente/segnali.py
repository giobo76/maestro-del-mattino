"""Indicatori di analisi tecnica e "situazione" di un titolo.

La riga t usa solo dati fino alla chiusura del giorno t.
"""
import numpy as np
import pandas as pd

COMPONENTI = ["trend", "rsi", "macd", "vol", "rottura", "giorno"]


def calcola_indicatori(prezzi: pd.DataFrame) -> pd.DataFrame:
    ind = prezzi.copy()
    chiusura = ind["Close"]
    ind["sma20"] = chiusura.rolling(20).mean()
    ind["sma50"] = chiusura.rolling(50).mean()

    variazione = chiusura.diff()
    guadagni = variazione.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    perdite = (-variazione.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    somma = guadagni + perdite
    # prezzi fermi: nessun guadagno né perdita, RSI neutro
    ind["rsi14"] = np.where(somma == 0, 50.0, 100 * guadagni / somma.replace(0, np.nan))
    ind.loc[guadagni.isna(), "rsi14"] = np.nan

    ind["macd"] = chiusura.ewm(span=12, adjust=False).mean() - chiusura.ewm(span=26, adjust=False).mean()
    ind["macd_segnale"] = ind["macd"].ewm(span=9, adjust=False).mean()
    ind["vol_media20"] = ind["Volume"].shift(1).rolling(20).mean()
    ind["max20_prec"] = ind["High"].shift(1).rolling(20).max()
    ind["rend_giorno"] = chiusura.pct_change()
    return ind


def _stato(condizioni: list, valori: list, altrimenti: str, indice) -> pd.Series:
    return pd.Series(np.select(condizioni, valori, default=altrimenti), index=indice)


def calcola_situazione(ind: pd.DataFrame) -> pd.Series:
    c = ind["Close"]
    i = ind.index
    trend = _stato([(c > ind["sma20"]) & (c > ind["sma50"]), (c < ind["sma20"]) & (c < ind["sma50"])],
                   ["su", "giu"], "misto", i)
    rsi = _stato([ind["rsi14"] < 30, ind["rsi14"] > 70], ["basso", "alto"], "normale", i)
    sopra = ind["macd"] > ind["macd_segnale"]
    sopra_ieri = sopra.shift(1, fill_value=False)
    macd = _stato([sopra & ~sopra_ieri, ~sopra & sopra_ieri], ["rialzo", "ribasso"], "nessuno", i)
    vol = _stato([ind["Volume"] > 2 * ind["vol_media20"]], ["alto"], "normale", i)
    rottura = _stato([c > ind["max20_prec"]], ["si"], "no", i)
    giorno = _stato([ind["rend_giorno"] > 0.02, ind["rend_giorno"] < -0.02],
                    ["forte_su", "forte_giu"], "normale", i)

    situazione = ("trend=" + trend + "|rsi=" + rsi + "|macd=" + macd + "|vol=" + vol
                  + "|rottura=" + rottura + "|giorno=" + giorno)
    necessari = ["sma50", "rsi14", "vol_media20", "max20_prec", "rend_giorno"]
    mancanti = ind[necessari].isna().any(axis=1)
    return situazione.where(~mancanti)
