from datetime import date

from datetime import datetime, timezone

from agente.calendario import adesso_roma, borsa_aperta, seduta_chiusa, seduta_precedente


def test_borsa_aperta():
    assert borsa_aperta("XMIL", date(2026, 12, 25)) is False
    assert borsa_aperta("XNYS", date(2026, 11, 26)) is False
    assert borsa_aperta("XMIL", date(2026, 11, 26)) is True
    assert borsa_aperta("XMIL", date(2026, 10, 17)) is False  # sabato


def test_adesso_roma_ha_fuso():
    assert adesso_roma().tzinfo is not None


def test_seduta_precedente():
    assert seduta_precedente("XNYS", date(2026, 10, 19)) == date(2026, 10, 16)  # lunedì -> venerdì
    assert seduta_precedente("XNYS", date(2026, 11, 27)) == date(2026, 11, 25)  # dopo Thanksgiving


def test_seduta_chiusa():
    giorno = date(2026, 10, 16)
    assert not seduta_chiusa("XNYS", giorno, datetime(2026, 10, 16, 16, 0, tzinfo=timezone.utc))
    assert seduta_chiusa("XNYS", giorno, datetime(2026, 10, 16, 20, 30, tzinfo=timezone.utc))
    assert seduta_chiusa("XNYS", giorno, datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc))
