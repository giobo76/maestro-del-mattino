import pandas as pd

from agente.config import Mercato
from agente.scelta import scegli
from agente.segnali import calcola_indicatori, calcola_situazione
from tests.aiuti import passeggiata

MERCATO = Mercato("ITA", "Borsa Italiana", "XMIL", "FTSEMIB.MI", "EUR", "it",
                  {"AAA.MI": "Alfa", "BBB.MI": "Beta", "CCC.MI": "Gamma"})


def prepara(probabilita):
    """probabilita: simbolo -> prob (None = situazione assente dalla tabella)."""
    prezzi, righe = {}, []
    for i, (simbolo, prob) in enumerate(probabilita.items()):
        prezzi[simbolo] = passeggiata(80, seme=i)
        situazione = calcola_situazione(calcola_indicatori(prezzi[simbolo])).iloc[-1]
        if prob is not None:
            righe.append({"situazione": situazione, "casi": 100, "salite": int(prob * 100),
                          "prob_grezza": prob, "prob": prob, "rend_medio": 0.003})
    tabella = pd.DataFrame(righe).drop_duplicates("situazione").set_index("situazione")
    return prezzi, tabella


def nessuna_notizia(nome, simbolo):
    return []


def test_sceglie_prob_piu_alta():
    prezzi, tabella = prepara({"AAA.MI": 0.56, "BBB.MI": 0.60})
    assert len(tabella) == 2  # situazioni diverse, altrimenti il test non ha senso
    scelta = scegli(MERCATO, prezzi, tabella, nessuna_notizia, lambda n, x: "neutro", 0.55)
    assert scelta.simbolo == "BBB.MI" and scelta.nome == "Beta"
    assert scelta.prob == 0.60 and scelta.casi == 100 and scelta.nota == ""


def test_scarta_notizie_negative():
    prezzi, tabella = prepara({"AAA.MI": 0.56, "BBB.MI": 0.60})
    giudizi = {"Beta": "negativo", "Alfa": "positivo"}
    scelta = scegli(MERCATO, prezzi, tabella, nessuna_notizia, lambda nome, n: giudizi[nome], 0.55)
    assert scelta.simbolo == "AAA.MI"
    assert scelta.scartati == ["BBB.MI"]
    assert scelta.giudizio_notizie == "positivo"


def test_tutti_scartati():
    prezzi, tabella = prepara({"AAA.MI": 0.56, "BBB.MI": 0.60})
    scelta = scegli(MERCATO, prezzi, tabella, nessuna_notizia, lambda n, x: "negativo", 0.55)
    assert scelta.simbolo is None
    assert "notizie negative" in scelta.nota


def test_nessuno_sopra_soglia():
    prezzi, tabella = prepara({"AAA.MI": 0.51, "BBB.MI": 0.52})
    scelta = scegli(MERCATO, prezzi, tabella, nessuna_notizia, lambda n, x: "neutro", 0.55)
    assert scelta.simbolo is None
    assert "55%" in scelta.nota


def test_giudizio_non_disponibile():
    prezzi, tabella = prepara({"AAA.MI": 0.58})
    scelta = scegli(MERCATO, prezzi, tabella, nessuna_notizia, lambda n, x: None, 0.55)
    assert scelta.simbolo == "AAA.MI"
    assert scelta.nota == "Filtro notizie non disponibile oggi."


def test_situazione_sconosciuta_ignorata():
    prezzi, tabella = prepara({"AAA.MI": 0.58, "CCC.MI": None})
    scelta = scegli(MERCATO, prezzi, tabella, nessuna_notizia, lambda n, x: "neutro", 0.55)
    assert scelta.simbolo == "AAA.MI"
