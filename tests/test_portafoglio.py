"""Test del Portafoglio Investimenti Lab (S020)."""
from datetime import date

import numpy as np
import pandas as pd

from agente import portafoglio
from agente.posta import email_mattina

URL = "https://example.org"


def serie(valori, fine="2026-11-21"):
    idx = pd.date_range(end=fine, periods=len(valori), freq="D")
    return pd.Series(valori, index=idx, dtype=float)


def test_esposizione_salita_discesa_e_storia_corta():
    assert portafoglio.esposizione(serie(np.linspace(100, 300, 150))) == 6
    assert portafoglio.esposizione(serie(np.linspace(300, 100, 150))) == 0
    assert portafoglio.esposizione(serie(np.linspace(100, 300, 50))) == 0


def test_stato_nasdaq_zona_neutra():
    giorni = pd.bdate_range("2024-01-01", "2026-11-20")
    # 22 mesi in salita poi discesa lenta: deve restare DENTRO finché non scende sotto media −3%
    mesi = giorni.to_period("M")
    livelli = {p: 100 + i * 5 for i, p in enumerate(sorted(set(mesi)))}
    s = pd.Series([livelli[m] for m in mesi], index=giorni, dtype=float)
    st = portafoglio.stato_nasdaq(s, date(2026, 11, 22))
    assert st["stato"] == 1 and st["soglia"] < st["ultimo"]
    giu = s.copy()
    giu[giu.index >= "2026-10-01"] = 50.0          # ottobre crolla sotto la media −3%
    assert portafoglio.stato_nasdaq(giu, date(2026, 11, 22))["stato"] == 0
    # il mese in corso (novembre) non conta: un crollo a novembre non cambia lo stato di fine ottobre
    nov = s.copy()
    nov[nov.index >= "2026-11-01"] = 50.0
    assert portafoglio.stato_nasdaq(nov, date(2026, 11, 22))["stato"] == 1


def test_calcola_prima_volta_poi_cambio_e_candela_di_oggi_esclusa():
    btc = serie(list(np.linspace(100, 300, 149)) + [1.0], fine="2026-11-22")   # ultima candela = oggi (in corso)
    eth = serie(np.linspace(300, 100, 150), fine="2026-11-21")
    ndx = pd.Series(np.linspace(100, 200, 700), index=pd.bdate_range(end="2026-11-20", periods=700))
    pf = portafoglio.calcola(btc, eth, ndx, date(2026, 11, 22), 10000, None)
    assert pf["prima_volta"] and pf["azioni"] == []
    assert pf["stato"]["BTC"] == 6 and pf["stato"]["ETH"] == 0 and pf["stato"]["NDX"] == 1
    assert round(pf["righe"][0]["valore"]) == 2500
    pf2 = portafoglio.calcola(btc, eth, ndx, date(2026, 11, 22), 10000,
                              {"BTC": 2, "ETH": 0, "NDX": 0, "mese_ribilanciato": "2026-10"})
    testo = " | ".join(pf2["azioni"])
    assert "Bitcoin: da 2/6 a 6/6 → COMPRA" in testo
    assert "Nasdaq 2x: COMPRA" in testo
    assert "Inizio mese" in testo


def test_email_solo_portafoglio():
    btc = serie(np.linspace(100, 300, 150))
    ndx = pd.Series(np.linspace(100, 200, 700), index=pd.bdate_range(end="2026-11-20", periods=700))
    pf = portafoglio.calcola(btc, btc, ndx, date(2026, 11, 22), 10000,
                             {"BTC": 6, "ETH": 6, "NDX": 1, "mese_ribilanciato": "2026-11"})
    assert pf["azioni"] == []
    assert email_mattina([], URL, squeeze=None, portafoglio=pf) is None      # nessuna azione: nessuna email
    pf["azioni"] = ["Bitcoin: da 5/6 a 6/6 → COMPRA 0.0012 BTC"]
    oggetto, html = email_mattina([], URL, squeeze=None, portafoglio=pf)
    assert oggetto.startswith("💼 Portafoglio Lab:") and "Portafoglio Investimenti Lab" in html
