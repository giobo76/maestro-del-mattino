from datetime import date

import pandas as pd
import pytest

from agente.archivio import aggiungi_previsioni, leggi_previsioni
from agente.config import carica_config
from agente.scelta import Scelta
from agente.statistiche import calcola_statistiche, costo_andata_ritorno, simula_conto
from agente.verifica import registra_esiti

COSTI = carica_config("config.yaml").costi
ZERO = {k: 0 for k in COSTI}


def prev_con_esiti(esiti, mercato="ITA", prob=0.57, situazione="trend=su|rsi=normale"):
    """esiti: lista di (giorno, apertura, chiusura)."""
    prev = leggi_previsioni("non-esiste.csv")
    for giorno, _, _ in esiti:
        prev = aggiungi_previsioni(prev, giorno, [Scelta(mercato, "X", "X", prob, 100, 0.0, situazione)])
    for giorno, apertura, chiusura in esiti:
        prev = registra_esiti(prev, lambda s, g, a=apertura, c=chiusura, d=giorno: {"X": (a, c)} if g == d else {},
                              giorno)
    return prev


def test_costo_ita_minimo():
    assert costo_andata_ritorno("ITA", 100, 25, COSTI, 1.1) == pytest.approx(2.50)


def test_costo_ita_percentuale():
    assert costo_andata_ritorno("ITA", 10_000, 25, COSTI, 1.1) == pytest.approx(10.00)


def test_costo_usa_piccolo():
    assert costo_andata_ritorno("USA", 100, 200, COSTI, 1.10) == pytest.approx(0.70 / 1.10 + 0.06)


def test_simula_conto_tasse():
    prev = prev_con_esiti([(date(2026, 10, 1), 10, 11), (date(2026, 10, 2), 10, 9.5)])
    conto = simula_conto(prev, {"ITA": 100}, ZERO, {}, 0.26)
    assert conto["finale_lordo"] == pytest.approx(104.5)
    assert conto["tasse"] == pytest.approx(1.17)
    assert conto["finale_netto"] == pytest.approx(103.33)
    assert len(conto["andamento"]) == 2


def test_simula_conto_perdita_niente_tasse():
    prev = prev_con_esiti([(date(2026, 10, 1), 10, 9)])
    conto = simula_conto(prev, {"ITA": 100}, ZERO, {}, 0.26)
    assert conto["tasse"] == 0 and conto["finale_netto"] == pytest.approx(90)


def test_simula_conto_con_costi_ibkr():
    prev = prev_con_esiti([(date(2026, 10, 1), 10, 10.15)])
    conto = simula_conto(prev, {"ITA": 100}, COSTI, {}, 0.26)
    assert conto["finale_lordo"] == pytest.approx(101.5 - 2.5)  # +1,5% mangiato dalle commissioni


def test_statistiche_vuote():
    stat = calcola_statistiche(leggi_previsioni("non-esiste.csv"), carica_config("config.yaml"), {}, {})
    assert stat["totale"] == 0 and stat["percentuale"] is None
    assert stat["conto_simulato"]["finale_netto"] == pytest.approx(1000)


def test_percentuali_e_calibrazione():
    esiti = [(date(2026, 10, d), 10, 11 if d % 2 else 9) for d in range(1, 11)]
    stat = calcola_statistiche(prev_con_esiti(esiti, prob=0.59), carica_config("config.yaml"), {}, {})
    assert stat["totale"] == 10 and stat["azzeccate"] == 5 and stat["percentuale"] == 0.5
    assert stat["per_mercato"]["ITA"]["totale"] == 10
    fascia = [f for f in stat["calibrazione"] if f["previsioni"] > 0]
    assert len(fascia) == 1 and fascia[0]["fascia"] == "58–61%" and fascia[0]["percentuale"] == 0.5
    assert {"segnale": "trend=su", "casi": 10, "percentuale": 0.5} in stat["segnali"]


def test_rendimento_indice():
    esiti = [(date(2026, 10, 1), 10, 11), (date(2026, 10, 5), 10, 11)]
    indice = pd.Series([100.0, 102.0, 103.0, 110.0],
                       index=pd.to_datetime(["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-05"]))
    stat = calcola_statistiche(prev_con_esiti(esiti), carica_config("config.yaml"), {}, {"ITA": indice})
    assert stat["indici"]["ITA"] == pytest.approx(110 / 100 - 1)


def test_conti_solo_sopra_soglia():
    prev = prev_con_esiti([(date(2026, 10, 1), 10, 11), (date(2026, 10, 2), 10, 5)])
    prev.loc[prev["data"] == "2026-10-02", "sotto_soglia"] = True
    stat = calcola_statistiche(prev, carica_config("config.yaml"), {}, {})
    assert stat["totale"] == 2
    assert stat["sopra_soglia"]["totale"] == 1 and stat["studio"]["totale"] == 1
    conto = simula_conto(prev[~prev["sotto_soglia"]], {"ITA": 100}, ZERO, {}, 0)
    assert stat["conto_simulato"]["andamento"][-1][0] == "2026-10-01"
    assert conto["finale_lordo"] == pytest.approx(110)
