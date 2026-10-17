"""Comandi dell'agente: mattina, sera, tabella."""
import argparse
import dataclasses
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from agente import dati
from agente.archivio import (
    aggiungi_previsioni, leggi_oggi, leggi_previsioni, salva_oggi, salva_previsioni,
)
from agente.calendario import ROMA, adesso_roma, borsa_aperta
from agente.config import Config, carica_config
from agente.dati import DatiNonDisponibili
from agente.pagina import disegna_grafico, genera_sito
from agente.probabilita import costruisci_tabella, prepara_storico, prova_fuori_campione
from agente.scelta import scegli
from agente.spiegazione import Cervello, crea_cervello, giudica_notizie, scrivi_testi
from agente.statistiche import calcola_statistiche
from agente.verifica import registra_esiti

log = logging.getLogger("agente")

ORA_INIZIO = {"mattina": 7, "sera": 22}


@dataclass
class Servizi:
    scarica_prezzi: Callable
    scarica_prezzi_giorno: Callable
    scarica_notizie: Callable
    cervello: Cervello | None
    cambi: Callable[[date, date], dict[date, float]]
    indici: Callable[[str, date], pd.Series | None]


def _chiusure(simbolo: str, dal: date) -> pd.Series | None:
    try:
        tabella = dati.scarica_prezzi([simbolo], 1, date.today() + timedelta(days=1))
    except DatiNonDisponibili:
        return None
    df = tabella.get(simbolo)
    return None if df is None else df.loc[df.index >= pd.Timestamp(dal - timedelta(days=7)), "Close"]


def _cambi(dal: date, al: date) -> dict[date, float]:
    serie = _chiusure("EURUSD=X", dal)
    return {} if serie is None else {g.date(): float(v) for g, v in serie.items()}


def servizi_reali(cfg: Config) -> Servizi:
    return Servizi(
        scarica_prezzi=dati.scarica_prezzi,
        scarica_prezzi_giorno=dati.scarica_prezzi_giorno,
        scarica_notizie=dati.scarica_notizie,
        cervello=crea_cervello(cfg),
        cambi=_cambi,
        indici=_chiusure,
    )


def deve_partire(comando: str, adesso: datetime, oggi_json: dict | None) -> bool:
    if comando == "tabella":
        return True
    locale = adesso.astimezone(ROMA)
    fatto = (oggi_json or {}).get(f"fatto_{comando}")
    return locale.hour >= ORA_INIZIO[comando] and fatto != locale.date().isoformat()


def esegui_tabella(cfg: Config, cartella_dati: Path, oggi: date, servizi: Servizi) -> None:
    cartella_dati.mkdir(parents=True, exist_ok=True)
    for codice, mercato in cfg.mercati.items():
        log.info("Tabella storica %s: scarico %d anni", codice, cfg.anni_storico)
        prezzi = servizi.scarica_prezzi(list(mercato.titoli), cfg.anni_storico, oggi)
        storico = prepara_storico(prezzi)
        tabella = costruisci_tabella(storico, None, cfg.casi_minimi, cfg.casi_virtuali)
        tabella.to_csv(cartella_dati / f"tabella_{codice}.csv")
        prova = prova_fuori_campione(storico, cfg.casi_minimi, cfg.casi_virtuali, cfg.soglia_prob)
        (cartella_dati / f"prova_{codice}.json").write_text(json.dumps(prova, indent=2), encoding="utf-8")
        log.info("Tabella %s: %d situazioni, prova fuori campione %s", codice, len(tabella), prova)


def _leggi_tabella(cartella_dati: Path, codice: str) -> pd.DataFrame:
    return pd.read_csv(cartella_dati / f"tabella_{codice}.csv", index_col="situazione")


def _parole(cartella_dati: Path) -> list[str]:
    percorso = cartella_dati / "parole.json"
    return json.loads(percorso.read_text(encoding="utf-8")) if percorso.exists() else []


def _pubblica(cfg: Config, cartella_dati: Path, cartella_sito: Path, prev: pd.DataFrame,
              oggi_json: dict, servizi: Servizi) -> None:
    cambi, indici = {}, {}
    conclusi = prev[prev["salito"].notna()]
    if len(conclusi):
        dal = date.fromisoformat(conclusi["data"].min())
        al = date.fromisoformat(conclusi["data"].max())
        cambi = servizi.cambi(dal, al)
        for codice, mercato in cfg.mercati.items():
            serie = servizi.indici(mercato.indice, dal)
            if serie is not None:
                indici[codice] = serie
    stat = calcola_statistiche(prev, cfg, cambi, indici)
    prova = {}
    for codice in cfg.mercati:
        percorso = cartella_dati / f"prova_{codice}.json"
        if percorso.exists():
            prova[codice] = json.loads(percorso.read_text(encoding="utf-8"))
    genera_sito(cartella_sito, oggi_json, prev, stat, prova, adesso_roma())


def esegui_mattina(cfg: Config, cartella_dati: Path, cartella_sito: Path, oggi: date,
                   servizi: Servizi) -> None:
    if not all((cartella_dati / f"tabella_{c}.csv").exists() for c in cfg.mercati):
        esegui_tabella(cfg, cartella_dati, oggi, servizi)
    parole = _parole(cartella_dati)
    schede, scelte = [], []
    for codice, mercato in cfg.mercati.items():
        base = {"mercato": codice, "nome_mercato": mercato.nome, "valuta": mercato.valuta}
        if not borsa_aperta(mercato.calendario, oggi):
            schede.append({**base, "simbolo": None, "nota": "Borsa chiusa oggi."})
            continue
        try:
            prezzi = servizi.scarica_prezzi(list(mercato.titoli), 1, oggi)
        except DatiNonDisponibili:
            log.error("Prezzi %s non disponibili", codice)
            schede.append({**base, "simbolo": None, "nota": "Dati non disponibili oggi."})
            continue

        scelta = scegli(
            mercato, prezzi, _leggi_tabella(cartella_dati, codice),
            lambda nome, simbolo, lingua=mercato.lingua_notizie: servizi.scarica_notizie(nome, simbolo, lingua),
            lambda nome, notizie: giudica_notizie(servizi.cervello, nome, notizie),
            cfg.soglia_prob)
        scelte.append(scelta)
        scheda = {**dataclasses.asdict(scelta), **base, "grafico": None, "testi": None}
        if scelta.simbolo:
            df = prezzi[scelta.simbolo]
            grafico = cartella_dati / "grafici" / f"{codice}.png"
            disegna_grafico(df, scelta.nome, grafico)
            scheda["grafico"] = str(grafico)
            scheda["prezzo_ieri"] = float(df["Close"].iloc[-1])
            testi = scrivi_testi(servizi.cervello, {
                "nome": scelta.nome, "mercato": mercato.nome, "prob": scelta.prob, "casi": scelta.casi,
                "rend_medio": scelta.rend_medio, "situazione": scelta.situazione,
                "notizie": [n.titolo for n in scelta.notizie]}, parole[-30:])
            scheda["testi"] = testi
            if testi:
                parole.append(testi["parola"])
        log.info("%s: scelto %s (%s)", codice, scelta.simbolo, scelta.nota or "ok")
        schede.append(scheda)

    prev = aggiungi_previsioni(leggi_previsioni(cartella_dati / "previsioni.csv"), oggi, scelte)
    salva_previsioni(prev, cartella_dati / "previsioni.csv")
    (cartella_dati / "parole.json").write_text(json.dumps(parole, ensure_ascii=False), encoding="utf-8")
    oggi_json = {"data": oggi.isoformat(), "schede": schede, "fatto_mattina": oggi.isoformat(), "fatto_sera": None}
    salva_oggi(cartella_dati / "oggi.json", oggi_json)
    _pubblica(cfg, cartella_dati, cartella_sito, prev, leggi_oggi(cartella_dati / "oggi.json"), servizi)


def esegui_sera(cfg: Config, cartella_dati: Path, cartella_sito: Path, oggi: date,
                servizi: Servizi) -> None:
    prev = registra_esiti(leggi_previsioni(cartella_dati / "previsioni.csv"),
                          servizi.scarica_prezzi_giorno, oggi)
    salva_previsioni(prev, cartella_dati / "previsioni.csv")
    oggi_json = leggi_oggi(cartella_dati / "oggi.json") or {"data": oggi.isoformat(), "schede": []}
    oggi_json["fatto_sera"] = oggi.isoformat()
    salva_oggi(cartella_dati / "oggi.json", oggi_json)
    _pubblica(cfg, cartella_dati, cartella_sito, prev, oggi_json, servizi)


def _scrivi_output(nessun_lavoro: bool) -> None:
    percorso = os.environ.get("GITHUB_OUTPUT")
    if percorso:
        with open(percorso, "a", encoding="utf-8") as f:
            f.write(f"nessun_lavoro={'true' if nessun_lavoro else 'false'}\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m agente")
    parser.add_argument("comando", choices=["mattina", "sera", "tabella"])
    parser.add_argument("--forza", action="store_true", help="ignora l'orario e i lavori già fatti")
    parser.add_argument("--giorno", type=date.fromisoformat, help="data da usare (prove), AAAA-MM-GG")
    parser.add_argument("--dati", type=Path, default=Path("dati"))
    parser.add_argument("--sito", type=Path, default=Path("sito"))
    argomenti = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    adesso = adesso_roma()
    if not argomenti.forza and not deve_partire(argomenti.comando, adesso, leggi_oggi(argomenti.dati / "oggi.json")):
        log.info("Nessun lavoro da fare ora per '%s'", argomenti.comando)
        _scrivi_output(True)
        return 0

    cfg = carica_config()
    oggi = argomenti.giorno or adesso.date()
    servizi = servizi_reali(cfg)
    if argomenti.comando == "tabella":
        esegui_tabella(cfg, argomenti.dati, oggi, servizi)
        oggi_json = leggi_oggi(argomenti.dati / "oggi.json") or {"data": oggi.isoformat(), "schede": []}
        _pubblica(cfg, argomenti.dati, argomenti.sito, leggi_previsioni(argomenti.dati / "previsioni.csv"),
                  oggi_json, servizi)
    elif argomenti.comando == "mattina":
        esegui_mattina(cfg, argomenti.dati, argomenti.sito, oggi, servizi)
    else:
        esegui_sera(cfg, argomenti.dati, argomenti.sito, oggi, servizi)
    _scrivi_output(False)
    return 0
