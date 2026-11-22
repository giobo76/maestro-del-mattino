"""Portafoglio Investimenti Lab (Trading-Lab S020, esperimento E060) — SOLO DEMO.

25% Bitcoin e 25% Ethereum con le medie a scalini (S018): esposizione = condizioni vere su 6
(chiusura > SMA20, > SMA50, > SMA100; SMA20 > SMA50, SMA20 > SMA100, SMA50 > SMA100) sull'ultima candela giornaliera CHIUSA.
50% Nasdaq-100 2x (ETP, es. Amundi LQQ) con il filtro mensile S011: a fine mese indice > media 10 mesi +3% → dentro,
< media −3% → fuori, in mezzo invariato. Il primo giorno del mese si riportano le parti a 25/25/50.
L'agente confronta con l'ultimo stato comunicato (dati/portafoglio.json): i cambi del weekend arrivano il lunedì.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd

QUOTE = {"BTC": 0.25, "ETH": 0.25, "NDX": 0.50}


def esposizione(chiusure: pd.Series) -> int:
    """Condizioni vere su 6 all'ultima chiusura (0 se mancano 100 giorni di storia)."""
    c = chiusure.dropna()
    if len(c) < 100:
        return 0
    m1, m2, m3 = (float(c.rolling(n).mean().iloc[-1]) for n in (20, 50, 100))
    x = float(c.iloc[-1])
    return int(sum([x > m1, x > m2, x > m3, m1 > m2, m1 > m3, m2 > m3]))


def stato_nasdaq(chiusure: pd.Series, oggi: date) -> dict:
    """Stato S011 alla fine dell'ultimo mese completo prima di `oggi` (regola identica a Trading-Lab S008/S011)."""
    c = chiusure.dropna()
    mensili = c.groupby(c.index.to_period("M")).last()
    mensili = mensili[mensili.index < pd.Period(oggi, "M")]
    media = mensili.rolling(10, min_periods=10).mean()
    stato = None
    for p in media.dropna().index:
        x, m = mensili[p], media[p]
        if stato is None:
            stato = 1 if x > m else 0
        elif stato == 0 and x > m * 1.03:
            stato = 1
        elif stato == 1 and x < m * 0.97:
            stato = 0
    if stato is None:
        return {"stato": 0, "soglia": None, "ultimo": float(c.iloc[-1]) if len(c) else None}
    # soglia STIMATA per la fine del mese in corso: media delle ultime 9 chiusure mensili + l'ultimo prezzo
    media_viva = (mensili.iloc[-9:].sum() + float(c.iloc[-1])) / 10
    soglia = media_viva * (0.97 if stato == 1 else 1.03)
    return {"stato": int(stato), "soglia": float(soglia), "ultimo": float(c.iloc[-1])}


def _chiuse(serie: pd.Series, oggi: date) -> pd.Series:
    """Solo candele giornaliere chiuse: la candela di oggi (ancora in corso) viene esclusa."""
    s = serie.dropna()
    return s[[d.date() < oggi for d in s.index]]


def calcola(btc: pd.Series, eth: pd.Series, ndx: pd.Series, oggi: date, capitale: float,
            precedente: dict | None) -> dict:
    """Situazione del portafoglio e azioni rispetto all'ultimo stato comunicato."""
    btc, eth = _chiuse(btc, oggi), _chiuse(eth, oggi)
    k = {"BTC": esposizione(btc), "ETH": esposizione(eth)}
    prezzi = {"BTC": float(btc.iloc[-1]), "ETH": float(eth.iloc[-1])}
    nas = stato_nasdaq(ndx, oggi)
    prec = precedente or {}
    righe, azioni = [], []
    for sigla, nome in (("BTC", "Bitcoin"), ("ETH", "Ethereum")):
        valore = capitale * QUOTE[sigla] * k[sigla] / 6
        quantita = math.floor(valore / prezzi[sigla] * 10000) / 10000
        righe.append({"nome": nome, "sigla": sigla, "k": k[sigla], "valore": valore, "quantita": quantita,
                      "prezzo": prezzi[sigla]})
        kp = prec.get(sigla)
        if kp is not None and kp != k[sigla]:
            delta = capitale * QUOTE[sigla] * (k[sigla] - kp) / 6
            q = math.floor(abs(delta) / prezzi[sigla] * 10000) / 10000
            azioni.append(f"{nome}: da {kp}/6 a {k[sigla]}/6 → {'COMPRA' if delta > 0 else 'VENDI'} "
                          f"{q:g} {sigla} (circa {abs(delta):,.0f} €)".replace(",", "."))
    sp = prec.get("NDX")
    if sp is not None and sp != nas["stato"]:
        azioni.append("Nasdaq 2x: " + (f"COMPRA l'ETP 2x (es. LQQ) per circa {capitale * QUOTE['NDX']:,.0f} €".replace(",", ".")
                                       if nas["stato"] == 1 else "VENDI tutto l'ETP 2x e resta in liquidità")
                      + " (segnale di fine mese)")
    mese = oggi.strftime("%Y-%m")
    ribilancia = prec.get("mese_ribilanciato") not in (None, mese)
    if ribilancia:
        azioni.append("Inizio mese: riporta le parti a 25% Bitcoin / 25% Ethereum / 50% Nasdaq 2x del valore totale")
    investito = sum(r["valore"] for r in righe) + capitale * QUOTE["NDX"] * nas["stato"]
    return {"data": oggi.isoformat(), "capitale": capitale, "righe": righe, "nasdaq": nas, "azioni": azioni,
            "prima_volta": precedente is None, "investito": investito,
            "stato": {"BTC": k["BTC"], "ETH": k["ETH"], "NDX": nas["stato"], "mese_ribilanciato": mese,
                      "data": oggi.isoformat()}}
