from datetime import datetime, timezone

from agente.dati import Notizia
from agente.spiegazione import giudica_notizie, scrivi_testi

NOTIZIA = Notizia("Eni alza le stime", "http://x", "Sole", datetime(2026, 10, 16, tzinfo=timezone.utc))
SCHEDA = {"nome": "Eni", "mercato": "Borsa Italiana", "prob": 0.57, "casi": 142, "rend_medio": 0.004,
          "situazione": "trend=su|rsi=normale|macd=rialzo|vol=alto|rottura=no|giorno=normale",
          "notizie": ["Eni alza le stime"]}
TESTI_OK = ('{"perche": "Il titolo sale.", "rischio": "Dati USA.", "parola": "MACD", '
            '"parola_spiegazione": "Un indicatore."}')


class CervelloFinto:
    def __init__(self, risposta=None, errore=None):
        self.risposta, self.errore, self.prompt = risposta, errore, []

    def genera(self, prompt):
        self.prompt.append(prompt)
        if self.errore:
            raise self.errore
        return self.risposta


def test_giudizio_valido():
    assert giudica_notizie(CervelloFinto('{"giudizio": "negativo"}'), "Eni", [NOTIZIA]) == "negativo"


def test_nessuna_notizia_neutro():
    cervello = CervelloFinto('{"giudizio": "negativo"}')
    assert giudica_notizie(cervello, "Eni", []) == "neutro"
    assert cervello.prompt == []


def test_json_rotto_restituisce_none():
    assert giudica_notizie(CervelloFinto("non è json"), "Eni", [NOTIZIA]) is None
    assert scrivi_testi(CervelloFinto("non è json"), SCHEDA, []) is None


def test_valore_fuori_elenco():
    assert giudica_notizie(CervelloFinto('{"giudizio": "boh"}'), "Eni", [NOTIZIA]) is None


def test_errore_di_rete_restituisce_none():
    assert giudica_notizie(CervelloFinto(errore=RuntimeError("429")), "Eni", [NOTIZIA]) is None
    assert scrivi_testi(CervelloFinto(errore=RuntimeError("429")), SCHEDA, []) is None


def test_testi_validi_anche_con_blocco_codice():
    testi = scrivi_testi(CervelloFinto("```json\n" + TESTI_OK + "\n```"), SCHEDA, [])
    assert testi["parola"] == "MACD"


def test_testi_chiave_mancante():
    assert scrivi_testi(CervelloFinto('{"perche": "x", "parola": "y", "parola_spiegazione": "z"}'),
                        SCHEDA, []) is None


def test_cervello_none():
    assert giudica_notizie(None, "Eni", [NOTIZIA]) is None
    assert scrivi_testi(None, SCHEDA, []) is None


def test_prompt_contiene_parole_usate():
    cervello = CervelloFinto(TESTI_OK)
    scrivi_testi(cervello, SCHEDA, ["RSI", "volumi"])
    assert "RSI" in cervello.prompt[0] and "57,0%" in cervello.prompt[0] and "+0,40%" in cervello.prompt[0]


def test_prompt_avvisa_solo_studio():
    cervello = CervelloFinto(TESTI_OK)
    scrivi_testi(cervello, {**SCHEDA, "sotto_soglia": True}, [])
    assert "solo per studio" in cervello.prompt[0]
    cervello = CervelloFinto(TESTI_OK)
    scrivi_testi(cervello, SCHEDA, [])
    assert "solo per studio" not in cervello.prompt[0]
