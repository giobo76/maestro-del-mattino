"""Archivio delle operazioni (operazioni.csv) e controllo serale."""
import dataclasses
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from agente.dati import DatiNonDisponibili
from agente.operazione import Operazione, avanza, risultato_r
from agente.scelta import Scelta

log = logging.getLogger(__name__)

CAMPI = [f.name for f in dataclasses.fields(Operazione)]
TIPI = {f.name: f.type for f in dataclasses.fields(Operazione)}


@dataclass
class Messaggio:
    operazione_id: str
    nome: str
    evento: str
    testo: str


def _valore(campo: str, valore):
    if pd.isna(valore):
        return 0 if campo == "giorni_senza_dati" else None
    tipo = str(TIPI[campo])
    if "bool" in tipo:
        return str(valore).lower() == "true"
    if campo in ("casi", "giorni_senza_dati"):
        return int(valore)
    if "float" in tipo:
        return float(valore)
    return str(valore)


def leggi_operazioni(percorso) -> list[Operazione]:
    if not Path(percorso).exists():
        return []
    tabella = pd.read_csv(percorso, dtype=str, keep_default_na=False, na_values=[""])
    return [Operazione(**{c: _valore(c, riga[c]) for c in CAMPI}) for _, riga in tabella.iterrows()]


def salva_operazioni(ops: list[Operazione], percorso) -> None:
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    righe = [dataclasses.asdict(op) for op in sorted(ops, key=lambda o: (o.data_segnale, o.mercato))]
    pd.DataFrame(righe, columns=CAMPI).to_csv(percorso, index=False)


def nuova_operazione(scelta: Scelta, giorno: date) -> Operazione:
    lv = scelta.livelli
    return Operazione(
        id=f"{giorno.isoformat()}-{scelta.mercato}", mercato=scelta.mercato, simbolo=scelta.simbolo,
        nome=scelta.nome, data_segnale=giorno.isoformat(), riferimento=lv.riferimento, r=lv.r,
        stop_iniziale=lv.stop, pareggio=lv.pareggio, prima_uscita=lv.prima_uscita,
        sotto_soglia=scelta.sotto_soglia, resa_attesa=scelta.resa, casi=scelta.casi)


def aperta_nel_mercato(ops: list[Operazione], mercato: str) -> Operazione | None:
    return next((op for op in ops if op.mercato == mercato and op.stato != "chiusa"), None)


def _prezzo(op: Operazione, valore: float) -> str:
    return f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".") + \
        (" €" if op.mercato == "ITA" else " $")


def _r(valore: float) -> str:
    return f"{valore:+.2f}R".replace(".", ",").replace("-", "−")


def testo_evento(op: Operazione, evento: str) -> str:
    n = op.nome
    if evento == "ingresso":
        return f"▶️ {n}: operazione partita all'apertura a {_prezzo(op, op.ingresso)}."
    if evento == "apertura_sotto_stop":
        return f"🔴 {n}: ha aperto sotto lo stop, chiusa subito a {_prezzo(op, op.prezzo_uscita)} ({_r(risultato_r(op))})."
    if evento == "stop":
        return (f"🔴 {n}: stop toccato a {_prezzo(op, op.prezzo_uscita)}. "
                f"Operazione chiusa a {_r(risultato_r(op))}.")
    if evento == "pareggio_stop":
        return f"➖ {n}: tornato al prezzo d'ingresso, chiusa a pareggio ({_r(risultato_r(op))})."
    if evento == "pareggio":
        return (f"🟡 {n}: +1R raggiunto. Controlla che lo stop sia salito al prezzo d'ingresso "
                f"({_prezzo(op, op.ingresso)}).")
    if evento == "prima_uscita":
        return f"🟢 {n}: +2R raggiunto, metà venduta a {_prezzo(op, op.prezzo_meta)}. Il resto corre."
    if evento == "sotto_media":
        return f"📉 {n}: ha chiuso sotto la media a 20 giorni. Domattina vendi il resto all'apertura."
    if evento == "uscita_finale":
        return (f"✅ {n}: resto venduto a {_prezzo(op, op.prezzo_uscita)}. "
                f"Risultato finale {_r(risultato_r(op))}.")
    if evento == "senza_dati":
        return (f"⚠️ {n}: nessun dato da Yahoo da {op.giorni_senza_dati} sere. "
                "Controlla il titolo sull'app di IBKR.")
    return f"{n}: {evento}"


def aggiorna_operazioni(ops: list[Operazione],
                        barre: Callable[[list[str], date], dict[str, pd.DataFrame]],
                        oggi: date, chiusa: Callable[[str, date], bool]) -> list[Messaggio]:
    attive = [op for op in ops if op.stato != "chiusa"]
    if not attive:
        return []
    dal = min(date.fromisoformat(op.data_segnale) for op in attive) - timedelta(days=45)
    try:
        dati = barre(sorted({op.simbolo for op in attive}), dal)
    except DatiNonDisponibili:
        log.error("Barre non disponibili: operazioni non aggiornate stasera")
        dati = {}

    messaggi = []
    for op in attive:
        df = dati.get(op.simbolo)
        if df is None or df.empty:
            op.giorni_senza_dati += 1
            if op.giorni_senza_dati >= 2:
                messaggi.append(Messaggio(op.id, op.nome, "senza_dati", testo_evento(op, "senza_dati")))
            continue
        op.giorni_senza_dati = 0
        sma20 = df["Close"].rolling(20).mean()
        dopo = op.ultimo_giorno or op.data_segnale
        for giorno, riga in df.iterrows():
            g = giorno.date()
            if g.isoformat() <= dopo or g > oggi or not chiusa(op.mercato, g):
                continue
            eventi = avanza(op, g.isoformat(), riga["Open"], riga["High"], riga["Low"], riga["Close"],
                            sma20.loc[giorno])
            messaggi += [Messaggio(op.id, op.nome, e, testo_evento(op, e)) for e in eventi]
            if op.stato == "chiusa":
                break
    return messaggi
