"""Squeeze Momentum Oscillator [AlgoAlpha]: cambi di colore (verde/rosso) sui titoli del FTSE MIB.

Formula tradotta dal codice Pine pubblico di AlgoAlpha (Mozilla Public License 2.0):
https://www.tradingview.com/script/WDsx1YV1-Squeeze-Momentum-Oscillator-AlgoAlpha/
Impostazioni predefinite (10 / 20). Colore = segno di `vf` ("Underlying Momentum"): verde > 0, rosso < 0.
Verificata il 2026-11-09 su ENI contro il grafico TradingView (scarto di pochi decimi).
Solo osservazione: non è una strategia testata.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LEN = 10


def _ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, ignore_na=True).mean().where(x.notna().cummax())


def _wma(x: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1)
    return x.rolling(n).apply(lambda v: np.dot(v, w) / w.sum(), raw=True)


def _hma(x: pd.Series, n: int) -> pd.Series:
    return _wma(2 * _wma(x, n // 2) - _wma(x, n), int(np.floor(np.sqrt(n))))


def momentum(prezzi: pd.DataFrame) -> pd.Series:
    """Serie `vf` dell'indicatore (High, Low, Close giornalieri)."""
    h, l, c = prezzi["High"], prezzi["Low"], prezzi["Close"]
    basso = _ema(l.rolling(LEN).min(), LEN)
    alto = _ema(h.rolling(LEN).max(), LEN)
    d, val = 0, []
    cp = hp = lp = np.nan
    for ci, hi, lo in zip(c.values, alto.values, basso.values):
        if not np.isnan(hp) and ci > hi and cp <= hp:
            d = 1
        if not np.isnan(lp) and ci < lo and cp >= lp:
            d = -1
        val.append(lo if d == 1 else hi)
        cp, hp, lp = ci, hi, lo
    distanza = c - pd.Series(val, index=c.index)
    return _hma(distanza, LEN) / _ema(h - l, LEN * 2) * 100 / 8


def _giorni_stesso_colore(vf: pd.Series) -> int:
    segni = np.sign(vf.values)
    n = 1
    while n < len(segni) and segni[-n - 1] == segni[-1]:
        n += 1
    return n


def riepilogo(prezzi: dict[str, pd.DataFrame], nomi: dict[str, str]) -> dict:
    """Cambi di colore all'ultima chiusura disponibile di ogni titolo."""
    rossi, verdi, tutti_rossi, data = [], [], [], None
    for simbolo, df in prezzi.items():
        vf = momentum(df).dropna()
        if len(vf) < 2:
            continue
        oggi, ieri = float(vf.iloc[-1]), float(vf.iloc[-2])
        voce = {"simbolo": simbolo, "nome": nomi.get(simbolo, simbolo), "momentum": round(oggi, 1),
                "ieri": round(ieri, 1), "chiusura": float(df["Close"].iloc[-1]), "giorni": _giorni_stesso_colore(vf)}
        data = max(data, vf.index[-1].date().isoformat()) if data else vf.index[-1].date().isoformat()
        if oggi < 0 <= ieri:
            rossi.append(voce)
        elif oggi > 0 >= ieri:
            verdi.append(voce)
        if oggi < 0:
            tutti_rossi.append(voce)
    return {"data": data, "verso_rosso": sorted(rossi, key=lambda v: v["momentum"]),
            "verso_verde": sorted(verdi, key=lambda v: -v["momentum"]),
            "rossi": sorted(tutti_rossi, key=lambda v: v["momentum"]), "titoli": len(prezzi)}
