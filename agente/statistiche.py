"""Costi IBKR, conti simulati e statistiche delle previsioni."""
from datetime import date

import pandas as pd

from agente.config import Config
from agente.segnali import COMPONENTI

FASCE = [("55–58%", 0.55, 0.58), ("58–61%", 0.58, 0.61), ("oltre 61%", 0.61, 1.01)]


def costo_andata_ritorno(mercato: str, valore_eur: float, prezzo: float, costi: dict,
                         cambio_eur_usd: float) -> float:
    """Commissioni di acquisto + vendita in euro. Tobin tax esclusa: si vende in giornata."""
    if mercato == "ITA":
        return 2 * max(costi["ita_minimo_eur"], costi["ita_pct"] * valore_eur)
    valore_usd = valore_eur * cambio_eur_usd
    azioni = valore_usd / prezzo
    per_ordine = min(max(costi["usa_minimo_usd"], azioni * costi["usa_per_azione_usd"]),
                     costi["usa_massimo_pct"] * valore_usd)
    return 2 * per_ordine / cambio_eur_usd + 2 * costi["cambio_pct"] * valore_eur


def _cambio(cambi: dict[date, float], giorno: date) -> float:
    if not cambi:
        return 1.0
    precedenti = [d for d in cambi if d <= giorno]
    return cambi[max(precedenti)] if precedenti else cambi[min(cambi)]


def _conclusi(prev: pd.DataFrame) -> pd.DataFrame:
    return prev[prev["salito"].notna()].sort_values("data")


def simula_conto(prev: pd.DataFrame, capitale: dict[str, float], costi: dict,
                 cambi: dict[date, float], tasse_pct: float) -> dict:
    valori = dict(capitale)
    iniziale = sum(capitale.values())
    andamento = []
    conclusi = _conclusi(prev)
    for data, giorno in conclusi[conclusi["mercato"].isin(list(capitale))].groupby("data", sort=True):
        for _, riga in giorno.iterrows():
            m = riga["mercato"]
            costo = costo_andata_ritorno(m, valori[m], riga["apertura"], costi,
                                         _cambio(cambi, date.fromisoformat(data)))
            valori[m] = valori[m] * (1 + riga["rend"]) - costo
        andamento.append((data, sum(valori.values())))
    lordo = sum(valori.values())
    tasse = tasse_pct * max(0.0, lordo - iniziale)
    return {"iniziale": iniziale, "finale_lordo": lordo, "tasse": tasse,
            "finale_netto": lordo - tasse, "andamento": andamento}


def _conteggio(righe: pd.DataFrame) -> dict:
    totale = len(righe)
    azzeccate = int(righe["salito"].sum()) if totale else 0
    return {"totale": totale, "azzeccate": azzeccate,
            "percentuale": azzeccate / totale if totale else None}


def _rend_indice(serie: pd.Series, dal: str, al: str) -> float | None:
    """Compra e tieni: dalla chiusura del giorno prima della prima previsione all'ultima chiusura."""
    prima = serie[serie.index < pd.Timestamp(dal)]
    dopo = serie[serie.index <= pd.Timestamp(al)]
    if dopo.empty:
        return None
    partenza = prima.iloc[-1] if not prima.empty else dopo.iloc[0]
    return float(dopo.iloc[-1] / partenza - 1)


def calcola_statistiche(prev: pd.DataFrame, cfg: Config, cambi: dict[date, float],
                        indici: dict[str, pd.Series]) -> dict:
    conclusi = _conclusi(prev)
    stat = _conteggio(conclusi)
    stat["per_mercato"] = {m: _conteggio(conclusi[conclusi["mercato"] == m]) for m in cfg.mercati}

    stat["calibrazione"] = []
    for etichetta, da, a in FASCE:
        righe = conclusi[(conclusi["prob"] >= da) & (conclusi["prob"] < a)]
        stat["calibrazione"].append({
            "fascia": etichetta, "previsioni": len(righe),
            "prob_media": float(righe["prob"].mean()) if len(righe) else None,
            "percentuale": float(righe["salito"].mean()) if len(righe) else None})

    quota = cfg.conto_simulato_eur / len(cfg.mercati)
    stat["conto_simulato"] = simula_conto(prev, {m: quota for m in cfg.mercati}, cfg.costi, cambi,
                                          cfg.costi["tasse_pct"])
    quota_ibkr = cfg.ibkr_capitale_eur / len(cfg.ibkr_mercati)
    stat["conto_ibkr"] = simula_conto(prev, {m: quota_ibkr for m in cfg.ibkr_mercati}, cfg.costi, cambi,
                                      cfg.costi["tasse_pct"])

    stat["indici"] = {}
    for m, serie in indici.items():
        righe = conclusi[conclusi["mercato"] == m]
        if len(righe):
            stat["indici"][m] = _rend_indice(serie, righe["data"].iloc[0], righe["data"].iloc[-1])

    segnali = []
    if len(conclusi):
        parti = conclusi["situazione"].str.split("|")
        for componente in COMPONENTI:
            stati = parti.map(lambda p: next((x for x in p if x.startswith(componente + "=")), None))
            for stato, gruppo in conclusi.groupby(stati):
                if len(gruppo) >= 5:
                    segnali.append({"segnale": stato, "casi": len(gruppo),
                                    "percentuale": float(gruppo["salito"].mean())})
    stat["segnali"] = sorted(segnali, key=lambda s: s["percentuale"], reverse=True)
    return stat
