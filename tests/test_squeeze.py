import numpy as np
import pandas as pd

from agente import squeeze
from agente.posta import blocco_squeeze, email_mattina

URL = "https://giobo76.github.io/maestro-del-mattino/"


def serie(n=200, seme=1):
    """Sale per 120 giorni, poi scende: il momentum deve passare dal verde al rosso."""
    rng = np.random.default_rng(seme)
    c = 100 * np.exp(np.cumsum(np.r_[np.full(120, 0.004), np.full(n - 120, -0.006)] + rng.normal(0, 0.01, n)))
    return pd.DataFrame({"High": c * 1.01, "Low": c * 0.99, "Close": c}, index=pd.bdate_range("2026-01-01", periods=n))


def test_valori_di_riferimento():
    # valori calcolati con lo scanner di Trading-Lab S014, verificato su ENI contro TradingView (2026-11-09)
    vf = squeeze.momentum(serie())
    assert [round(float(x), 4) for x in vf.iloc[[60, 119, 150, 199]]] == [38.8411, 42.0108, -64.411, -74.7819]


def test_cambio_verde_rosso_rilevato_il_giorno_giusto():
    df = serie()
    vf = squeeze.momentum(df).dropna()
    giorno = next(vf.index[i] for i in range(1, len(vf)) if vf.iloc[i] < 0 <= vf.iloc[i - 1])
    r = squeeze.riepilogo({"X.MI": df.loc[:giorno]}, {"X.MI": "Prova"})
    assert r["data"] == giorno.date().isoformat()
    assert [v["nome"] for v in r["verso_rosso"]] == ["Prova"] and r["verso_verde"] == []
    assert r["rossi"][0]["giorni"] == 1


def test_nessun_cambio_nessuna_email():
    sq = {"data": "2026-11-06", "verso_rosso": [], "verso_verde": [], "rossi": [], "titoli": 40}
    assert blocco_squeeze(sq) == ""
    assert email_mattina([], URL, squeeze=sq) is None
    assert email_mattina([], URL, squeeze=None) is None


def test_email_solo_cambi_di_colore():
    voce = {"simbolo": "ENI.MI", "nome": "Eni", "momentum": -14.4, "ieri": 5.3, "chiusura": 25.05, "giorni": 1}
    sq = {"data": "2026-11-06", "verso_rosso": [voce], "verso_verde": [], "rossi": [voce], "titoli": 40}
    oggetto, html = email_mattina([], URL, squeeze=sq)
    assert oggetto == "🔄 FTSE MIB: 1 al rosso"
    assert "Eni" in html and "06/11" in html and "+5,3 → -14,4" in html and "Rossi in tutto: 1 su 40" in html
    assert "non batte il compra e tieni" in html


def test_riepilogo_ignora_titoli_corti():
    df = serie().iloc[:5]
    assert squeeze.riepilogo({"X.MI": df}, {}) == {"data": None, "verso_rosso": [], "verso_verde": [],
                                                   "rossi": [], "titoli": 1}
