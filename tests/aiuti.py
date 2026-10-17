"""Dati sintetici per i test."""
import numpy as np
import pandas as pd


def crea_prezzi(chiusure, volumi=None, aperture=None, massimi=None, inizio="2024-01-01"):
    chiusure = np.asarray(chiusure, dtype=float)
    n = len(chiusure)
    indice = pd.bdate_range(inizio, periods=n)
    return pd.DataFrame(
        {
            "Open": chiusure if aperture is None else np.asarray(aperture, dtype=float),
            "High": chiusure if massimi is None else np.asarray(massimi, dtype=float),
            "Low": chiusure,
            "Close": chiusure,
            "Volume": np.full(n, 1000.0) if volumi is None else np.asarray(volumi, dtype=float),
        },
        index=indice,
    )


def passeggiata(n, seme=0, inizio="2024-01-01"):
    rng = np.random.default_rng(seme)
    chiusure = 100 * np.cumprod(1 + rng.normal(0, 0.015, n))
    aperture = chiusure * (1 + rng.normal(0, 0.005, n))
    massimi = np.maximum(chiusure, aperture) * 1.005
    volumi = rng.integers(500, 3000, n)
    return crea_prezzi(chiusure, volumi, aperture, massimi, inizio)
