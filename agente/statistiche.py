"""Statistiche delle operazioni in R e conti simulati con le commissioni IBKR."""
from datetime import date

import pandas as pd

from agente.config import Config
from agente.operazione import Operazione, rendimento, risultato_r


def costo_ordine(mercato: str, valore_eur: float, prezzo: float, costi: dict, cambio_eur_usd: float) -> float:
    """Commissione di un singolo ordine, in euro."""
    if mercato == "ITA":
        return max(costi["ita_minimo_eur"], costi["ita_pct"] * valore_eur)
    valore_usd = valore_eur * cambio_eur_usd
    azioni = valore_usd / prezzo
    commissione = min(max(costi["usa_minimo_usd"], azioni * costi["usa_per_azione_usd"]),
                      costi["usa_massimo_pct"] * valore_usd)
    return commissione / cambio_eur_usd + costi["cambio_pct"] * valore_eur


def _cambio(cambi: dict[date, float], giorno: date) -> float:
    if not cambi:
        return 1.0
    precedenti = [d for d in cambi if d <= giorno]
    return cambi[max(precedenti)] if precedenti else cambi[min(cambi)]


def _chiuse(ops: list[Operazione]) -> list[Operazione]:
    return sorted((o for o in ops if o.stato == "chiusa"), key=lambda o: (o.data_uscita, o.mercato))


def simula_conto(ops: list[Operazione], capitale: dict[str, float], costi: dict,
                 cambi: dict[date, float], tasse_pct: float) -> dict:
    """Reinveste tutto il capitale del mercato in ogni operazione vera (non "solo studio")."""
    valori = dict(capitale)
    iniziale = sum(capitale.values())
    andamento = []
    for op in _chiuse(ops):
        if op.sotto_soglia or op.mercato not in valori:
            continue
        valore = valori[op.mercato]
        cambio = _cambio(cambi, date.fromisoformat(op.data_ingresso))
        costo = costo_ordine(op.mercato, valore, op.ingresso, costi, cambio)
        if op.prezzo_meta is not None:
            costo += 2 * costo_ordine(op.mercato, valore / 2, op.ingresso, costi, cambio)
        else:
            costo += costo_ordine(op.mercato, valore, op.ingresso, costi, cambio)
        valori[op.mercato] = valore * (1 + rendimento(op)) - costo
        andamento.append((op.data_uscita, sum(valori.values())))
    lordo = sum(valori.values())
    tasse = tasse_pct * max(0.0, lordo - iniziale)
    return {"iniziale": iniziale, "finale_lordo": lordo, "tasse": tasse,
            "finale_netto": lordo - tasse, "andamento": andamento}


def _gruppo(ops: list[Operazione]) -> dict:
    n = len(ops)
    if n == 0:
        return {"chiuse": 0, "resa_media": None, "pct_stop": None, "pct_pareggio": None,
                "pct_2r": None, "somma_r": 0.0}
    rese = [risultato_r(o) for o in ops]
    return {
        "chiuse": n,
        "resa_media": sum(rese) / n,
        "pct_stop": sum(o.motivo == "stop loss" for o in ops) / n,
        "pct_pareggio": sum(o.motivo == "stop a pareggio" for o in ops) / n,
        "pct_2r": sum(o.prezzo_meta is not None for o in ops) / n,
        "somma_r": sum(rese),
    }


def _rend_indice(serie: pd.Series, dal: str, al: str) -> float | None:
    """Compra e tieni: dalla chiusura del giorno prima del primo ingresso all'ultima uscita."""
    prima = serie[serie.index < pd.Timestamp(dal)]
    dopo = serie[serie.index <= pd.Timestamp(al)]
    if dopo.empty:
        return None
    partenza = prima.iloc[-1] if not prima.empty else dopo.iloc[0]
    return float(dopo.iloc[-1] / partenza - 1)


def calcola_statistiche(ops: list[Operazione], cfg: Config, cambi: dict[date, float],
                        indici: dict[str, pd.Series]) -> dict:
    chiuse = _chiuse(ops)
    stat = {
        "consigli": _gruppo([o for o in chiuse if not o.sotto_soglia]),
        "studio": _gruppo([o for o in chiuse if o.sotto_soglia]),
        "aperte": sum(o.stato != "chiusa" for o in ops),
    }
    quota = cfg.conto_simulato_eur / len(cfg.mercati)
    stat["conto_simulato"] = simula_conto(ops, {m: quota for m in cfg.mercati}, cfg.costi, cambi,
                                          cfg.costi["tasse_pct"])
    quota_ibkr = cfg.ibkr_capitale_eur / len(cfg.ibkr_mercati)
    stat["conto_ibkr"] = simula_conto(ops, {m: quota_ibkr for m in cfg.ibkr_mercati}, cfg.costi, cambi,
                                      cfg.costi["tasse_pct"])
    stat["indici"] = {}
    for m, serie in indici.items():
        del_mercato = [o for o in chiuse if o.mercato == m and not o.sotto_soglia]
        if del_mercato:
            stat["indici"][m] = _rend_indice(serie, min(o.data_ingresso for o in del_mercato),
                                             max(o.data_uscita for o in del_mercato))
    return stat


def quantita(mercato: str, capitale_eur: float, prezzo: float, cambio_eur_usd: float) -> float:
    """Azioni acquistabili con il capitale: intere in Italia, frazioni (4 decimali) negli USA."""
    if mercato == "ITA":
        return int(capitale_eur // prezzo)
    return round(capitale_eur * cambio_eur_usd / prezzo, 4)
