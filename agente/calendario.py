"""Giorni di borsa aperta e ora italiana."""
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars

ROMA = ZoneInfo("Europe/Rome")


def adesso_roma() -> datetime:
    return datetime.now(ROMA)


@lru_cache
def _calendario(codice: str):
    return exchange_calendars.get_calendar(codice)


def borsa_aperta(calendario: str, giorno: date) -> bool:
    return bool(_calendario(calendario).is_session(giorno.isoformat()))
