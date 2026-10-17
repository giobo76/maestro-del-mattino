"""Email tramite l'API di Resend."""
import html as html_lib
import json
import logging
import urllib.request

from agente.operazioni import Messaggio

log = logging.getLogger(__name__)

MITTENTE = "Maestro del mattino <onboarding@resend.dev>"
URL_RESEND = "https://api.resend.com/emails"


def invia(oggetto: str, html: str, destinatario: str, chiave: str | None,
          apri=urllib.request.urlopen) -> bool:
    if not chiave:
        log.warning("RESEND_API_KEY mancante: email non inviata")
        return False
    corpo = json.dumps({"from": MITTENTE, "to": [destinatario], "subject": oggetto, "html": html}).encode()
    richiesta = urllib.request.Request(URL_RESEND, data=corpo, method="POST", headers={
        "Authorization": f"Bearer {chiave}", "Content-Type": "application/json",
        "User-Agent": "maestro-del-mattino"})
    try:
        with apri(richiesta, timeout=20) as risposta:
            risposta.read()
        return True
    except Exception as errore:  # HTTPError, URLError, timeout: l'agente prosegue comunque
        log.error("Email non inviata: %s", errore)
        return False


def _prezzo(valore: float, valuta: str) -> str:
    testo = f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return testo + (" €" if valuta == "EUR" else " $")


def _pagina(contenuto: str, url_pagina: str) -> str:
    return (f'<div style="font-family:system-ui,sans-serif;max-width:560px">{contenuto}'
            f'<p><a href="{url_pagina}">Apri la pagina completa</a></p>'
            '<p style="color:#666;font-size:12px">Strumento personale a scopo didattico. '
            "Non è una consulenza finanziaria.</p></div>")


def email_mattina(schede: list[dict], url_pagina: str) -> tuple[str, str] | None:
    nuove = [s for s in schede if s.get("nuova")]
    if not nuove:
        return None
    blocchi = []
    for s in nuove:
        lv, v = s["livelli"], s["valuta"]
        studio = ('<p style="background:#fff8c5;padding:6px">⚠️ Sotto soglia: <b>solo studio</b>, '
                  "non per investire.</p>" if s.get("sotto_soglia") else "")
        quantita = s.get("quantita")
        righe = [("Ingresso", "al mercato, all'apertura"),
                 ("Stop loss", _prezzo(lv["stop"], v)),
                 ("Pareggio (+1R): sposta lo stop all'ingresso", _prezzo(lv["pareggio"], v)),
                 ("Prima uscita (+2R): vendi metà", _prezzo(lv["prima_uscita"], v)),
                 ("Il resto", "vendi dopo una chiusura sotto la media a 20 giorni (ti avviso io)")]
        if quantita:
            righe.append(("Quantità (conto da 100 €)", f"{quantita:g}".replace(".", ",")))
        elif quantita == 0:
            righe.append(("Quantità", "con 100 € non puoi comprarne nemmeno una"))
        else:
            righe.append(("Quantità", "mercato non incluso nel tuo conto IBKR: solo simulazione"))
        tabella = "".join(f"<tr><td style='padding:4px 8px'>{html_lib.escape(a)}</td>"
                          f"<td style='padding:4px 8px'><b>{html_lib.escape(b)}</b></td></tr>" for a, b in righe)
        blocchi.append(f"<h3>{html_lib.escape(s['nome'])} ({html_lib.escape(s['simbolo'])})</h3>{studio}"
                       f"<table style='border-collapse:collapse'>{tabella}</table>")
    oggetto = "📈 Nuova operazione: " + ", ".join(s["nome"] for s in nuove)
    return oggetto, _pagina("".join(blocchi), url_pagina)


def email_sera(messaggi: list[Messaggio], url_pagina: str) -> tuple[str, str] | None:
    if not messaggi:
        return None
    n = len(messaggi)
    oggetto = f"🔔 Maestro del mattino: {n} aggiornament{'o' if n == 1 else 'i'}"
    elenco = "".join(f"<li style='margin:6px 0'>{html_lib.escape(m.testo)}</li>" for m in messaggi)
    return oggetto, _pagina(f"<ul>{elenco}</ul>", url_pagina)
