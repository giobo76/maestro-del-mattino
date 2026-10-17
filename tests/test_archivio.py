from datetime import datetime, timezone

from agente.archivio import leggi_oggi, salva_oggi
from agente.dati import Notizia


def test_oggi_json(tmp_path):
    percorso = tmp_path / "oggi.json"
    assert leggi_oggi(percorso) is None
    notizia = Notizia("t", "http://x", "f", datetime(2026, 10, 16, tzinfo=timezone.utc))
    salva_oggi(percorso, {"data": "2026-10-16", "schede": [{"notizie": [notizia]}]})
    letto = leggi_oggi(percorso)
    assert letto["data"] == "2026-10-16"
    assert letto["schede"][0]["notizie"][0]["titolo"] == "t"
