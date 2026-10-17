from datetime import datetime

import pandas as pd

from agente.config import carica_config
from agente.operazione import Livelli, Operazione, avanza
from agente.pagina import FOOTER, disegna_grafico, genera_sito
from agente.statistiche import calcola_statistiche
from tests.aiuti import passeggiata

CFG = carica_config("config.yaml")
PROVA = {"ITA": {"dal": "2025-10-16", "al": "2026-10-16", "operazioni": 20, "ancora_aperte": 1,
                 "resa_annunciata": 0.25, "resa_reale": -0.12, "pct_stop": 0.5, "pct_2r": 0.2}}
LIVELLI = {"riferimento": 100.0, "r": 4.0, "stop": 96.0, "pareggio": 104.0, "prima_uscita": 108.0}


def scheda(**cambi):
    base = {"mercato": "ITA", "nome_mercato": "Borsa Italiana", "valuta": "EUR", "nuova": True,
            "simbolo": "CPR.MI", "nome": "Campari", "resa": 0.25, "casi": 140, "pct_stop": 0.41,
            "pct_2r": 0.33, "situazione": "trend=su|rsi=normale|macd=rialzo|vol=alto|rottura=no|giorno=normale",
            "livelli": LIVELLI, "quantita": 1, "perdita_massima": 4.0, "giudizio_notizie": "neutro",
            "nota": "", "scartati": [], "grafico": None, "sotto_soglia": False,
            "notizie": [{"titolo": "Campari cresce", "link": "http://x", "fonte": "Sole", "data": "2026-10-16"}],
            "testi": {"perche": "Il titolo è in salita.", "rischio": "Se scatta lo stop perdi il 4%.",
                      "parola": "ATR", "parola_spiegazione": "Il movimento medio."}}
    base.update(cambi)
    return base


def operazione(giorni=(), inizio="2026-10-16", studio=False):
    op = Operazione(f"{inizio}-ITA", "ITA", "CPR.MI", "Campari", inizio, 100.0, 4.0, 96.0, 104.0, 108.0,
                    studio, 0.25, 140)
    for i, g in enumerate(giorni):
        avanza(op, str((pd.Timestamp(inizio) + pd.Timedelta(days=i + 3)).date()), *g)
    return op


def genera(tmp_path, schede, ops=(), data="2026-10-16", aggiornato=datetime(2026, 10, 16, 7, 31)):
    stat = calcola_statistiche(list(ops), CFG, {}, {})
    return genera_sito(tmp_path / "sito", {"data": data, "schede": schede}, list(ops), stat, PROVA,
                       aggiornato).read_text(encoding="utf-8")


def test_scheda_livelli(tmp_path):
    html = genera(tmp_path, [scheda()])
    for testo in ("Campari", "96,00 €", "104,00 €", "108,00 €", "+0,25R", "140 operazioni", "41%",
                  "Il titolo è in salita.", FOOTER, "Analisi del 16/10/2026", "Ultima chiusura"):
        assert testo in html, testo
    assert "−0,12R" in html  # prova fuori campione


def test_scheda_studio(tmp_path):
    html = genera(tmp_path, [scheda(sotto_soglia=True, nota="Sotto soglia: solo per studio, non per investire.")])
    assert "solo studio" in html


def test_quantita_italia_zero(tmp_path):
    assert "con 100 € non puoi comprarne nemmeno una" in genera(tmp_path, [scheda(quantita=0)])


def test_scheda_posizione_aperta(tmp_path):
    op = operazione([(100, 105, 99, 104, 0)])
    html = genera(tmp_path, [{"mercato": "ITA", "nome_mercato": "Borsa Italiana", "valuta": "EUR",
                              "nuova": False, "simbolo": None, "posizione_id": op.id,
                              "nota": "Posizione già aperta su Campari: oggi nessuna nuova operazione."}], [op])
    assert "Posizione già aperta su Campari" in html
    assert "Posizioni aperte" in html and "+1,00R" in html  # ultimo prezzo 104


def test_storico_risultato_r(tmp_path):
    chiusa = operazione([(100, 101, 95, 96, 0)])
    html = genera(tmp_path, [scheda()], [chiusa])
    assert "−1,00R" in html and "stop loss" in html


def test_statistiche_vuote(tmp_path):
    assert "Ancora nessuna operazione chiusa" in genera(tmp_path, [scheda()])


def test_testi_mancanti(tmp_path):
    assert "Spiegazione non disponibile oggi" in genera(tmp_path, [scheda(testi=None)])


def test_nessuna_scelta(tmp_path):
    nota = "Oggi nessun titolo ha una resa storica di almeno +0,10R: meglio stare fermi."
    assert nota in genera(tmp_path, [{"mercato": "ITA", "nome_mercato": "Borsa Italiana", "valuta": "EUR",
                                      "simbolo": None, "nota": nota}])


def test_analisi_vecchia(tmp_path):
    html = genera(tmp_path, [scheda()], data="2026-10-15")
    assert "Oggi non c'è una nuova analisi (borsa chiusa o problema tecnico)" in html


def test_grafico_con_livelli(tmp_path):
    percorso = tmp_path / "g.png"
    disegna_grafico(passeggiata(120), "Campari", percorso, Livelli(100, 4, 96, 104, 108))
    assert percorso.exists() and percorso.stat().st_size > 1000


def test_grafico_copiato(tmp_path):
    origine = tmp_path / "ITA.png"
    disegna_grafico(passeggiata(120), "Campari", origine)
    html = genera(tmp_path, [scheda(grafico=str(origine))])
    assert (tmp_path / "sito" / "grafici" / "ITA.png").exists() and 'src="grafici/ITA.png"' in html
