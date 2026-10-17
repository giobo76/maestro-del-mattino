from datetime import date

import pytest

from agente.archivio import aggiungi_previsioni, leggi_previsioni
from agente.dati import DatiNonDisponibili
from agente.scelta import Scelta
from agente.verifica import registra_esiti


def previsioni(*giorni):
    prev = leggi_previsioni("non-esiste.csv")
    for giorno in giorni:
        prev = aggiungi_previsioni(prev, giorno, [Scelta("ITA", "ENI.MI", "Eni", 0.57, 142, 0.004, "s")])
    return prev


def test_registra_esito():
    prev = registra_esiti(previsioni(date(2026, 10, 16)), lambda s, g: {"ENI.MI": (10.0, 10.3)},
                          date(2026, 10, 16))
    riga = prev.iloc[0]
    assert bool(riga["salito"]) is True
    assert riga["rend"] == pytest.approx(0.03)
    assert riga["apertura"] == 10.0 and riga["chiusura"] == 10.3


def test_esito_mancante_resta_in_attesa():
    prev = registra_esiti(previsioni(date(2026, 10, 16)), lambda s, g: {}, date(2026, 10, 16))
    assert prev["salito"].isna().all()
    prev = registra_esiti(prev, lambda s, g: {"ENI.MI": (10.0, 9.9)}, date(2026, 10, 17))
    assert bool(prev.iloc[0]["salito"]) is False


def test_yahoo_rotto_resta_in_attesa():
    def rotto(simboli, giorno):
        raise DatiNonDisponibili("giù")

    prev = registra_esiti(previsioni(date(2026, 10, 16)), rotto, date(2026, 10, 16))
    assert prev["salito"].isna().all()


def test_previsione_futura_non_toccata():
    chiesti = []

    def prezzi(simboli, giorno):
        chiesti.append(giorno)
        return {"ENI.MI": (10.0, 10.3)}

    prev = registra_esiti(previsioni(date(2026, 10, 16), date(2026, 10, 19)), prezzi, date(2026, 10, 16))
    assert chiesti == [date(2026, 10, 16)]
    assert prev["salito"].isna().sum() == 1
