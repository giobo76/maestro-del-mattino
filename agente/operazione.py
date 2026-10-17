"""Un'operazione: livelli e regole giorno per giorno.

Le stesse regole valgono per la simulazione sul passato e per le operazioni vere.
Caso peggiore: lo stop si controlla prima degli obiettivi e il pareggio protegge dal giorno dopo.
"""
from dataclasses import dataclass

import pandas as pd

from agente.segnali import calcola_indicatori


@dataclass
class Livelli:
    riferimento: float
    r: float
    stop: float
    pareggio: float
    prima_uscita: float


@dataclass
class Operazione:
    id: str
    mercato: str
    simbolo: str
    nome: str
    data_segnale: str
    riferimento: float
    r: float
    stop_iniziale: float
    pareggio: float
    prima_uscita: float
    sotto_soglia: bool
    resa_attesa: float
    casi: int
    stato: str = "in attesa"
    ingresso: float | None = None
    data_ingresso: str | None = None
    stop: float | None = None
    pareggio_attivo: bool = False
    prezzo_meta: float | None = None
    data_meta: str | None = None
    prezzo_uscita: float | None = None
    data_uscita: str | None = None
    ultimo_giorno: str | None = None
    ultimo_prezzo: float | None = None
    motivo: str | None = None
    giorni_senza_dati: int = 0


def livelli_da(riferimento: float, atr: float, atr_mult: float) -> Livelli | None:
    if pd.isna(atr) or pd.isna(riferimento) or atr <= 0:
        return None
    r = atr_mult * atr
    return Livelli(riferimento, r, riferimento - r, riferimento + r, riferimento + 2 * r)


def calcola_livelli(prezzi: pd.DataFrame, atr_mult: float) -> Livelli | None:
    ultima = calcola_indicatori(prezzi).iloc[-1]
    return livelli_da(float(ultima["Close"]), float(ultima["atr14"]), atr_mult)


def _chiudi(op: Operazione, prezzo: float, giorno: str, motivo: str) -> None:
    op.prezzo_uscita, op.data_uscita, op.motivo, op.stato = prezzo, giorno, motivo, "chiusa"


def avanza(op: Operazione, giorno: str, o: float, h: float, l: float, c: float, sma20: float) -> list[str]:
    if op.stato == "chiusa":
        return []
    eventi = []
    op.ultimo_giorno, op.ultimo_prezzo = giorno, c

    if op.stato == "in attesa":
        op.ingresso, op.data_ingresso, op.stop, op.stato = o, giorno, op.stop_iniziale, "aperta"
        eventi.append("ingresso")
        if o <= op.stop_iniziale:
            _chiudi(op, o, giorno, "apertura sotto lo stop")
            return eventi + ["apertura_sotto_stop"]

    if op.stato == "uscita domani":
        _chiudi(op, o, giorno, "chiusura sotto la media a 20")
        return eventi + ["uscita_finale"]

    if l <= op.stop:
        evento = "pareggio_stop" if op.pareggio_attivo else "stop"
        _chiudi(op, min(o, op.stop), giorno, "stop a pareggio" if op.pareggio_attivo else "stop loss")
        return eventi + [evento]

    if op.stato == "aperta" and h >= op.prima_uscita:
        op.prezzo_meta, op.data_meta, op.stato = max(o, op.prima_uscita), giorno, "meta chiusa"
        eventi.append("prima_uscita")

    if not op.pareggio_attivo and h >= op.pareggio:
        op.pareggio_attivo, op.stop = True, op.ingresso
        eventi.append("pareggio")

    if op.stato == "meta chiusa" and c < sma20:
        op.stato = "uscita domani"
        eventi.append("sotto_media")
    return eventi


def _media_metà(op: Operazione, misura) -> float | None:
    if op.stato != "chiusa":
        return None
    if op.prezzo_meta is None:
        return misura(op.prezzo_uscita)
    return (misura(op.prezzo_meta) + misura(op.prezzo_uscita)) / 2


def risultato_r(op: Operazione) -> float | None:
    return _media_metà(op, lambda prezzo: (prezzo - op.ingresso) / op.r)


def rendimento(op: Operazione) -> float | None:
    return _media_metà(op, lambda prezzo: prezzo / op.ingresso - 1)
