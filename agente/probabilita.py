"""Probabilità storiche: quante volte una "situazione" è stata seguita da un rialzo
tra apertura e chiusura del giorno dopo."""
import pandas as pd

from agente.segnali import calcola_indicatori, calcola_situazione


def prepara_storico(prezzi: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parti = []
    for simbolo, df in prezzi.items():
        situazione = calcola_situazione(calcola_indicatori(df))
        apertura_dopo = df["Open"].shift(-1)
        chiusura_dopo = df["Close"].shift(-1)
        parte = pd.DataFrame({
            "simbolo": simbolo,
            "data": df.index,
            "situazione": situazione.values,
            "data_esito": pd.Series(df.index, index=df.index).shift(-1).values,
            "salito": (chiusura_dopo > apertura_dopo).values,
            "rend": (chiusura_dopo / apertura_dopo - 1).values,
        })
        parti.append(parte.dropna(subset=["situazione", "data_esito", "rend"]))
    if not parti:
        return pd.DataFrame(columns=["simbolo", "data", "situazione", "data_esito", "salito", "rend"])
    return pd.concat(parti, ignore_index=True)


def costruisci_tabella(storico: pd.DataFrame, fino_a: pd.Timestamp | None,
                       casi_minimi: int, casi_virtuali: int) -> pd.DataFrame:
    usati = storico if fino_a is None else storico[storico["data_esito"] <= fino_a]
    media = float(usati["salito"].mean())
    tabella = usati.groupby("situazione").agg(
        casi=("salito", "size"), salite=("salito", "sum"), rend_medio=("rend", "mean"))
    tabella["salite"] = tabella["salite"].astype(int)
    tabella["prob_grezza"] = tabella["salite"] / tabella["casi"]
    tabella["prob"] = (tabella["salite"] + casi_virtuali * media) / (tabella["casi"] + casi_virtuali)
    tabella = tabella[tabella["casi"] >= casi_minimi]
    tabella = tabella[["casi", "salite", "prob_grezza", "prob", "rend_medio"]]
    tabella.attrs["media"] = media
    return tabella


def cerca(tabella: pd.DataFrame, situazione: str) -> dict | None:
    if situazione not in tabella.index:
        return None
    riga = tabella.loc[situazione]
    return {"prob": float(riga["prob"]), "casi": int(riga["casi"]), "rend_medio": float(riga["rend_medio"])}


def simula_scelte(storico: pd.DataFrame, tabella: pd.DataFrame, dal: pd.Timestamp,
                  soglia: float) -> pd.DataFrame:
    colonne = ["data_esito", "simbolo", "prob", "salito", "rend"]
    righe = storico[storico["data_esito"] >= dal].merge(
        tabella[["prob"]], left_on="situazione", right_index=True)
    if righe.empty:
        return pd.DataFrame(columns=colonne)
    migliori = righe.loc[righe.groupby("data_esito")["prob"].idxmax()]
    migliori = migliori[migliori["prob"] >= soglia]
    return migliori[colonne].sort_values("data_esito").reset_index(drop=True)


def prova_fuori_campione(storico: pd.DataFrame, casi_minimi: int, casi_virtuali: int,
                         soglia: float) -> dict:
    al = storico["data_esito"].max()
    taglio = al - pd.Timedelta(days=365)
    tabella = costruisci_tabella(storico, taglio, casi_minimi, casi_virtuali)
    scelte = simula_scelte(storico, tabella, taglio + pd.Timedelta(days=1), soglia)
    vuoto = scelte.empty
    return {
        "dal": str((taglio + pd.Timedelta(days=1)).date()),
        "al": str(al.date()),
        "giorni_con_scelta": int(len(scelte)),
        "prob_media_annunciata": None if vuoto else float(scelte["prob"].mean()),
        "percentuale_reale": None if vuoto else float(scelte["salito"].mean()),
        "rend_medio": None if vuoto else float(scelte["rend"].mean()),
    }
