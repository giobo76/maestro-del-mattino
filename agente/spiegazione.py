"""Gemini: giudizio sulle notizie e testi in italiano semplice.

Gemini racconta i numeri che riceve: non sceglie i titoli e non produce numeri per la pagina.
"""
import json
import logging
import os
from typing import Protocol

from agente.config import Config
from agente.dati import Notizia

log = logging.getLogger(__name__)

GIUDIZI = {"positivo", "neutro", "negativo"}
CHIAVI_TESTI = ["perche", "rischio", "parola", "parola_spiegazione"]


class Cervello(Protocol):
    def genera(self, prompt: str) -> str: ...


class CervelloGemini:
    def __init__(self, modello: str, chiave: str):
        from google import genai

        self.modello = modello
        self.client = genai.Client(api_key=chiave)

    def genera(self, prompt: str) -> str:
        risposta = self.client.models.generate_content(
            model=self.modello, contents=prompt,
            config={"response_mime_type": "application/json"})
        return risposta.text


def crea_cervello(cfg: Config) -> Cervello | None:
    chiave = os.environ.get("GEMINI_API_KEY")
    if not chiave:
        log.warning("GEMINI_API_KEY mancante: niente spiegazioni")
        return None
    return CervelloGemini(cfg.gemini_modello, chiave)


def _chiedi_json(cervello: Cervello | None, prompt: str) -> dict | None:
    if cervello is None:
        return None
    try:
        testo = cervello.genera(prompt).strip()
        if testo.startswith("```"):
            testo = testo.strip("`").removeprefix("json").strip()
        risposta = json.loads(testo)
        return risposta if isinstance(risposta, dict) else None
    except Exception as errore:
        log.warning("Gemini non disponibile o risposta non valida: %s", errore)
        return None


def giudica_notizie(cervello: Cervello | None, nome: str, notizie: list[Notizia]) -> str | None:
    if not notizie:
        return "neutro"
    elenco = "\n".join(f"- {n.titolo}" for n in notizie)
    prompt = (
        f"Sei un analista. Leggi questi titoli di notizie su {nome} delle ultime 24 ore.\n{elenco}\n"
        'Rispondi solo con JSON {"giudizio": "positivo"|"neutro"|"negativo"}. '
        "Negativo solo se la notizia può far scendere il titolo oggi (indagini, conti sotto le attese, "
        "taglio delle stime, declassamenti)."
    )
    risposta = _chiedi_json(cervello, prompt)
    giudizio = (risposta or {}).get("giudizio")
    return giudizio if giudizio in GIUDIZI else None


def _pct(valore: float, decimali: int, segno: str = "") -> str:
    return f"{valore * 100:{segno}.{decimali}f}%".replace(".", ",")


def _prezzo(valore: float) -> str:
    return f"{valore:.2f}".replace(".", ",")


def _r(valore: float) -> str:
    return f"{valore:+.2f}R".replace(".", ",")


def scrivi_testi(cervello: Cervello | None, scheda: dict, parole_gia_usate: list[str]) -> dict | None:
    notizie = "\n".join(f"- {t}" for t in scheda.get("notizie", [])) or "- nessuna notizia"
    lv = scheda["livelli"]
    prompt = (
        "Scheda dell'operazione del giorno:\n"
        f"Titolo: {scheda['nome']} ({scheda['mercato']})\n"
        f"Piano: ingresso all'apertura; stop loss a {_prezzo(lv['stop'])}; quando il prezzo arriva a "
        f"{_prezzo(lv['pareggio'])} (+1R) lo stop sale al prezzo d'ingresso; a {_prezzo(lv['prima_uscita'])} "
        "(+2R) si vende metà; il resto si tiene finché il titolo chiude sotto la media mobile a 20 giorni.\n"
        f"Chiusura di riferimento: {_prezzo(lv['riferimento'])}\n"
        f"Nel passato, in {scheda['casi']} operazioni con segnali simili: resa media {_r(scheda['resa'])} "
        f"per operazione, stop pieno nel {_pct(scheda['pct_stop'], 0)} dei casi, "
        f"+2R raggiunto nel {_pct(scheda['pct_2r'], 0)}.\n"
        f"Segnali: {scheda['situazione']}\n"
        f"Notizie delle ultime 24 ore:\n{notizie}\n\n"
        + ("ATTENZIONE: la resa storica è sotto la soglia: è un titolo solo per studio, non un "
           "consiglio di investimento. Dillo chiaramente nella prima frase di 'perche'.\n\n"
           if scheda.get("sotto_soglia") else "")
        + "Scrivi per un principiante, in italiano semplice. Rispondi solo con JSON con le chiavi "
        '"perche", "rischio", "parola", "parola_spiegazione". '
        "'perche': 4-5 frasi che spiegano i segnali, le notizie e il piano dell'operazione. "
        "'rischio': 1-2 frasi sul rischio principale, dicendo quanto si perde in percentuale se scatta lo stop. "
        "'parola': un termine tecnico presente nella scheda e non in questo elenco: "
        f"{', '.join(parole_gia_usate) or 'nessuno'}. "
        "'parola_spiegazione': spiegazione con un esempio, massimo 3 frasi. "
        "Non scrivere numeri diversi da quelli della scheda e scrivili all'italiana, con la virgola. "
        "Non promettere guadagni."
    )
    risposta = _chiedi_json(cervello, prompt)
    if risposta is None or not all(isinstance(risposta.get(k), str) and risposta[k].strip()
                                   for k in CHIAVI_TESTI):
        return None
    return {k: risposta[k].strip() for k in CHIAVI_TESTI}
