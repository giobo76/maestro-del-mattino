"""Generazione della pagina web e dei grafici."""
import math
import shutil
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

FOOTER = "Strumento personale a scopo didattico. Non è una consulenza finanziaria."
CARTELLA_TEMPLATE = Path(__file__).parent / "templates"

SEGNALI_LEGGIBILI = {
    "trend=su": "Tendenza in salita (prezzo sopra le medie mobili a 20 e 50 giorni)",
    "trend=giu": "Tendenza in discesa (prezzo sotto le medie mobili)",
    "trend=misto": "Tendenza incerta",
    "rsi=basso": "RSI basso: il titolo è sceso molto (ipervenduto)",
    "rsi=alto": "RSI alto: il titolo è salito molto (ipercomprato)",
    "rsi=normale": "RSI nella norma",
    "macd=rialzo": "MACD: incrocio al rialzo ieri",
    "macd=ribasso": "MACD: incrocio al ribasso ieri",
    "macd=nessuno": "MACD: nessun incrocio",
    "vol=alto": "Volumi ieri oltre il doppio del solito",
    "vol=normale": "Volumi nella norma",
    "rottura=si": "Ha superato il massimo degli ultimi 20 giorni",
    "rottura=no": "Nessuna rottura del massimo recente",
    "giorno=forte_su": "Ieri forte rialzo (oltre +2%)",
    "giorno=forte_giu": "Ieri forte ribasso (oltre −2%)",
    "giorno=normale": "Ieri giornata normale",
}


def _vuoto(valore) -> bool:
    return valore is None or (isinstance(valore, float) and math.isnan(valore)) or valore is pd.NA


def it_num(valore, decimali: int = 2, suffisso: str = "", segno: bool = False) -> str:
    if _vuoto(valore):
        return "–"
    testo = f"{valore:+,.{decimali}f}" if segno else f"{valore:,.{decimali}f}"
    testo = testo.replace(",", "§").replace(".", ",").replace("§", ".").replace("-", "−")
    return testo + suffisso


def it_pct(valore, decimali: int = 1, segno: bool = False) -> str:
    return "–" if _vuoto(valore) else it_num(valore * 100, decimali, "%", segno)


def leggi_segnali(situazione: str | None) -> list[str]:
    if not situazione:
        return []
    return [SEGNALI_LEGGIBILI.get(parte, parte) for parte in situazione.split("|")]


def disegna_grafico(prezzi: pd.DataFrame, nome: str, percorso: Path) -> None:
    ultimi = prezzi.copy()
    ultimi["sma20"] = ultimi["Close"].rolling(20).mean()
    ultimi["sma50"] = ultimi["Close"].rolling(50).mean()
    ultimi = ultimi.iloc[-63:]
    figura, asse = plt.subplots(figsize=(8, 4), dpi=100)
    asse.plot(ultimi.index, ultimi["Close"], color="#1f6feb", linewidth=2, label="Prezzo di chiusura")
    asse.plot(ultimi.index, ultimi["sma20"], color="#e3a008", linewidth=1.3, label="Media 20 giorni")
    asse.plot(ultimi.index, ultimi["sma50"], color="#8b5cf6", linewidth=1.3, label="Media 50 giorni")
    asse.scatter([ultimi.index[-1]], [ultimi["Close"].iloc[-1]], color="#d1242f", zorder=5, s=40,
                 label="Ieri")
    asse.set_title(f"{nome}: ultimi 3 mesi")
    asse.grid(alpha=0.3)
    asse.legend(loc="upper left", fontsize=8)
    figura.autofmt_xdate()
    figura.tight_layout()
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(percorso)
    plt.close(figura)


def _storico(prev: pd.DataFrame) -> list[dict]:
    righe = []
    for _, r in prev.sort_values(["data", "mercato"], ascending=[False, True]).iterrows():
        if _vuoto(r["salito"]):
            esito = "in attesa"
        else:
            esito = ("✅ " if r["salito"] else "❌ ") + it_pct(r["rend"], 2, segno=True)
        righe.append({"data": r["data"], "mercato": r["mercato"], "nome": r["nome"],
                      "prob": it_pct(r["prob"]) + (" (studio)" if r.get("sotto_soglia") is True else ""), "apertura": it_num(r["apertura"]),
                      "chiusura": it_num(r["chiusura"]), "esito": esito})
    return righe


def genera_sito(cartella: Path, oggi: dict, prev: pd.DataFrame, stat: dict, prova: dict,
                aggiornato: datetime) -> Path:
    cartella = Path(cartella)
    (cartella / "grafici").mkdir(parents=True, exist_ok=True)
    schede = []
    for scheda in oggi.get("schede", []):
        scheda = dict(scheda)
        if scheda.get("grafico") and Path(scheda["grafico"]).exists():
            nome_file = Path(scheda["grafico"]).name
            shutil.copy(scheda["grafico"], cartella / "grafici" / nome_file)
            scheda["grafico_url"] = f"grafici/{nome_file}"
        schede.append(scheda)

    ambiente = Environment(loader=FileSystemLoader(CARTELLA_TEMPLATE), autoescape=select_autoescape())
    ambiente.filters.update(it_num=it_num, it_pct=it_pct, leggi_segnali=leggi_segnali)
    html = ambiente.get_template("index.html").render(
        data=oggi.get("data"), aggiornato=aggiornato.strftime("%d/%m/%Y alle %H:%M"),
        schede=schede, storico=_storico(prev), stat=stat, prova=prova, footer=FOOTER)
    percorso = cartella / "index.html"
    percorso.write_text(html, encoding="utf-8")
    return percorso
