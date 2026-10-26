import json
from datetime import date
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
    assert "6,380 €" in html and "7,100 €" in html and "Stop loss" in html
    assert "solo studio" in html and URL in html


def test_email_mattina_quantita_zero_e_solo_simulato():
    _, html = email_mattina([scheda(quantita=0)], URL)
    assert "nemmeno una" in html
    _, html = email_mattina([scheda(quantita=0, capitale=1000)], URL)
    assert "con 1.000 € non puoi" in html
    _, html = email_mattina([scheda(quantita=None)], URL)
    assert "non incluso nel tuo conto" in html


def test_prezzi_sotto_10_con_tre_decimali():
    _, html = email_mattina([scheda(livelli={"riferimento": 5.958, "r": 0.17, "stop": 5.7882,
                                             "pareggio": 6.1277, "prima_uscita": 6.2976})], URL)
    assert "5,788 €" in html and "6,298 €" in html


def test_email_mattina_istruzioni_tws():
    _, html = email_mattina([scheda(quantita=167, livelli={"riferimento": 5.958, "r": 0.17, "stop": 5.7882,
                                                           "pareggio": 6.1277, "prima_uscita": 6.2976})],
                            URL, oggi=date(2026, 10, 26))
    assert "Come inserirlo in TWS" in html and "Prima delle 09:00" in html
    assert "Q.TÀ <b>167</b>" in html and "Ordini bracket" in html
    assert "LMT <b>6.298</b>" in html and "quantità <b>83</b>" in html  # metà per difetto in Italia
    assert "STP <b>5.788</b>" in html and "innesco <b>6.128</b>" in html


def test_istruzioni_tws_usa_orario_e_frazioni():
    _, html = email_mattina([scheda(mercato="USA", valuta="USD", nome="Caterpillar", simbolo="CAT", quantita=1.6335,
                                    livelli={"riferimento": 687.0, "r": 54.75, "stop": 632.25,
                                             "pareggio": 741.75, "prima_uscita": 796.50})],
                            URL, oggi=date(2026, 10, 26))
    assert "Prima delle 14:30" in html  # settimana del cambio d'ora: New York apre un'ora prima
    assert "quantità <b>0.8167</b>" in html and "LMT <b>796.50</b>" in html
    _, html = email_mattina([scheda(mercato="USA", valuta="USD", quantita=1.6335)], URL, oggi=date(2026, 11, 3))
    assert "Prima delle 15:30" in html


def test_istruzioni_tws_assenti_se_solo_studio_o_senza_quantita():
    _, html = email_mattina([scheda(sotto_soglia=True)], URL, oggi=date(2026, 10, 26))
    assert "Come inserirlo in TWS" not in html
    _, html = email_mattina([scheda(quantita=0)], URL, oggi=date(2026, 10, 26))
    assert "Come inserirlo in TWS" not in html
