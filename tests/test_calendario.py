from datetime import date

from agente.calendario import adesso_roma, borsa_aperta


def test_borsa_aperta():
    assert borsa_aperta("XMIL", date(2026, 12, 25)) is False
    assert borsa_aperta("XNYS", date(2026, 11, 26)) is False
    assert borsa_aperta("XMIL", date(2026, 11, 26)) is True
    assert borsa_aperta("XMIL", date(2026, 10, 17)) is False  # sabato


def test_adesso_roma_ha_fuso():
    assert adesso_roma().tzinfo is not None
