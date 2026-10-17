import numpy as np
import pytest

from agente.operazione import Livelli, Operazione, avanza, calcola_livelli, rendimento, risultato_r
from tests.aiuti import crea_prezzi


def operazione():
    return Operazione(id="2026-10-19-ITA", mercato="ITA", simbolo="CPR.MI", nome="Campari",
                      data_segnale="2026-10-19", riferimento=100.0, r=4.0, stop_iniziale=96.0,
                      pareggio=104.0, prima_uscita=108.0, sotto_soglia=False, resa_attesa=0.25, casi=140)


def giorno(op, data, o, h, l, c, sma20=0.0):
    return avanza(op, data, o, h, l, c, sma20)


def test_calcola_livelli():
    chiusure = np.full(30, 100.0)
    prezzi = crea_prezzi(chiusure, massimi=chiusure + 1)
    prezzi["Low"] = chiusure - 1
    assert calcola_livelli(prezzi, 2.0) == Livelli(100.0, pytest.approx(4.0), pytest.approx(96.0),
                                                   pytest.approx(104.0), pytest.approx(108.0))


def test_atr_nullo_niente_livelli():
    assert calcola_livelli(crea_prezzi(np.full(30, 100.0)), 2.0) is None


def test_ingresso_e_stop():
    op = operazione()
    assert giorno(op, "d1", 100, 101, 95, 96) == ["ingresso", "stop"]
    assert op.stato == "chiusa" and op.prezzo_uscita == 96
    assert risultato_r(op) == pytest.approx(-1)
    assert rendimento(op) == pytest.approx(-0.04)


def test_apertura_sotto_stop():
    op = operazione()
    assert giorno(op, "d1", 94, 95, 93, 94) == ["ingresso", "apertura_sotto_stop"]
    assert risultato_r(op) == pytest.approx(0)  # compra e rivende subito a 94


def test_stop_prima_degli_obiettivi():
    op = operazione()
    eventi = giorno(op, "d1", 100, 109, 95, 107)
    assert "prima_uscita" not in eventi and op.prezzo_uscita == 96


def test_pareggio_dal_giorno_dopo():
    op = operazione()
    assert giorno(op, "d1", 100, 105, 99, 104) == ["ingresso", "pareggio"]
    assert op.stop == 100
    assert giorno(op, "d2", 103, 103, 99.5, 100) == ["pareggio_stop"]
    assert op.prezzo_uscita == 100 and risultato_r(op) == pytest.approx(0)


def test_percorso_completo():
    op = operazione()
    giorno(op, "d1", 100, 105, 99, 104)
    assert giorno(op, "d2", 104, 109, 103, 108, 101) == ["prima_uscita"]
    assert op.prezzo_meta == 108 and op.stato == "meta chiusa"
    assert giorno(op, "d3", 110, 115, 109, 114, 103) == []
    assert giorno(op, "d4", 113, 113, 105, 106, 107) == ["sotto_media"]
    assert op.stato == "uscita domani"
    assert giorno(op, "d5", 105, 106, 104, 105, 107) == ["uscita_finale"]
    assert op.data_uscita == "d5" and op.ultimo_giorno == "d5"
    assert risultato_r(op) == pytest.approx((2 + 1.25) / 2)
    assert rendimento(op) == pytest.approx((0.08 + 0.05) / 2)


def test_apertura_sopra_2r():
    op = operazione()
    giorno(op, "d1", 100, 101, 99, 100)
    assert giorno(op, "d2", 110, 111, 109, 110, 100) == ["prima_uscita", "pareggio"]
    assert op.prezzo_meta == 110


def test_chiusa_non_cambia():
    op = operazione()
    giorno(op, "d1", 100, 101, 95, 96)
    assert giorno(op, "d2", 100, 120, 90, 110) == []
    assert risultato_r(op) == pytest.approx(-1)


def test_non_chiusa_senza_risultato():
    op = operazione()
    giorno(op, "d1", 100, 101, 99, 100)
    assert risultato_r(op) is None and rendimento(op) is None
