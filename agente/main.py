"""Comandi dell'agente: mattina, sera, tabella, segna."""
import argparse
import dataclasses
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from agente import dati
from agente.archivio import leggi_oggi, salva_oggi
from agente.calendario import ROMA, adesso_roma, borsa_aperta, seduta_chiusa, seduta_precedente
from agente.config import Config, carica_config
from agente.dati import DatiNonDisponibili
from agente.operazione import Operazione
from agente.operazioni import (
    aggiorna_operazioni, aperta_nel_mercato, leggi_operazioni, nuova_operazione, salva_operazioni,
    segna_eseguita,
)
from agente.pagina import disegna_grafico, genera_sito
from agente.posta import email_mattina, email_sera, invia
from agente.scelta import scegli
from agente.spiegazione import Cervello, crea_cervello, giudica_notizie, scrivi_testi
from agente.statistiche import calcola_statistiche, costo_ordine, quantita
from agente.storico_r import costruisci_tabella_r, prova_fuori_campione_r, simula_storico

log = logging.getLogger("agente")

ORA_INIZIO = {"mattina": 7, "sera": 22}
URL_PAGINA = "https://giobo76.github.io/maestro-del-mattino/"
STATI_LEGGIBILI = {"in attesa": "in attesa dell'apertura", "aperta": "aperta", "meta chiusa": "metà già venduta",
                   "uscita domani": "da chiudere all'apertura"}


@dataclass
class Servizi:
    scarica_prezzi: Callable
    scarica_dal: Callable[[list[str], date], dict[str, pd.DataFrame]]
    scarica_notizie: Callable
    cervello: Cervello | None
    cambi: Callable[[date, date], dict[date, float]]
    indici: Callable[[str, date], pd.Series | None]
    invia: Callable[[str, str], bool]
    adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def _chiusure(simbolo: str, dal: date) -> pd.Series | None:
    try:
        return dati.scarica_chiusure(simbolo, dal)
    except DatiNonDisponibili:
        return None


def _cambi(dal: date, al: date) -> dict[date, float]:
    serie = _chiusure("EURUSD=X", dal)
    return {} if serie is None else {g.date(): float(v) for g, v in serie.items()}


def servizi_reali(cfg: Config) -> Servizi:
    chiave = os.environ.get("RESEND_API_KEY")
    return Servizi(
        scarica_prezzi=dati.scarica_prezzi,
        scarica_dal=dati.scarica_dal,
        scarica_notizie=dati.scarica_notizie,
        cervello=crea_cervello(cfg),
        cambi=_cambi,
        indici=_chiusure,
        invia=lambda oggetto, html: invia(oggetto, html, cfg.email_destinatario, chiave),
    )


def deve_partire(comando: str, adesso: datetime, oggi_json: dict | None) -> bool:
    if comando in ("tabella", "segna"):
        return True
    locale = adesso.astimezone(ROMA)
    fatto = (oggi_json or {}).get(f"fatto_{comando}")
    return locale.hour >= ORA_INIZIO[comando] and fatto != locale.date().isoformat()


def esegui_tabella(cfg: Config, cartella_dati: Path, oggi: date, servizi: Servizi) -> None:
    cartella_dati.mkdir(parents=True, exist_ok=True)
    for codice, mercato in cfg.mercati.items():
        log.info("Tabella storica %s: scarico %d anni", codice, cfg.anni_storico)
        try:
            prezzi = servizi.scarica_prezzi(list(mercato.titoli), cfg.anni_storico, oggi)
        except DatiNonDisponibili:
            log.error("Tabella %s non aggiornata: prezzi non disponibili", codice)
            continue
        storico = simula_storico(prezzi, cfg.atr_mult)
        tabella = costruisci_tabella_r(storico, None, cfg.casi_minimi, cfg.casi_virtuali)
        tabella.to_csv(cartella_dati / f"tabella_{codice}.csv")
        prova = prova_fuori_campione_r(storico, cfg.casi_minimi, cfg.casi_virtuali, cfg.soglia_r)
        prova["media_tutte"] = float(tabella.attrs["media"])
        (cartella_dati / f"prova_{codice}.json").write_text(json.dumps(prova, indent=2), encoding="utf-8")
        log.info("Tabella %s: %d situazioni, prova fuori campione %s", codice, len(tabella), prova)


def _leggi_tabella(cartella_dati: Path, codice: str) -> pd.DataFrame:
    return pd.read_csv(cartella_dati / f"tabella_{codice}.csv", index_col="situazione")


def _parole(cartella_dati: Path) -> list[str]:
    percorso = cartella_dati / "parole.json"
    return json.loads(percorso.read_text(encoding="utf-8")) if percorso.exists() else []


def _pubblica(cfg: Config, cartella_dati: Path, cartella_sito: Path, ops: list[Operazione],
              oggi_json: dict, servizi: Servizi) -> None:
    cambi, indici = {}, {}
    iniziate = [o.data_ingresso for o in ops if o.data_ingresso]
    if iniziate:
        dal = date.fromisoformat(min(iniziate))
        cambi = servizi.cambi(dal, date.today())
        for codice, mercato in cfg.mercati.items():
            serie = servizi.indici(mercato.indice, dal)
            if serie is not None:
                indici[codice] = serie
    stat = calcola_statistiche(ops, cfg, cambi, indici)
    prova = {}
    for codice in cfg.mercati:
        percorso = cartella_dati / f"prova_{codice}.json"
        if percorso.exists():
            prova[codice] = json.loads(percorso.read_text(encoding="utf-8"))
    genera_sito(cartella_sito, oggi_json, ops, stat, prova, adesso_roma())


def _cambio_attuale(servizi: Servizi, oggi: date) -> float | None:
    cambi = servizi.cambi(oggi, oggi)
    if not cambi:
        log.warning("Cambio EUR/USD non disponibile")
        return None
    return cambi[max(cambi)]


def esegui_mattina(cfg: Config, cartella_dati: Path, cartella_sito: Path, oggi: date,
                   servizi: Servizi) -> None:
    if not all((cartella_dati / f"tabella_{c}.csv").exists() for c in cfg.mercati):
        esegui_tabella(cfg, cartella_dati, oggi, servizi)
    ops = leggi_operazioni(cartella_dati / "operazioni.csv")
    parole = _parole(cartella_dati)
    schede = []
    for codice, mercato in cfg.mercati.items():
        base = {"mercato": codice, "nome_mercato": mercato.nome, "valuta": mercato.valuta, "nuova": False}
        aperta = aperta_nel_mercato(ops, codice, solo_vere=True)
        studio_aperta = next((op for op in ops if op.mercato == codice and op.stato != "chiusa"
                              and op.sotto_soglia), None)
        if aperta is not None:
            schede.append({**base, "simbolo": None, "posizione_id": aperta.id,
                           "nota": f"Posizione già aperta su {aperta.nome} ({STATI_LEGGIBILI[aperta.stato]}): "
                                   "oggi nessuna nuova operazione su questo mercato."})
            continue
        if not borsa_aperta(mercato.calendario, oggi):
            schede.append({**base, "simbolo": None, "nota": "Borsa chiusa oggi."})
            continue
        if not (cartella_dati / f"tabella_{codice}.csv").exists():
            schede.append({**base, "simbolo": None, "nota": "Dati non disponibili oggi."})
            continue
        try:
            prezzi = servizi.scarica_prezzi(list(mercato.titoli), 1, oggi,
                                            ultima=seduta_precedente(mercato.calendario, oggi))
        except DatiNonDisponibili:
            log.error("Prezzi %s non disponibili", codice)
            schede.append({**base, "simbolo": None, "nota": "Dati non disponibili oggi."})
            continue

        scelta = scegli(
            mercato, prezzi, _leggi_tabella(cartella_dati, codice),
            lambda nome, simbolo, lingua=mercato.lingua_notizie: servizi.scarica_notizie(nome, simbolo, lingua),
            lambda nome, notizie: giudica_notizie(servizi.cervello, nome, notizie),
            cfg.soglia_r, cfg.atr_mult, studio=cfg.modalita_studio)
        scheda = {**dataclasses.asdict(scelta), **base, "grafico": None, "testi": None}
        if scelta.simbolo and scelta.sotto_soglia and studio_aperta is not None:
            # un solo titolo "solo studio" per mercato: non se ne apre un secondo
            schede.append({**base, "simbolo": None, "posizione_id": studio_aperta.id,
                           "nota": f"Oggi nessuna operazione vera. Prosegue lo studio di {studio_aperta.nome}."})
            continue
        if scelta.simbolo:
            lv = scelta.livelli
            grafico = cartella_dati / "grafici" / f"{codice}.png"
            disegna_grafico(prezzi[scelta.simbolo], scelta.nome, grafico, lv)
            cambio = 1.0 if codice == "ITA" else _cambio_attuale(servizi, oggi)
            n = perdita = costo_r = None
            capitale = cfg.ibkr_capitale_eur / max(len(cfg.ibkr_mercati), 1)  # il conto si divide tra i mercati
            if codice in cfg.ibkr_mercati:
                if cambio is None:
                    scelta.nota = (scelta.nota + " Cambio euro/dollaro non disponibile: quantità calcolata "
                                   "con 1 € = 1 $, verificala su IBKR.").strip()
                    cambio = 1.0
                n = quantita(codice, capitale, lv.riferimento, cambio)
                perdita = n * lv.r / cambio
                if perdita:
                    costi = (costo_ordine(codice, capitale, lv.riferimento, cfg.costi, cambio)
                             + 2 * costo_ordine(codice, capitale / 2, lv.riferimento, cfg.costi, cambio))
                    costo_r = costi / perdita
            testi = scrivi_testi(servizi.cervello, {
                "nome": scelta.nome, "mercato": mercato.nome, "resa": scelta.resa, "casi": scelta.casi,
                "pct_stop": scelta.pct_stop, "pct_2r": scelta.pct_2r, "situazione": scelta.situazione,
                "livelli": dataclasses.asdict(lv), "sotto_soglia": scelta.sotto_soglia,
                "notizie": [x.titolo for x in scelta.notizie]}, parole[-30:])
            if testi:
                parole.append(testi["parola"])
            op = nuova_operazione(scelta, seduta_precedente(mercato.calendario, oggi))
            ops.append(op)
            scheda.update(nuova=True, grafico=str(grafico), testi=testi, quantita=n, perdita_massima=perdita,
                          costo_r=costo_r, posizione_id=op.id, nota=scelta.nota, capitale=capitale)
        log.info("%s: scelto %s (%s)", codice, scelta.simbolo, scelta.nota or "ok")
        schede.append(scheda)

    salva_operazioni(ops, cartella_dati / "operazioni.csv")
    (cartella_dati / "parole.json").write_text(json.dumps(parole, ensure_ascii=False), encoding="utf-8")
    oggi_json = {"data": oggi.isoformat(), "schede": schede, "fatto_mattina": oggi.isoformat(), "fatto_sera": None}
    salva_oggi(cartella_dati / "oggi.json", oggi_json)
    _pubblica(cfg, cartella_dati, cartella_sito, ops, leggi_oggi(cartella_dati / "oggi.json"), servizi)
    email = email_mattina(schede, URL_PAGINA)
    if email:
        servizi.invia(*email)


def esegui_sera(cfg: Config, cartella_dati: Path, cartella_sito: Path, oggi: date,
                servizi: Servizi) -> None:
    ops = leggi_operazioni(cartella_dati / "operazioni.csv")
    messaggi = aggiorna_operazioni(
        ops, servizi.scarica_dal, oggi,
        chiusa=lambda m, giorno: seduta_chiusa(cfg.mercati[m].calendario, giorno, servizi.adesso()))
    salva_operazioni(ops, cartella_dati / "operazioni.csv")
    oggi_json = leggi_oggi(cartella_dati / "oggi.json") or {"data": oggi.isoformat(), "schede": []}
    oggi_json["fatto_sera"] = oggi.isoformat()
    salva_oggi(cartella_dati / "oggi.json", oggi_json)
    _pubblica(cfg, cartella_dati, cartella_sito, ops, oggi_json, servizi)
    email = email_sera(messaggi, URL_PAGINA)
    if email:
        servizi.invia(*email)


def esegui_segna(cfg: Config, cartella_dati: Path, cartella_sito: Path, chi: str, eseguita: bool,
                 servizi: Servizi) -> None:
    """Registra se l'ordine proposto è stato eseguito davvero su IBKR."""
    ops = leggi_operazioni(cartella_dati / "operazioni.csv")
    op = segna_eseguita(ops, chi, eseguita)
    log.info("%s (%s) segnata come %s", op.nome, op.id, "eseguita" if eseguita else "non eseguita")
    salva_operazioni(ops, cartella_dati / "operazioni.csv")
    oggi_json = leggi_oggi(cartella_dati / "oggi.json") or {"data": date.today().isoformat(), "schede": []}
    _pubblica(cfg, cartella_dati, cartella_sito, ops, oggi_json, servizi)


def _scrivi_output(nessun_lavoro: bool) -> None:
    percorso = os.environ.get("GITHUB_OUTPUT")
    if percorso:
        with open(percorso, "a", encoding="utf-8") as f:
            f.write(f"nessun_lavoro={'true' if nessun_lavoro else 'false'}\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m agente")
    parser.add_argument("comando", choices=["mattina", "sera", "tabella", "segna"])
    parser.add_argument("--operazione", help="segna: mercato (ITA/USA, la più recente) o id dell'operazione")
    parser.add_argument("--eseguita", choices=["si", "no"], help="segna: hai eseguito l'ordine su IBKR?")
    parser.add_argument("--forza", action="store_true", help="ignora l'orario e i lavori già fatti")
    parser.add_argument("--giorno", type=date.fromisoformat, help="data da usare (prove), AAAA-MM-GG")
    parser.add_argument("--dati", type=Path, default=Path("dati"))
    parser.add_argument("--sito", type=Path, default=Path("sito"))
    argomenti = parser.parse_args(argv)
    if argomenti.comando == "segna" and not (argomenti.operazione and argomenti.eseguita):
        parser.error("segna richiede --operazione e --eseguita")
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
        _pubblica(cfg, argomenti.dati, argomenti.sito, leggi_operazioni(argomenti.dati / "operazioni.csv"),
                  oggi_json, servizi)
    elif argomenti.comando == "segna":
        esegui_segna(cfg, argomenti.dati, argomenti.sito, argomenti.operazione, argomenti.eseguita == "si",
                     servizi)
    elif argomenti.comando == "mattina":
        esegui_mattina(cfg, argomenti.dati, argomenti.sito, oggi, servizi)
    else:
        esegui_sera(cfg, argomenti.dati, argomenti.sito, oggi, servizi)
    _scrivi_output(False)
    return 0
