"""Lettura e scrittura della pagina del giorno (oggi.json)."""
import dataclasses
import json
from pathlib import Path


def _serializza(valore):
    if dataclasses.is_dataclass(valore):
        return dataclasses.asdict(valore)
    return str(valore)


def leggi_oggi(percorso) -> dict | None:
    if not Path(percorso).exists():
        return None
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def salva_oggi(percorso, contenuto: dict) -> None:
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    testo = json.dumps(contenuto, ensure_ascii=False, indent=2, default=_serializza)
    Path(percorso).write_text(testo, encoding="utf-8")
