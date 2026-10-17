from datetime import date

import pandas as pd
import pytest

from agente.operazione import Livelli
from agente.operazioni import (
    aggiorna_operazioni, aperta_nel_mercato, leggi_operazioni, nuova_operazione, salva_operazioni,
)
from agente.scelta import Scelta


def scelta(mercato="ITA", simbolo="CPR.MI"):
    return Scelta(mercato=mercato, simbolo=simbolo, nome="Campari", resa=0.25, casi=140, pct_stop=0.4,
                  pct_2r=0.3, situazione="s", livelli=Livelli(100.0, 4.0, 96.0, 104.0, 108.0))


def barre_da(giorni, prima="2026-09-01"):
    """giorni: lista di (data, o, h, l, c). Prima 30 giorni piatti a 100 per la media a 20."""
    piatti = pd.bdate_range(prima, periods=30)
    righe = [(d, 100.0, 100.5, 99.5, 100.0) for d in piatti] + [(pd.Timestamp(d), *v) for d, *v in giorni]
    df = pd.DataFrame(righe, columns=["data", "Open", "High", "Low", "Close"]).set_index("data")
    df["Volume"] = 1000.0
    return lambda simboli, dal: {"CPR.MI": df}


SEMPRE = lambda mercato, giorno: True  # noqa: E731


def test_salva_e_rileggi_operazioni(tmp_path):
    op = nuova_operazione(scelta(), date(2026, 10, 19))
    assert op.id == "2026-10-19-ITA" and op.stato == "in attesa" and op.stop_iniziale == 96.0
    salva_operazioni([op], tmp_path / "operazioni.csv")
    [letta] = leggi_operazioni(tmp_path / "operazioni.csv")
    assert letta == op
    assert leggi_operazioni(tmp_path / "non-esiste.csv") == []


def test_aggiorna_percorso_completo():
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    barre = barre_da([("2026-10-19", 100, 105, 99, 104), ("2026-10-20", 104, 109, 103, 108),
                      ("2026-10-21", 103, 103, 100.1, 100.2), ("2026-10-22", 98, 99, 97, 98)])
    messaggi = aggiorna_operazioni(ops, barre, date(2026, 10, 21), SEMPRE)  # una sera alla volta
    messaggi += aggiorna_operazioni(ops, barre, date(2026, 10, 22), SEMPRE)
    assert [m.evento for m in messaggi] == ["ingresso", "pareggio", "prima_uscita", "sotto_media", "uscita_finale"]
    assert ops[0].stato == "chiusa"
    assert "Campari" in messaggi[2].testo and "108,00 €" in messaggi[2].testo


def test_giorni_applicati_una_volta():
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    barre = barre_da([("2026-10-19", 100, 101, 99, 100)])
    assert len(aggiorna_operazioni(ops, barre, date(2026, 10, 19), SEMPRE)) == 1
    assert aggiorna_operazioni(ops, barre, date(2026, 10, 19), SEMPRE) == []


def test_recupero_piu_giorni():
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    barre = barre_da([("2026-10-19", 100, 101, 99, 100), ("2026-10-20", 100, 105, 99, 104),
                      ("2026-10-21", 104, 104, 95, 96)])
    eventi = [m.evento for m in aggiorna_operazioni(ops, barre, date(2026, 10, 21), SEMPRE)]
    assert eventi == ["ingresso", "pareggio", "pareggio_stop"]


def test_seduta_non_chiusa_non_applicata():
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    barre = barre_da([("2026-10-19", 100, 101, 99, 100)])
    assert aggiorna_operazioni(ops, barre, date(2026, 10, 19), lambda m, g: False) == []
    assert ops[0].stato == "in attesa"


def test_titolo_senza_dati_segnalato():
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    vuoto = lambda simboli, dal: {}  # noqa: E731
    assert aggiorna_operazioni(ops, vuoto, date(2026, 10, 19), SEMPRE) == []
    [messaggio] = aggiorna_operazioni(ops, vuoto, date(2026, 10, 20), SEMPRE)
    assert messaggio.evento == "senza_dati" and ops[0].stato == "in attesa"


def test_aperta_nel_mercato():
    op = nuova_operazione(scelta(), date(2026, 10, 16))
    assert aperta_nel_mercato([op], "ITA") is op
    assert aperta_nel_mercato([op], "USA") is None
    op.stato = "chiusa"
    assert aperta_nel_mercato([op], "ITA") is None


def test_sera_saltata_non_inventa_la_vendita():
    """Chiusura sotto la media il 21, sera del 21 saltata: la vendita è all'apertura dopo l'avviso (23)."""
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    giorni = [("2026-10-19", 100, 105, 99, 104), ("2026-10-20", 104, 109, 103, 108),
              ("2026-10-21", 103, 103, 100.1, 100.2), ("2026-10-22", 101, 102, 100.5, 101),
              ("2026-10-23", 99, 100, 98, 99)]
    aggiorna_operazioni(ops, barre_da(giorni[:2]), date(2026, 10, 20), SEMPRE)
    eventi = [m.evento for m in aggiorna_operazioni(ops, barre_da(giorni[:4]), date(2026, 10, 22), SEMPRE)]
    assert eventi == ["sotto_media"] and ops[0].stato == "uscita domani"
    eventi = [m.evento for m in aggiorna_operazioni(ops, barre_da(giorni), date(2026, 10, 23), SEMPRE)]
    assert eventi == ["uscita_finale"] and ops[0].prezzo_uscita == 99 and ops[0].data_uscita == "2026-10-23"


def test_split_riscala_i_livelli():
    ops = [nuova_operazione(scelta(), date(2026, 10, 16))]
    aggiorna_operazioni(ops, barre_da([("2026-10-19", 100, 101, 99, 100)]), date(2026, 10, 19), SEMPRE)
    # split 10:1: Yahoo riscala tutta la storia
    df = barre_da([("2026-10-19", 100, 101, 99, 100), ("2026-10-20", 100, 101, 99, 100)])([], None)["CPR.MI"] / 10
    messaggi = aggiorna_operazioni(ops, lambda s, d: {"CPR.MI": df}, date(2026, 10, 20), SEMPRE)
    op = ops[0]
    assert op.stato == "aperta" and op.stop_iniziale == pytest.approx(9.6) and op.ingresso == pytest.approx(10)
    assert [m.evento for m in messaggi] == ["riscalato"]
