import json
import urllib.error

from agente.operazioni import Messaggio
from agente.posta import email_mattina, email_sera, invia

URL = "https://giobo76.github.io/maestro-del-mattino/"


def scheda(**cambi):
    base = {"mercato": "ITA", "nome_mercato": "Borsa Italiana", "valuta": "EUR", "nuova": True,
            "nome": "Campari", "simbolo": "CPR.MI", "resa": 0.25, "casi": 140, "sotto_soglia": False,
            "quantita": 15, "perdita_massima": 4.0,
            "livelli": {"riferimento": 6.62, "r": 0.24, "stop": 6.38, "pareggio": 6.86, "prima_uscita": 7.10}}
    base.update(cambi)
    return base


class Apri:
    def __init__(self, errore=None):
        self.richieste, self.errore = [], errore

    def __call__(self, richiesta, timeout):
        self.richieste.append(richiesta)
        if self.errore:
            raise self.errore
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"id": "1"}'


def test_invia_corpo_e_header():
    apri = Apri()
    assert invia("Oggetto", "<p>ciao</p>", "x@y.it", "chiave", apri=apri) is True
    [r] = apri.richieste
    assert r.full_url == "https://api.resend.com/emails"
    assert r.get_header("Authorization") == "Bearer chiave"
    corpo = json.loads(r.data)
    assert corpo["to"] == ["x@y.it"] and corpo["subject"] == "Oggetto"
    assert corpo["from"] == "Maestro del mattino <onboarding@resend.dev>"


def test_senza_chiave_non_invia():
    apri = Apri()
    assert invia("O", "h", "x@y.it", None, apri=apri) is False and apri.richieste == []


def test_errore_resend_non_blocca():
    errore = urllib.error.HTTPError("u", 403, "vietato", {}, None)
    assert invia("O", "h", "x@y.it", "chiave", apri=Apri(errore)) is False
    assert invia("O", "h", "x@y.it", "chiave", apri=Apri(OSError("rete"))) is False


def test_email_sera_vuota_none():
    assert email_sera([], URL) is None


def test_email_sera():
    oggetto, html = email_sera([Messaggio("1", "Campari", "stop", "🔴 Campari: stop toccato.")], URL)
    assert "1 aggiornamento" in oggetto and "stop toccato" in html and URL in html


def test_email_mattina_senza_operazioni_none():
    assert email_mattina([scheda(nuova=False), {"mercato": "USA", "simbolo": None}], URL) is None


def test_email_mattina_livelli():
    oggetto, html = email_mattina([scheda(), scheda(nome="Palantir", sotto_soglia=True, valuta="USD")], URL)
    assert oggetto == "📈 Nuova operazione: Campari, Palantir"
    assert "6,38 €" in html and "7,10 €" in html and "Stop loss" in html
    assert "solo studio" in html and URL in html
