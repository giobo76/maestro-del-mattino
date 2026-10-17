"""Download di prezzi (Yahoo Finance) e notizie (feed RSS)."""
import calendar
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

COLONNE_PREZZI = ["Open", "High", "Low", "Close", "Volume"]
RIGHE_MINIME = 60


class DatiNonDisponibili(Exception):
    pass


@dataclass
class Notizia:
    titolo: str
    link: str
    fonte: str
    data: datetime


def _scarica(simboli: list[str], tentativi: int, pausa_s: float, **opzioni) -> pd.DataFrame:
    for tentativo in range(1, tentativi + 1):
        try:
            tabella = yf.download(simboli, group_by="ticker", auto_adjust=True, progress=False,
                                  threads=True, **opzioni)
            if tabella is not None and not tabella.empty:
                return tabella
            log.warning("Yahoo ha restituito dati vuoti (tentativo %d)", tentativo)
        except Exception as errore:  # yfinance solleva eccezioni di tipo diverso
            log.warning("Errore Yahoo (tentativo %d): %s", tentativo, errore)
        if tentativo < tentativi:
            time.sleep(pausa_s)
    raise DatiNonDisponibili("Yahoo Finance non risponde")


def _per_simbolo(tabella: pd.DataFrame, simbolo: str) -> pd.DataFrame | None:
    if isinstance(tabella.columns, pd.MultiIndex):
        if simbolo not in tabella.columns.get_level_values(0):
            return None
        df = tabella[simbolo]
    else:
        df = tabella
    df = df[[c for c in COLONNE_PREZZI if c in df.columns]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df.dropna(subset=["Open", "Close"])


def scarica_prezzi(simboli: list[str], anni: int, oggi: date, pausa_s: float = 5) -> dict[str, pd.DataFrame]:
    tabella = _scarica(simboli, 3, pausa_s, period=f"{anni}y")
    risultato = {}
    for simbolo in simboli:
        df = _per_simbolo(tabella, simbolo)
        if df is not None:
            df = df[df.index < pd.Timestamp(oggi)]
        if df is None or len(df) < RIGHE_MINIME:
            log.warning("Titolo %s escluso: dati insufficienti", simbolo)
            continue
        risultato[simbolo] = df
    return risultato


def scarica_prezzi_giorno(simboli: list[str], giorno: date) -> dict[str, tuple[float, float]]:
    tabella = _scarica(simboli, 3, 5, start=giorno.isoformat(),
                       end=(giorno + timedelta(days=1)).isoformat())
    risultato = {}
    for simbolo in simboli:
        df = _per_simbolo(tabella, simbolo)
        if df is None:
            continue
        riga = df[df.index == pd.Timestamp(giorno)]
        if not riga.empty:
            risultato[simbolo] = (float(riga["Open"].iloc[0]), float(riga["Close"].iloc[0]))
    return risultato


def _url_feed(nome: str, simbolo: str, lingua: str) -> list[str]:
    query = quote_plus(f'"{nome}" when:1d')
    if lingua == "it":
        return [f"https://news.google.com/rss/search?q={query}&hl=it&gl=IT&ceid=IT:it"]
    return [
        f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={simbolo}&region=US&lang=en-US",
    ]


def scarica_notizie(nome: str, simbolo: str, lingua: str, ore: int = 24,
                    adesso: datetime | None = None) -> list[Notizia]:
    adesso = adesso or datetime.now(timezone.utc)
    limite = adesso - timedelta(hours=ore)
    notizie = []
    for url in _url_feed(nome, simbolo, lingua):
        try:
            feed = feedparser.parse(url)
        except Exception as errore:
            log.warning("Feed non disponibile %s: %s", url, errore)
            continue
        for voce in getattr(feed, "entries", []):
            pubblicata = getattr(voce, "published_parsed", None)
            if pubblicata is None:
                continue
            data = datetime.fromtimestamp(calendar.timegm(pubblicata), timezone.utc)
            if data < limite:
                continue
            fonte = getattr(getattr(voce, "source", None), "title", None) or url.split("/")[2]
            notizie.append(Notizia(titolo=voce.title, link=voce.link, fonte=fonte, data=data))
    notizie.sort(key=lambda n: n.data, reverse=True)
    return notizie[:10]
