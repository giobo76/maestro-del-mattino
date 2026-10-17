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


def seduta_precedente(calendario: str, giorno: date) -> date:
    cal = _calendario(calendario)
    seduta = cal.date_to_session(giorno.isoformat(), direction="next")
    return cal.previous_session(seduta).date()


def seduta_chiusa(calendario: str, giorno: date, adesso: datetime) -> bool:
    """Vero se la seduta del giorno è terminata (o non c'era)."""
    cal = _calendario(calendario)
    if not cal.is_session(giorno.isoformat()):
        return True
    return adesso >= cal.session_close(giorno.isoformat()).to_pydatetime()
