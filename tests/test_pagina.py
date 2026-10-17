from datetime import date, datetime
from pathlib import Path

from agente.archivio import aggiungi_previsioni, leggi_previsioni
from agente.config import carica_config
from agente.pagina import FOOTER, disegna_grafico, genera_sito
from agente.scelta import Scelta
from agente.statistiche import calcola_statistiche
from tests.aiuti import passeggiata

CFG = carica_config("config.yaml")
PROVA = {"ITA": {"dal": "2025-10-16", "al": "2026-10-16", "giorni_con_scelta": 120,
                 "prob_media_annunciata": 0.57, "percentuale_reale": 0.54, "rend_medio": 0.001}}


def scheda(**cambi):
    base = {"mercato": "ITA", "nome_mercato": "Borsa Italiana", "valuta": "EUR", "simbolo": "ENI.MI",
            "nome": "Eni", "prob": 0.57, "casi": 142, "rend_medio": 0.004, "prezzo_ieri": 25.95,
            "situazione": "trend=su|rsi=normale|macd=rialzo|vol=alto|rottura=no|giorno=normale",
            "giudizio_notizie": "neutro", "nota": "", "scartati": [], "grafico": None,
            "notizie": [{"titolo": "Eni alza le stime", "link": "http://x", "fonte": "Sole", "data": "2026-10-16"}],
            "testi": {"perche": "Il titolo è in salita.", "rischio": "Dati USA alle 14:30.",
                      "parola": "MACD", "parola_spiegazione": "Un indicatore di tendenza."}}
    base.update(cambi)
    return base


def genera(tmp_path, schede, prev=None):
    prev = leggi_previsioni("non-esiste.csv") if prev is None else prev
    stat = calcola_statistiche(prev, CFG, {}, {})
    percorso = genera_sito(tmp_path / "sito", {"data": "2026-10-16", "schede": schede}, prev, stat, PROVA,
                           datetime(2026, 10, 16, 7, 31))
    return percorso.read_text(encoding="utf-8")


def test_pagina_contiene_scheda(tmp_path):
    html = genera(tmp_path, [scheda()])
    assert "Eni" in html and "57,0%" in html and "142 casi" in html
    assert "Il titolo è in salita." in html and "MACD" in html
    assert FOOTER == "Strumento personale a scopo didattico. Non è una consulenza finanziaria."
    assert FOOTER in html
    assert "54,0%" in html  # prova fuori campione


def test_pagina_sotto_soglia(tmp_path):
    html = genera(tmp_path, [scheda(sotto_soglia=True, nota="Sotto soglia: solo per studio, non per investire.")])
    assert "Sotto soglia: solo per studio, non per investire." in html and "Eni" in html


def test_pagina_mostra_data_analisi(tmp_path):
    html = genera(tmp_path, [scheda()])
    assert "Analisi del 16/10/2026" in html and "Ultima chiusura" in html
    assert "non c'è una nuova analisi" not in html


def test_pagina_analisi_vecchia(tmp_path):
    prev = leggi_previsioni("non-esiste.csv")
    stat = calcola_statistiche(prev, CFG, {}, {})
    html = genera_sito(tmp_path / "sito", {"data": "2026-10-15", "schede": [scheda()]}, prev, stat, PROVA,
                       datetime(2026, 10, 16, 22, 31)).read_text(encoding="utf-8")
    assert "Oggi non c'è una nuova analisi (borsa chiusa o problema tecnico)" in html


def test_pagina_senza_testi(tmp_path):
    assert "Spiegazione non disponibile oggi" in genera(tmp_path, [scheda(testi=None)])


def test_pagina_nessuna_scelta(tmp_path):
    nota = "Oggi nessun titolo supera il 55% di probabilità storica: meglio stare fermi."
    html = genera(tmp_path, [scheda(simbolo=None, nome=None, prob=None, casi=None, testi=None, nota=nota)])
    assert nota in html


def test_pagina_statistiche_vuote(tmp_path):
    assert "Ancora nessun risultato" in genera(tmp_path, [scheda()])


def test_pagina_storico(tmp_path):
    prev = aggiungi_previsioni(leggi_previsioni("non-esiste.csv"), date(2026, 10, 15),
                               [Scelta("ITA", "ENI.MI", "Eni", 0.57, 142, 0.004, "trend=su")])
    assert "in attesa" in genera(tmp_path, [scheda()], prev)


def test_storico_segna_studio(tmp_path):
    s = Scelta("ITA", "ENI.MI", "Eni", 0.52, 142, 0.004, "trend=su")
    s.sotto_soglia = True
    prev = aggiungi_previsioni(leggi_previsioni("non-esiste.csv"), date(2026, 10, 15), [s])
    assert "52,0% (studio)" in genera(tmp_path, [scheda()], prev)


def test_grafico_creato(tmp_path):
    percorso = tmp_path / "grafico.png"
    disegna_grafico(passeggiata(120), "Eni", percorso)
    assert percorso.exists() and percorso.stat().st_size > 1000


def test_grafico_copiato(tmp_path):
    origine = tmp_path / "ITA.png"
    disegna_grafico(passeggiata(120), "Eni", origine)
    html = genera(tmp_path, [scheda(grafico=str(origine))])
    assert (tmp_path / "sito" / "grafici" / "ITA.png").exists()
    assert 'src="grafici/ITA.png"' in html
