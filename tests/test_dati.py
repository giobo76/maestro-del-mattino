from datetime import date, datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from agente import dati
from agente.dati import (
    DatiNonDisponibili, scarica_chiusure, scarica_notizie, scarica_prezzi, scarica_prezzi_giorno,
)


def download_finto(tabelle):
    """tabelle: simbolo -> DataFrame. Restituisce colonne (simbolo, campo) come yfinance."""
    def finto(simboli, **kwargs):
        return pd.concat({s: tabelle[s] for s in simboli}, axis=1)
    return finto


def tabella(giorni, valore=10.0):
    indice = pd.bdate_range("2026-06-01", periods=giorni)
    return pd.DataFrame({c: np.full(giorni, valore) for c in ["Open", "High", "Low", "Close", "Volume"]},
                        index=indice)


def test_scarta_riga_di_oggi(monkeypatch):
    t = tabella(80)
    oggi = t.index[-1].date()
    monkeypatch.setattr(dati.yf, "download", download_finto({"AAA": t}))
    risultato = scarica_prezzi(["AAA"], 1, oggi, pausa_s=0)
    assert risultato["AAA"].index[-1].date() < oggi
    assert len(risultato["AAA"]) == 79


def test_simbolo_senza_dati_escluso(monkeypatch):
    vuota = tabella(80, valore=np.nan)
    monkeypatch.setattr(dati.yf, "download", download_finto({"AAA": tabella(80), "ZZZ": vuota}))
    risultato = scarica_prezzi(["AAA", "ZZZ"], 1, date(2030, 1, 1), pausa_s=0)
    assert set(risultato) == {"AAA"}


def test_tre_tentativi_poi_errore(monkeypatch):
    chiamate = []

    def rotto(*args, **kwargs):
        chiamate.append(1)
        raise ConnectionError("niente rete")

    monkeypatch.setattr(dati.yf, "download", rotto)
    with pytest.raises(DatiNonDisponibili):
        scarica_prezzi(["AAA"], 1, date(2030, 1, 1), pausa_s=0)
    assert len(chiamate) == 3


def test_download_vuoto_e_errore(monkeypatch):
    monkeypatch.setattr(dati.yf, "download", lambda *a, **k: pd.DataFrame())
    with pytest.raises(DatiNonDisponibili):
        scarica_prezzi(["AAA"], 1, date(2030, 1, 1), pausa_s=0)


def test_prezzi_giorno(monkeypatch):
    t = tabella(5)
    t.loc[t.index[2], "Open"] = 9.0
    giorno = t.index[2].date()
    monkeypatch.setattr(dati.yf, "download", download_finto({"AAA": t, "BBB": tabella(5, np.nan)}))
    assert scarica_prezzi_giorno(["AAA", "BBB"], giorno) == {"AAA": (9.0, 10.0)}


def voce(titolo, ore_fa, adesso):
    momento = (adesso - pd.Timedelta(hours=ore_fa)).timetuple()
    return SimpleNamespace(title=titolo, link="http://x", published_parsed=momento,
                           source=SimpleNamespace(title="Fonte"))


def test_feed_rotto_saltato(monkeypatch):
    adesso = datetime(2026, 10, 16, 7, 0, tzinfo=timezone.utc)

    def parse(url):
        if "news.google.com" in url:
            raise ConnectionError("rotto")
        return SimpleNamespace(entries=[voce("Apple sale", 2, adesso), voce("Vecchia", 50, adesso)])

    monkeypatch.setattr(dati.feedparser, "parse", parse)
    notizie = scarica_notizie("Apple", "AAPL", "en", adesso=adesso)
    assert [n.titolo for n in notizie] == ["Apple sale"]


def test_notizie_italiane_solo_google(monkeypatch):
    adesso = datetime(2026, 10, 16, 7, 0, tzinfo=timezone.utc)
    url_chiesti = []

    def parse(url):
        url_chiesti.append(url)
        return SimpleNamespace(entries=[voce(f"Eni {i}", i, adesso) for i in range(15)])

    monkeypatch.setattr(dati.feedparser, "parse", parse)
    notizie = scarica_notizie("Eni", "ENI.MI", "it", adesso=adesso)
    assert len(url_chiesti) == 1 and "hl=it" in url_chiesti[0]
    assert len(notizie) == 10
    assert notizie[0].titolo == "Eni 0"


def test_titolo_fermo_escluso(monkeypatch):
    attivo, fermo = tabella(80), tabella(60)
    monkeypatch.setattr(dati.yf, "download", download_finto({"AAA": attivo, "OLD": fermo}))
    ultima = attivo.index[-1].date()
    risultato = scarica_prezzi(["AAA", "OLD"], 1, date(2030, 1, 1), pausa_s=0, ultima=ultima)
    assert set(risultato) == {"AAA"}


def test_tutti_fermi_dati_non_disponibili(monkeypatch):
    monkeypatch.setattr(dati.yf, "download", download_finto({"AAA": tabella(80)}))
    with pytest.raises(DatiNonDisponibili):
        scarica_prezzi(["AAA"], 1, date(2030, 1, 1), pausa_s=0, ultima=date(2029, 12, 31))


def test_chiusure_dal_giorno_chiesto(monkeypatch):
    chiesto = {}

    def finto(simboli, **kwargs):
        chiesto.update(kwargs)
        return download_finto({"^GSPC": tabella(80)})(simboli)

    monkeypatch.setattr(dati.yf, "download", finto)
    serie = scarica_chiusure("^GSPC", date(2024, 3, 10))
    assert chiesto["start"] == "2024-03-03"
    assert len(serie) == 80
