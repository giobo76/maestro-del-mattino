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

from agente.operazione import Livelli, Operazione, risultato_r  # noqa: E402

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


def disegna_grafico(prezzi: pd.DataFrame, nome: str, percorso: Path, livelli: Livelli | None = None) -> None:
    ultimi = prezzi.copy()
    ultimi["sma20"] = ultimi["Close"].rolling(20).mean()
    ultimi["sma50"] = ultimi["Close"].rolling(50).mean()
    ultimi = ultimi.iloc[-63:]
    figura, asse = plt.subplots(figsize=(8, 4.5), dpi=100)
    asse.plot(ultimi.index, ultimi["Close"], color="#1f6feb", linewidth=2, label="Prezzo di chiusura")
    asse.plot(ultimi.index, ultimi["sma20"], color="#e3a008", linewidth=1.3, label="Media 20 giorni")
    asse.plot(ultimi.index, ultimi["sma50"], color="#8b5cf6", linewidth=1.3, label="Media 50 giorni")
    asse.scatter([ultimi.index[-1]], [ultimi["Close"].iloc[-1]], color="#1f6feb", zorder=5, s=40)
    if livelli is not None:
        for valore, colore, etichetta in ((livelli.stop, "#d1242f", "Stop loss"),
                                          (livelli.pareggio, "#e3a008", "Pareggio (+1R)"),
                                          (livelli.prima_uscita, "#1a7f37", "Prima uscita (+2R)")):
            asse.axhline(valore, color=colore, linestyle="--", linewidth=1.2, label=etichetta)
    asse.set_title(f"{nome}: ultimi 3 mesi")
    asse.grid(alpha=0.3)
    asse.legend(loc="upper left", fontsize=8)
    figura.autofmt_xdate()
    figura.tight_layout()
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(percorso)
    plt.close(figura)


def _data_it(iso: str | None) -> str | None:
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y") if iso else None


def it_r(valore) -> str:
    return "–" if _vuoto(valore) else it_num(valore, 2, "R", segno=True)


def it_prezzo(valore, valuta: str) -> str:
    return it_num(valore, 2, " €" if valuta == "EUR" else " $")


STATI = {"in attesa": "in attesa dell'apertura", "aperta": "aperta", "meta chiusa": "metà già venduta",
         "uscita domani": "da chiudere all'apertura", "chiusa": "chiusa"}


def _posizione(op: Operazione) -> dict:
    valuta = "EUR" if op.mercato == "ITA" else "USD"
    attuale = None
    if op.ingresso is not None and op.ultimo_prezzo is not None:
        attuale = (op.ultimo_prezzo - op.ingresso) / op.r
        if op.prezzo_meta is not None:
            attuale = ((op.prezzo_meta - op.ingresso) / op.r + attuale) / 2
    return {"id": op.id, "nome": op.nome, "mercato": op.mercato, "stato": STATI[op.stato],
            "ingresso": it_prezzo(op.ingresso, valuta), "stop": it_prezzo(op.stop or op.stop_iniziale, valuta),
            "ultimo": it_prezzo(op.ultimo_prezzo, valuta), "r_attuale": it_r(attuale),
            "studio": op.sotto_soglia, "carta": op.eseguita is False}


def _storico(ops: list[Operazione]) -> list[dict]:
    righe = []
    for op in sorted((o for o in ops if o.stato == "chiusa"), key=lambda o: o.data_uscita, reverse=True):
        valuta = "EUR" if op.mercato == "ITA" else "USD"
        r = risultato_r(op)
        segno = "✅" if r > 0.05 else ("❌" if r < -0.05 else "➖")
        righe.append({"data": _data_it(op.data_ingresso), "nome": op.nome, "mercato": op.mercato,
                      "ingresso": it_prezzo(op.ingresso, valuta), "uscita": it_prezzo(op.prezzo_uscita, valuta),
                      "risultato": f"{segno} {it_r(r)}", "motivo": op.motivo, "studio": op.sotto_soglia,
                      "carta": op.eseguita is False})
    return righe


def genera_sito(cartella: Path, oggi: dict, ops: list[Operazione], stat: dict, prova: dict,
                aggiornato: datetime) -> Path:
    cartella = Path(cartella)
    (cartella / "grafici").mkdir(parents=True, exist_ok=True)
    posizioni = {op.id: _posizione(op) for op in ops if op.stato != "chiusa"}
    schede = []
    for scheda in oggi.get("schede", []):
        scheda = dict(scheda)
        if scheda.get("grafico") and Path(scheda["grafico"]).exists():
            nome_file = Path(scheda["grafico"]).name
            shutil.copy(scheda["grafico"], cartella / "grafici" / nome_file)
            scheda["grafico_url"] = f"grafici/{nome_file}"
        scheda["posizione"] = posizioni.get(scheda.get("posizione_id"))
        schede.append(scheda)

    ambiente = Environment(loader=FileSystemLoader(CARTELLA_TEMPLATE), autoescape=select_autoescape())
    ambiente.filters.update(it_num=it_num, it_pct=it_pct, it_r=it_r, it_prezzo=it_prezzo,
                            leggi_segnali=leggi_segnali)
    html = ambiente.get_template("index.html").render(
        data=_data_it(oggi.get("data")), analisi_vecchia=oggi.get("data") != aggiornato.date().isoformat(),
        aggiornato=aggiornato.strftime("%d/%m/%Y alle %H:%M"), schede=schede,
        posizioni=list(posizioni.values()), storico=_storico(ops), stat=stat, prova=prova, footer=FOOTER)
    percorso = cartella / "index.html"
    percorso.write_text(html, encoding="utf-8")
    return percorso
