from datetime import date, datetime, timezone

from agente.archivio import (
    COLONNE, aggiungi_previsioni, leggi_oggi, leggi_previsioni, salva_oggi, salva_previsioni,
)
from agente.dati import Notizia
from agente.scelta import Scelta


def scelta(mercato="ITA", simbolo="ENI.MI", prob=0.57):
    return Scelta(mercato=mercato, simbolo=simbolo, nome="Eni", prob=prob, casi=142, rend_medio=0.004,
                  situazione="trend=su", giudizio_notizie="neutro")


def test_file_mancante_vuoto(tmp_path):
    prev = leggi_previsioni(tmp_path / "previsioni.csv")
    assert prev.empty and list(prev.columns) == COLONNE


def test_aggiungi_e_rileggi(tmp_path):
    percorso = tmp_path / "previsioni.csv"
    prev = aggiungi_previsioni(leggi_previsioni(percorso), date(2026, 10, 16),
                               [scelta(), Scelta(mercato="USA", nota="nessuno")])
    salva_previsioni(prev, percorso)
    riletto = leggi_previsioni(percorso)
    assert len(riletto) == 1
    riga = riletto.iloc[0]
    assert riga["data"] == "2026-10-16" and riga["simbolo"] == "ENI.MI"
    assert riga["prob"] == 0.57 and riga["casi"] == 142
    assert riletto["salito"].isna().all()


def test_nessun_doppione():
    prev = aggiungi_previsioni(leggi_previsioni("non-esiste.csv"), date(2026, 10, 16), [scelta()])
    prev = aggiungi_previsioni(prev, date(2026, 10, 16), [scelta(simbolo="ENEL.MI", prob=0.6)])
    assert len(prev) == 1 and prev.iloc[0]["simbolo"] == "ENEL.MI"


def test_oggi_json(tmp_path):
    percorso = tmp_path / "oggi.json"
    assert leggi_oggi(percorso) is None
    notizia = Notizia("t", "http://x", "f", datetime(2026, 10, 16, tzinfo=timezone.utc))
    salva_oggi(percorso, {"data": "2026-10-16", "schede": [{"notizie": [notizia]}]})
    letto = leggi_oggi(percorso)
    assert letto["data"] == "2026-10-16"
    assert letto["schede"][0]["notizie"][0]["titolo"] == "t"
