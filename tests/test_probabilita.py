import pandas as pd
import pytest

from agente.probabilita import (
    costruisci_tabella, cerca, prepara_storico, prova_fuori_campione, simula_scelte,
)
from tests.aiuti import passeggiata


def storico_finto(gruppi, inizio="2024-01-01"):
    """gruppi: lista di (situazione, casi, salite)."""
    righe = []
    giorno = pd.Timestamp(inizio)
    for situazione, casi, salite in gruppi:
        for k in range(casi):
            giorno += pd.Timedelta(days=1)
            righe.append({"simbolo": f"T{k % 3}", "data": giorno, "situazione": situazione,
                          "data_esito": giorno + pd.Timedelta(days=1), "salito": k < salite,
                          "rend": 0.01 if k < salite else -0.01})
    return pd.DataFrame(righe)


def test_esito_apertura_chiusura():
    prezzi = passeggiata(60)
    prezzi.iloc[-1, prezzi.columns.get_loc("Open")] = 10.0
    prezzi.iloc[-1, prezzi.columns.get_loc("Close")] = 10.2
    storico = prepara_storico({"X": prezzi})
    riga = storico[storico["data"] == prezzi.index[-2]].iloc[0]
    assert riga["data_esito"] == prezzi.index[-1]
    assert bool(riga["salito"]) is True
    assert riga["rend"] == pytest.approx(0.02)
    assert prezzi.index[-1] not in set(storico["data"])


def test_correzione_pochi_casi():
    tabella = costruisci_tabella(storico_finto([("A", 40, 34), ("B", 40, 6)]), None, 30, 30)
    assert tabella.attrs["media"] == pytest.approx(0.5)
    assert tabella.loc["A", "prob"] == pytest.approx(0.7)
    assert tabella.loc["A", "casi"] == 40
    assert cerca(tabella, "A")["prob"] == pytest.approx(0.7)
    assert cerca(tabella, "Z") is None


def test_scarta_sotto_30_casi():
    tabella = costruisci_tabella(storico_finto([("A", 40, 20), ("C", 29, 20)]), None, 30, 30)
    assert "C" not in tabella.index


def test_fino_a_non_usa_futuro():
    base = storico_finto([("A", 40, 34), ("B", 40, 6)])
    fino_a = base["data_esito"].max()
    futuro = storico_finto([("A", 50, 0)], inizio="2030-01-01")
    con_futuro = pd.concat([base, futuro], ignore_index=True)
    pd.testing.assert_frame_equal(costruisci_tabella(base, fino_a, 30, 30),
                                  costruisci_tabella(con_futuro, fino_a, 30, 30))


def test_simula_rispetta_soglia():
    storico = storico_finto([("A", 40, 20), ("B", 40, 21)])
    tabella = costruisci_tabella(storico, None, 30, 30)
    assert simula_scelte(storico, tabella, storico["data_esito"].min(), 0.55).empty
    scelte = simula_scelte(storico, tabella, storico["data_esito"].min(), 0.0)
    assert list(scelte.columns) == ["data_esito", "simbolo", "prob", "salito", "rend"]
    assert scelte["data_esito"].is_unique


def test_prova_fuori_campione_chiavi():
    prezzi = {f"T{i}": passeggiata(780, seme=i) for i in range(5)}
    prova = prova_fuori_campione(prepara_storico(prezzi), 30, 30, 0.0)
    assert set(prova) == {"dal", "al", "giorni_con_scelta", "prob_media_annunciata",
                          "percentuale_reale", "rend_medio"}
    assert prova["giorni_con_scelta"] > 200
    assert 0 <= prova["percentuale_reale"] <= 1
