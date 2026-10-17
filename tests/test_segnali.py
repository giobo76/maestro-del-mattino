import numpy as np
import pandas as pd

from agente.segnali import calcola_indicatori, calcola_situazione
from tests.aiuti import crea_prezzi, passeggiata


def ultima_situazione(prezzi):
    return calcola_situazione(calcola_indicatori(prezzi)).iloc[-1]


def test_rsi_valori_noti():
    salita = crea_prezzi(np.arange(1, 16))
    assert calcola_indicatori(salita)["rsi14"].iloc[-1] == 100
    alternata = crea_prezzi(100 + np.array([0, 1] * 30))
    assert 45 <= calcola_indicatori(alternata)["rsi14"].iloc[-1] <= 55


def test_trend_su():
    assert "trend=su" in ultima_situazione(crea_prezzi(np.linspace(100, 160, 60)))


def test_volume_alto():
    volumi = np.full(60, 1000.0)
    volumi[-1] = 2500
    assert "vol=alto" in ultima_situazione(crea_prezzi(np.full(60, 10.0), volumi))
    volumi[-1] = 1900
    assert "vol=normale" in ultima_situazione(crea_prezzi(np.full(60, 10.0), volumi))


def test_rottura():
    chiusure = np.full(60, 10.0)
    chiusure[-1] = 10.5
    assert "rottura=si" in ultima_situazione(crea_prezzi(chiusure, massimi=np.full(60, 10.0)))


def test_giorno_forte_giu():
    chiusure = np.full(60, 10.0)
    chiusure[-1] = 9.7
    assert "giorno=forte_giu" in ultima_situazione(crea_prezzi(chiusure))


def test_situazione_nan_inizio():
    situazioni = calcola_situazione(calcola_indicatori(passeggiata(60)))
    assert situazioni.iloc[:49].isna().all()
    assert situazioni.iloc[49:].notna().all()


def test_nessuna_sbirciata():
    prezzi = passeggiata(150, seme=3)
    intera = calcola_situazione(calcola_indicatori(prezzi))
    for k in (60, 99, 140):
        parziale = calcola_situazione(calcola_indicatori(prezzi.iloc[: k + 1]))
        assert parziale.iloc[-1] == intera.iloc[k]
