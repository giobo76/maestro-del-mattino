import dataclasses
import json
from datetime import date, datetime, timezone

import pytest

from agente.archivio import leggi_oggi, leggi_previsioni
from agente.config import carica_config
from agente.dati import DatiNonDisponibili
from agente.main import Servizi, deve_partire, esegui_mattina, esegui_sera
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
    return dataclasses.replace(cfg, mercati=mercati, soglia_prob=0.0)


def servizi(rotto=None):
    def prezzi(simboli, anni, oggi):
        if rotto and rotto in simboli[0]:
            raise DatiNonDisponibili("giù")
        return {s: passeggiata(400 if anni > 1 else 250, seme=i, inizio="2025-01-01") for i, s in enumerate(simboli)}

    return Servizi(
        scarica_prezzi=prezzi,
        scarica_prezzi_giorno=lambda simboli, giorno: {s: (10.0, 10.5) for s in simboli},
        scarica_notizie=lambda nome, simbolo, lingua: [],
        cervello=Cervello(),
        cambi=lambda dal, al: {},
        indici=lambda simbolo, dal: None,
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


def test_mattina_completa(tmp_path):
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    prev = leggi_previsioni(tmp_path / "dati" / "previsioni.csv")
    assert set(prev["mercato"]) == {"ITA", "USA"}
    oggi = leggi_oggi(tmp_path / "dati" / "oggi.json")
    assert oggi["fatto_mattina"] == "2026-10-19" and len(oggi["schede"]) == 2
    assert oggi["schede"][0]["testi"]["perche"] == "Spiegazione."
    assert (tmp_path / "dati" / "tabella_ITA.csv").exists()
    assert (tmp_path / "dati" / "grafici" / "ITA.png").exists()
    html = (tmp_path / "sito" / "index.html").read_text(encoding="utf-8")
    assert any(nome in html for nome in ("Xray", "Yank", "Zulu"))


def test_mercato_chiuso_saltato(tmp_path):
    esegui_mattina(config_piccola(), tmp_path / "dati", tmp_path / "sito", date(2026, 11, 26), servizi())
    prev = leggi_previsioni(tmp_path / "dati" / "previsioni.csv")
    assert list(prev["mercato"]) == ["ITA"]
    scheda_usa = [s for s in leggi_oggi(tmp_path / "dati" / "oggi.json")["schede"] if s["mercato"] == "USA"][0]
    assert scheda_usa["nota"] == "Borsa chiusa oggi."


def test_dati_non_disponibili_un_mercato(tmp_path):
    cfg = config_piccola()
    s = servizi()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), s)  # crea le tabelle
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 20), servizi(rotto="X"))
    prev = leggi_previsioni(tmp_path / "dati" / "previsioni.csv")
    assert list(prev[prev["data"] == "2026-10-20"]["mercato"]) == ["ITA"]
    schede = leggi_oggi(tmp_path / "dati" / "oggi.json")["schede"]
    assert [x["nota"] for x in schede if x["mercato"] == "USA"] == ["Dati non disponibili oggi."]


def test_sera_compila_esiti(tmp_path):
    cfg = config_piccola()
    esegui_mattina(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    esegui_sera(cfg, tmp_path / "dati", tmp_path / "sito", date(2026, 10, 19), servizi())
    prev = leggi_previsioni(tmp_path / "dati" / "previsioni.csv")
    assert prev["salito"].all()
    assert leggi_oggi(tmp_path / "dati" / "oggi.json")["fatto_sera"] == "2026-10-19"
    assert "Statistiche" in (tmp_path / "sito" / "index.html").read_text(encoding="utf-8")
