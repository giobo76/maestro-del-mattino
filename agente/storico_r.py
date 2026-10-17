"""Simulazione delle operazioni sul passato e resa media in R per ogni "situazione"."""
import pandas as pd

from agente.operazione import Operazione, avanza, livelli_da, risultato_r
from agente.segnali import calcola_indicatori, calcola_situazione

COLONNE = ["simbolo", "data_segnale", "situazione", "data_uscita", "chiusa", "risultato_r", "esito"]


def _esito(op: Operazione) -> str:
    if op.stato != "chiusa":
        return "aperta"
    if op.motivo == "apertura sotto lo stop":
        return "apertura_sotto_stop"
    if op.prezzo_meta is not None:
        return "prima_uscita"
    return "pareggio" if op.motivo == "stop a pareggio" else "stop"


def simula_storico(prezzi: dict[str, pd.DataFrame], atr_mult: float) -> pd.DataFrame:
    righe = []
    for simbolo, df in prezzi.items():
        ind = calcola_indicatori(df)
        situazioni = calcola_situazione(ind)
        date = list(ind.index)
        o, h, l, c = (ind[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
        sma, atr = ind["sma20"].to_numpy(), ind["atr14"].to_numpy()
        for t in range(len(ind) - 1):
            if pd.isna(situazioni.iloc[t]):
                continue
            lv = livelli_da(c[t], atr[t], atr_mult)
            if lv is None:
                continue
            op = Operazione("", "", simbolo, simbolo, "", lv.riferimento, lv.r, lv.stop, lv.pareggio,
                            lv.prima_uscita, False, 0.0, 0)
            uscita = None
            for j in range(t + 1, len(ind)):
                avanza(op, "", o[j], h[j], l[j], c[j], sma[j])
                if op.stato == "chiusa":
                    uscita = date[j]
                    break
            righe.append({"simbolo": simbolo, "data_segnale": date[t], "situazione": situazioni.iloc[t],
                          "data_uscita": uscita, "chiusa": op.stato == "chiusa",
                          "risultato_r": risultato_r(op), "esito": _esito(op)})
    storico = pd.DataFrame(righe, columns=COLONNE)
    storico["data_uscita"] = pd.to_datetime(storico["data_uscita"])
    return storico


def costruisci_tabella_r(storico: pd.DataFrame, fino_a: pd.Timestamp | None,
                         casi_minimi: int, casi_virtuali: int) -> pd.DataFrame:
    usate = storico[storico["chiusa"].astype(bool)]
    if fino_a is not None:
        usate = usate[usate["data_uscita"] <= fino_a]
    media = float(usate["risultato_r"].mean())
    tabella = usate.groupby("situazione").agg(
        casi=("risultato_r", "size"), somma=("risultato_r", "sum"),
        pct_stop=("esito", lambda e: float((e == "stop").mean())),
        pct_2r=("esito", lambda e: float((e == "prima_uscita").mean())))
    tabella["resa_grezza"] = tabella["somma"] / tabella["casi"]
    tabella["resa"] = (tabella["somma"] + casi_virtuali * media) / (tabella["casi"] + casi_virtuali)
    tabella = tabella[tabella["casi"] >= casi_minimi][["casi", "resa_grezza", "resa", "pct_stop", "pct_2r"]]
    tabella.attrs["media"] = media
    return tabella


def cerca(tabella: pd.DataFrame, situazione: str) -> dict | None:
    if situazione not in tabella.index:
        return None
    riga = tabella.loc[situazione]
    return {"resa": float(riga["resa"]), "casi": int(riga["casi"]),
            "pct_stop": float(riga["pct_stop"]), "pct_2r": float(riga["pct_2r"])}


def prova_fuori_campione_r(storico: pd.DataFrame, casi_minimi: int, casi_virtuali: int,
                           soglia: float) -> dict:
    al = storico["data_segnale"].max()
    taglio = al - pd.Timedelta(days=365)
    tabella = costruisci_tabella_r(storico, taglio, casi_minimi, casi_virtuali)
    candidate = storico[storico["data_segnale"] > taglio].merge(
        tabella[["resa"]], left_on="situazione", right_index=True)
    candidate = candidate[candidate["resa"] >= soglia]

    scelte, libero_dal = [], taglio
    for giorno, gruppo in candidate.groupby("data_segnale", sort=True):
        if giorno < libero_dal:
            continue
        migliore = gruppo.loc[gruppo["resa"].idxmax()]
        scelte.append(migliore)
        if not migliore["chiusa"]:
            break  # ancora aperta alla fine dei dati: nessun'altra operazione possibile
        libero_dal = migliore["data_uscita"]

    scelte = pd.DataFrame(scelte)
    chiuse = scelte[scelte["chiusa"].astype(bool)] if len(scelte) else scelte
    vuoto = len(chiuse) == 0
    return {
        "dal": str((taglio + pd.Timedelta(days=1)).date()),
        "al": str(al.date()),
        "operazioni": int(len(chiuse)),
        "ancora_aperte": int(len(scelte) - len(chiuse)),
        "resa_annunciata": None if vuoto else float(chiuse["resa"].mean()),
        "resa_reale": None if vuoto else float(chiuse["risultato_r"].mean()),
        "pct_stop": None if vuoto else float((chiuse["esito"] == "stop").mean()),
        "pct_2r": None if vuoto else float((chiuse["esito"] == "prima_uscita").mean()),
    }
