import numpy as np
import pandas as pd
import pytest

from agente.operazione import Operazione, avanza, livelli_da, risultato_r
from agente.segnali import calcola_indicatori
from agente.storico_r import cerca, costruisci_tabella_r, prova_fuori_campione_r, simula_storico
from tests.aiuti import crea_prezzi, passeggiata


def salita_e_discesa():
    chiusure = np.concatenate([np.linspace(100, 200, 100), np.linspace(198, 160, 20)])
    prezzi = crea_prezzi(chiusure, massimi=chiusure + 1)
    prezzi["Low"] = chiusure - 1
    return prezzi


def test_simula_salita_e_discesa():
    storico = simula_storico({"X": salita_e_discesa()}, 2.0)
    primi = storico[storico["data_segnale"] < storico["data_segnale"].iloc[0] + pd.Timedelta(days=40)]
    assert len(primi) > 5
    assert (primi["esito"] == "prima_uscita").all()
    assert (primi["risultato_r"] > 1).all()


def test_simula_usa_avanza():
    prezzi = passeggiata(200, seme=4)
    storico = simula_storico({"X": prezzi}, 2.0)
    riga = storico[storico["chiusa"]].iloc[10]
    ind = calcola_indicatori(prezzi)
    t = ind.index.get_loc(riga["data_segnale"])
    lv = livelli_da(ind["Close"].iloc[t], ind["atr14"].iloc[t], 2.0)
    op = Operazione("x", "ITA", "X", "X", "d", lv.riferimento, lv.r, lv.stop, lv.pareggio, lv.prima_uscita,
                    False, 0.0, 0)
    for j in range(t + 1, len(ind)):
        avanza(op, str(ind.index[j].date()), *ind[["Open", "High", "Low", "Close", "sma20"]].iloc[j])
        if op.stato == "chiusa":
            break
    assert riga["risultato_r"] == pytest.approx(risultato_r(op))
    assert riga["data_uscita"] == ind.index[j]


def test_nessuna_sbirciata():
    prezzi = passeggiata(300, seme=5)
    corto = simula_storico({"X": prezzi.iloc[:200]}, 2.0)
    lungo = simula_storico({"X": prezzi}, 2.0).set_index("data_segnale")
    for _, riga in corto[corto["chiusa"]].iterrows():
        assert lungo.loc[riga["data_segnale"], "risultato_r"] == pytest.approx(riga["risultato_r"])


def storico_finto(gruppi):
    """gruppi: lista di (situazione, operazioni, risultato_r)."""
    righe, giorno = [], pd.Timestamp("2024-01-01")
    for situazione, quante, r in gruppi:
        for _ in range(quante):
            giorno += pd.Timedelta(days=1)
            righe.append({"simbolo": "X", "data_segnale": giorno, "situazione": situazione,
                          "data_uscita": giorno + pd.Timedelta(days=3), "chiusa": True,
                          "risultato_r": r, "esito": "stop" if r < 0 else "prima_uscita"})
    return pd.DataFrame(righe)


def test_tabella_correzione_e_scarto():
    tabella = costruisci_tabella_r(storico_finto([("A", 40, 1.0), ("B", 40, -1.0), ("C", 29, 1.0)]),
                                   None, 30, 30)
    assert "C" not in tabella.index
    media = (40 - 40 + 29) / 109
    assert tabella.attrs["media"] == pytest.approx(media)
    assert tabella.loc["A", "resa"] == pytest.approx(40 / 70)  # prudente: tirata verso 0, non verso la media
    assert tabella.loc["A", "pct_2r"] == 1.0 and tabella.loc["B", "pct_stop"] == 1.0
    assert cerca(tabella, "A")["casi"] == 40 and cerca(tabella, "Z") is None


def test_tabella_ignora_aperte():
    storico = storico_finto([("A", 40, 1.0)])
    storico.loc[:9, "chiusa"] = False
    assert costruisci_tabella_r(storico, None, 30, 30).loc["A", "casi"] == 30


def test_prova_una_posizione_alla_volta():
    vecchie = storico_finto([("A", 40, 1.0)])
    vecchie["data_segnale"] -= pd.Timedelta(days=800)
    vecchie["data_uscita"] -= pd.Timedelta(days=800)
    base = pd.Timestamp("2026-01-05")
    nuove = pd.DataFrame([
        {"simbolo": "X", "data_segnale": base, "situazione": "A", "data_uscita": base + pd.Timedelta(days=10),
         "chiusa": True, "risultato_r": 2.0, "esito": "prima_uscita"},
        {"simbolo": "Y", "data_segnale": base + pd.Timedelta(days=2), "situazione": "A",
         "data_uscita": base + pd.Timedelta(days=5), "chiusa": True, "risultato_r": -1.0, "esito": "stop"},
        {"simbolo": "Z", "data_segnale": base + pd.Timedelta(days=12), "situazione": "A",
         "data_uscita": base + pd.Timedelta(days=20), "chiusa": True, "risultato_r": 1.0, "esito": "prima_uscita"},
    ])
    prova = prova_fuori_campione_r(pd.concat([vecchie, nuove], ignore_index=True), 30, 30, 0.1)
    assert prova["operazioni"] == 2 and prova["resa_reale"] == pytest.approx(1.5)


def test_prova_chiavi():
    prezzi = {f"T{i}": passeggiata(780, seme=i) for i in range(4)}
    prova = prova_fuori_campione_r(simula_storico(prezzi, 2.0), 30, 30, -10)
    assert set(prova) == {"dal", "al", "operazioni", "ancora_aperte", "resa_annunciata", "resa_reale",
                          "pct_stop", "pct_2r"}
    assert prova["operazioni"] > 5
