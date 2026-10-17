import dataclasses
import json
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from agente.archivio import leggi_oggi
from agente.config import carica_config
from agente.dati import DatiNonDisponibili
from agente.main import Servizi, deve_partire, esegui_mattina, esegui_sera
from agente.operazioni import leggi_operazioni
from tests.aiuti import passeggiata

RISPOSTA = json.dumps({"giudizio": "neutro", "perche": "Spiegazione.", "rischio": "Rischio.",
                       "parola": "RSI", "parola_spiegazione": "Indicatore."})


class Cervello:
    def genera(self, prompt):
        return RISPOSTA


def config_piccola():
    cfg = carica_config("config.yaml")
    mercati = {
        "ITA": dataclasses.replace(cfg.mercati["ITA"], titoli={"A.MI": "Alfa", "B.MI": "Beta", "C.MI": "Gamma"}),
        "USA": dataclasses.replace(cfg.mercati["USA"], titoli={"X": "Xray", "Y": "Yank", "Z": "Zulu"}),
    }
    return dataclasses.replace(cfg, mercati=mercati, soglia_r=-100.0)


class Posta:
    def __init__(self):
        self.inviate = []

    def __call__(self, oggetto, html):
        self.inviate.append((oggetto, html))
        return True


def barre_crollo(simboli, dal):
    """Ultima barra il 20/10/2026 con apertura bassissima: ogni operazione si chiude sotto lo stop."""
    indice = pd.bdate_range(end="2026-10-20", periods=40)
    df = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1000.0}, index=indice)
    df.iloc[-1] = [0.001, 0.002, 0.0005, 0.001, 1000.0]
    return {s: df for s in simboli}


def servizi(rotto=None, barre=barre_crollo):
    def prezzi(simboli, anni, oggi, ultima=None):
        if rotto and rotto in simboli[0]:
            raise DatiNonDisponibili("giù")
        return {s: passeggiata(400 if anni > 1 else 250, seme=i, inizio="2025-01-01") for i, s in enumerate(simboli)}

    return Servizi(
        scarica_prezzi=prezzi,
        scarica_dal=barre,
        scarica_notizie=lambda nome, simbolo, lingua: [],
        cervello=Cervello(),
        cambi=lambda dal, al: {},
        indici=lambda simbolo, dal: None,
        invia=Posta(),
        adesso=lambda: datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


def ora(testo):
    return datetime.fromisoformat(testo).replace(tzinfo=timezone.utc)


def test_deve_partire_ora_legale():
    assert deve_partire("mattina", ora("2026-07-15T05:30"), None)
    assert not deve_partire("mattina", ora("2026-07-15T06:30"), {"fatto_mattina": "2026-07-15"})
    assert deve_partire("sera", ora("2026-07-15T20:30"), {"fatto_mattina": "2026-07-15"})


def test_deve_partire_ora_solare():
    assert not deve_partire("mattina", ora("2026-01-15T05:30"), None)
    assert deve_partire("mattina", ora("2026-01-15T06:30"), None)
    assert not deve_partire("sera", ora("2026-01-15T20:30"), None)
    assert deve_partire("sera", ora("2026-01-15T21:30"), None)
    assert deve_partire("tabella", ora("2026-01-15T08:00"), None)


def test_mattina_crea_operazioni(tmp_path):
    s = servizi()
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), s)
    ops = leggi_operazioni(tmp_path / "dati" / "operazioni.csv")
    assert {o.mercato for o in ops} == {"ITA", "USA"} and all(o.stato == "in attesa" for o in ops)
    oggi = leggi_oggi(tmp_path / "dati" / "oggi.json")
    assert oggi["fatto_mattina"] == "2026-10-19"
    scheda = oggi["schede"][0]
    assert scheda["nuova"] is True and scheda["testi"]["perche"] == "Spiegazione."
    assert scheda["livelli"]["stop"] < scheda["livelli"]["riferimento"]
    assert (tmp_path / "dati" / "tabella_ITA.csv").exists() and (tmp_path / "dati" / "grafici" / "ITA.png").exists()
    [(oggetto, html)] = s.invia.inviate
    assert oggetto.startswith("📈 Nuova operazione")
    assert "Stop loss" in (tmp_path / "sito" / "index.html").read_text(encoding="utf-8")


def test_mattina_non_apre_seconda_posizione(tmp_path):
    cfg = config_piccola()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    s = servizi()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 20), s)
    assert len(leggi_operazioni(tmp_path / "dati" / "operazioni.csv")) == 2
    schede = leggi_oggi(tmp_path / "dati" / "oggi.json")["schede"]
    assert all(x["posizione_id"] for x in schede) and s.invia.inviate == []


def test_mercato_chiuso_saltato(tmp_path):
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 11, 26), servizi())
    assert [o.mercato for o in leggi_operazioni(tmp_path / "dati" / "operazioni.csv")] == ["ITA"]
    scheda_usa = [x for x in leggi_oggi(tmp_path / "dati" / "oggi.json")["schede"] if x["mercato"] == "USA"][0]
    assert scheda_usa["nota"] == "Borsa chiusa oggi."


def test_dati_non_disponibili_un_mercato(tmp_path):
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi(rotto="X"))
    assert [o.mercato for o in leggi_operazioni(tmp_path / "dati" / "operazioni.csv")] == ["ITA"]
    schede = leggi_oggi(tmp_path / "dati" / "oggi.json")["schede"]
    assert [x["nota"] for x in schede if x["mercato"] == "USA"] == ["Dati non disponibili oggi."]


def test_sera_aggiorna_e_avvisa(tmp_path):
    cfg = config_piccola()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    s = servizi()
    esegui_sera(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 20), s)
    ops = leggi_operazioni(tmp_path / "dati" / "operazioni.csv")
    assert all(o.stato == "chiusa" for o in ops)
    [(oggetto, html)] = s.invia.inviate
    assert "aggiornamenti" in oggetto and "stop toccato" in html and "operazione partita" in html
    assert leggi_oggi(tmp_path / "dati" / "oggi.json")["fatto_sera"] == "2026-10-20"
    assert "Storico" in (tmp_path / "sito" / "index.html").read_text(encoding="utf-8")


def test_sera_senza_novita_niente_email(tmp_path):
    s = servizi()
    esegui_sera(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 20), s)
    assert s.invia.inviate == []


def test_sera_durante_la_seduta_non_aggiorna(tmp_path):
    cfg = config_piccola()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    s = servizi()
    s.adesso = lambda: datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
    esegui_sera(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 20), s)
    ops = leggi_operazioni(tmp_path / "dati" / "operazioni.csv")
    # la seduta del 19 è chiusa (ingresso registrato), quella del 20 no (il crollo non si applica ancora)
    assert all(o.data_ingresso == "2026-10-19" and o.stato != "chiusa" for o in ops)


def test_mattina_chiede_ultima_seduta(tmp_path):
    chieste = []
    s = servizi()
    originale = s.scarica_prezzi

    def prezzi(simboli, anni, oggi, ultima=None):
        chieste.append(ultima)
        return originale(simboli, anni, oggi)

    s.scarica_prezzi = prezzi
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), s)
    assert date(2026, 10, 16) in chieste


def test_sera_stesso_giorno_segue_ingresso_vero(tmp_path):
    """Proposta la mattina del 19, la sera del 19 l'ingresso è all'apertura del 19."""
    cfg = config_piccola()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    ops = leggi_operazioni(tmp_path / "dati" / "operazioni.csv")
    assert all(o.data_segnale == "2026-10-16" for o in ops)

    def barre(simboli, dal):
        indice = pd.bdate_range(end="2026-10-19", periods=40)
        df = pd.DataFrame({"Open": 50.0, "High": 50.5, "Low": 49.5, "Close": 50.0, "Volume": 1.0}, index=indice)
        return {s: df for s in simboli}

    esegui_sera(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi(barre=barre))
    ops = leggi_operazioni(tmp_path / "dati" / "operazioni.csv")
    assert all(o.data_ingresso == "2026-10-19" for o in ops)


def test_prova_contiene_media_di_tutte(tmp_path):
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    prova = json.loads((tmp_path / "dati" / "prova_ITA.json").read_text(encoding="utf-8"))
    assert isinstance(prova["media_tutte"], float)


def test_quantita_solo_mercati_del_conto(tmp_path):
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    schede = {x["mercato"]: x for x in leggi_oggi(tmp_path / "dati" / "oggi.json")["schede"]}
    assert schede["ITA"]["quantita"] is None and schede["USA"]["quantita"] > 0
    assert 0 < schede["USA"]["costo_r"] < 5


def test_studio_non_blocca_operazione_vera(tmp_path):
    cfg = config_piccola()
    esegui_mattina(dataclasses.replace(cfg, soglia_r=100.0), tmp_path / "dati", tmp_path / "sito",
                   date(2026, 10, 19), servizi())
    assert all(o.sotto_soglia for o in leggi_operazioni(tmp_path / "dati" / "operazioni.csv"))
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 20), servizi())
    ops = leggi_operazioni(tmp_path / "dati" / "operazioni.csv")
    assert len(ops) == 4 and sum(not o.sotto_soglia for o in ops) == 2
    # un secondo titolo "solo studio" invece non si apre
    esegui_mattina(dataclasses.replace(cfg, soglia_r=100.0), tmp_path / "dati2", tmp_path / "sito2",
                   date(2026, 10, 19), servizi())
    esegui_mattina(dataclasses.replace(cfg, soglia_r=100.0), tmp_path / "dati2", tmp_path / "sito2",
                   date(2026, 10, 20), servizi())
    assert len(leggi_operazioni(tmp_path / "dati2" / "operazioni.csv")) == 2
