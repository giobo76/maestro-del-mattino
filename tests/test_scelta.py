import numpy as np
import pandas as pd

from agente.config import Mercato
from agente.scelta import scegli
from agente.segnali import calcola_indicatori, calcola_situazione
from tests.aiuti import crea_prezzi, passeggiata

MERCATO = Mercato("ITA", "Borsa Italiana", "XMIL", "FTSEMIB.MI", "EUR", "it",
                  {"AAA.MI": "Alfa", "BBB.MI": "Beta", "CCC.MI": "Gamma", "FER.MI": "Fermo"})


def prepara(rese):
    """rese: simbolo -> resa in R (None = situazione assente dalla tabella)."""
    prezzi, righe = {}, []
    for i, (simbolo, resa) in enumerate(rese.items()):
        prezzi[simbolo] = crea_prezzi(np.full(80, 10.0)) if simbolo == "FER.MI" else passeggiata(80, seme=i)
        situazione = calcola_situazione(calcola_indicatori(prezzi[simbolo])).iloc[-1]
        if resa is not None:
            righe.append({"situazione": situazione, "casi": 100, "resa_grezza": resa, "resa": resa,
                          "pct_stop": 0.4, "pct_2r": 0.3})
    tabella = pd.DataFrame(righe).drop_duplicates("situazione").set_index("situazione")
    return prezzi, tabella


def nessuna_notizia(nome, simbolo):
    return []


def scelta(rese, giudica=lambda n, x: "neutro", studio=False):
    prezzi, tabella = prepara(rese)
    return scegli(MERCATO, prezzi, tabella, nessuna_notizia, giudica, 0.10, 2.0, studio=studio), tabella


def test_sceglie_resa_piu_alta():
    s, tabella = scelta({"AAA.MI": 0.2, "BBB.MI": 0.4})
    assert len(tabella) == 2
    assert s.simbolo == "BBB.MI" and s.nome == "Beta" and s.resa == 0.4 and s.casi == 100
    assert s.pct_stop == 0.4 and s.pct_2r == 0.3 and s.nota == ""
    assert s.livelli.stop < s.livelli.riferimento < s.livelli.pareggio < s.livelli.prima_uscita


def test_scarta_notizie_negative():
    s, _ = scelta({"AAA.MI": 0.2, "BBB.MI": 0.4}, giudica=lambda nome, n: {"Beta": "negativo"}.get(nome, "neutro"))
    assert s.simbolo == "AAA.MI" and s.scartati == ["BBB.MI"]


def test_nessuno_sopra_soglia():
    s, _ = scelta({"AAA.MI": 0.05, "BBB.MI": -0.1})
    assert s.simbolo is None
    assert s.nota == "Oggi nessun titolo ha una resa storica di almeno +0,10R: meglio stare fermi."


def test_modalita_studio_sotto_soglia():
    s, _ = scelta({"AAA.MI": 0.05, "BBB.MI": -0.1}, studio=True)
    assert s.simbolo == "AAA.MI" and s.sotto_soglia is True
    assert s.nota == "Sotto soglia: solo per studio, non per investire."


def test_atr_nullo_escluso():
    s, tabella = scelta({"AAA.MI": 0.2, "FER.MI": 0.9})
    assert len(tabella) == 2
    assert s.simbolo == "AAA.MI"


def test_situazione_sconosciuta_ignorata():
    s, _ = scelta({"AAA.MI": 0.2, "CCC.MI": None})
    assert s.simbolo == "AAA.MI"
