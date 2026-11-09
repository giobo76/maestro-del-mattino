"""Email tramite l'API di Resend."""
import html as html_lib
import json
import logging
import math
import urllib.request
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from agente.calendario import ROMA

from agente.operazioni import Messaggio

log = logging.getLogger(__name__)

MITTENTE = "Maestro del mattino <onboarding@resend.dev>"
URL_RESEND = "https://api.resend.com/emails"
URL_SEGNA = "https://github.com/giobo76/maestro-del-mattino/actions/workflows/agente.yml"


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


def _decimali(valore: float) -> int:
    return 3 if valore < 10 else 2  # sotto i 10 € un centesimo è troppo grossolano per gli ordini


def _prezzo(valore: float, valuta: str) -> str:
    testo = f"{valore:,.{_decimali(valore)}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return testo + (" €" if valuta == "EUR" else " $")


def _tws(valore: float) -> str:
    """Prezzo come va scritto in TWS: punto decimale, nessun separatore delle migliaia."""
    return f"{valore:.{_decimali(valore)}f}"


def _apertura(mercato: str, oggi: date) -> str:
    if mercato == "ITA":
        return "09:00"
    new_york = datetime.combine(oggi, time(9, 30), tzinfo=ZoneInfo("America/New_York"))
    return new_york.astimezone(ROMA).strftime("%H:%M")  # 14:30 nelle settimane del cambio d'ora


def _istruzioni_tws(s: dict, oggi: date) -> str:
    lv, n = s["livelli"], s["quantita"]
    meta = n // 2 if s["mercato"] == "ITA" else math.floor(n / 2 * 10000) / 10000
    resto = round(n - meta, 4)
    passi = [
        f"<b>Prima delle {_apertura(s['mercato'], oggi)}</b> (apertura): ACQUISTARE, Q.TÀ <b>{n:g}</b>, "
        "tipo <b>MKT</b>, durata DAY → INVIA.",
        "Subito dopo, prima che l'acquisto venga eseguito: clic destro sulla riga dell'ordine → "
        "Allega → <b>Ordini bracket</b>. Sostituisci i prezzi proposti da TWS:"
        f"<br>• ProfitTaker: LMT <b>{_tws(lv['prima_uscita'])}</b>, quantità <b>{meta:g}</b>, durata GTC"
        f"<br>• StopLoss: STP <b>{_tws(lv['stop'])}</b>, quantità <b>{n:g}</b>, durata GTC"
        "<br>I prezzi si scrivono con il <b>punto</b>; il prezzo dello stop va nella colonna "
        "<b>«Prezzo stop»</b> (sotto «Ask» nella scheda Portafoglio)."
        "<br>Controlla con doppio clic su ogni riga, poi Trasmetti.",
        "Dopo l'apertura, ad acquisto eseguito: doppio clic sullo StopLoss → Visualizzazioni \"Completa\" → "
        f"Adegua Stop: tipo STP, innesco <b>{_tws(lv['pareggio'])}</b>, stop adeguato = <b>il tuo prezzo "
        "d'ingresso</b> → Trasmetti. Così lo stop sale al pareggio da solo.",
        "Quando la <b>metà viene venduta</b> (+2R), TWS può annullare anche lo StopLoss. Apri «In sospeso (tutti)»: "
        f"se lo stop non c'è più, dalla scheda Portafoglio inserisci VENDERE <b>{resto:g}</b>, tipo STP, "
        "«Prezzo stop» = <b>il tuo prezzo d'ingresso</b>, durata GTC → Trasmetti.",
    ]
    elenco = "".join(f"<li style='margin:4px 0'>{p}</li>" for p in passi)
    return ("<details open style='background:#f3f6fa;padding:6px 10px;margin-top:8px'>"
            "<summary><b>Come inserirlo in TWS</b></summary>"
            f"<ol style='padding-left:18px'>{elenco}</ol>"
            "<p style='font-size:12px'>Mai una vendita LMT sotto il prezzo attuale per proteggerti: "
            "si esegue subito. Per lo stop si usa sempre STP.</p></details>")


def _pagina(contenuto: str, url_pagina: str) -> str:
    return (f'<div style="font-family:system-ui,sans-serif;max-width:560px">{contenuto}'
            f'<p><a href="{url_pagina}">Apri la pagina completa</a></p>'
            '<p style="color:#666;font-size:12px">Strumento personale a scopo didattico. '
            "Non è una consulenza finanziaria.</p></div>")


def _data_breve(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%d/%m") if iso else ""


def blocco_squeeze(sq: dict | None) -> str:
    """Sezione dell'email con i cambi di colore dello Squeeze Momentum [AlgoAlpha] sul FTSE MIB."""
    if not sq or not (sq.get("verso_rosso") or sq.get("verso_verde")):
        return ""
    def righe(voci, simbolo):
        return "".join(f"<li>{simbolo} <b>{html_lib.escape(v['nome'])}</b> ({html_lib.escape(v['simbolo'])}): "
                       f"momentum {_num(v['ieri'])} → {_num(v['momentum'])}, chiusura {_num(v['chiusura'], 3)}</li>"
                       for v in voci)
    parti = [f"<h3>🔄 FTSE MIB: cambi di colore alla chiusura del {_data_breve(sq.get('data'))}</h3>",
             "<p style='font-size:13px;color:#555'>Squeeze Momentum Oscillator [AlgoAlpha], impostazioni 10/20. "
             "Solo osservazione: segnale non ancora testato.</p>"]
    if sq.get("verso_rosso"):
        parti.append("<p><b>Dal verde al rosso</b></p><ul>" + righe(sq["verso_rosso"], "🔴") + "</ul>")
    if sq.get("verso_verde"):
        parti.append("<p><b>Dal rosso al verde</b></p><ul>" + righe(sq["verso_verde"], "🟢") + "</ul>")
    rossi = [v["nome"] for v in sq.get("rossi", [])]
    parti.append(f"<p style='font-size:13px'>Rossi in tutto: {len(rossi)} su {sq.get('titoli', 0)}"
                 + (f" ({html_lib.escape(', '.join(rossi))})" if rossi else "") + ".</p>")
    return "".join(parti)


def _num(valore: float, decimali: int = 1) -> str:
    return f"{valore:+.{decimali}f}".replace(".", ",") if decimali == 1 else f"{valore:.{decimali}f}".replace(".", ",")


def email_mattina(schede: list[dict], url_pagina: str, oggi: date | None = None,
                  squeeze: dict | None = None) -> tuple[str, str] | None:
    oggi = oggi or datetime.now(ROMA).date()
    nuove = [s for s in schede if s.get("nuova")]
    sq_html = blocco_squeeze(squeeze)
    if not nuove:
        if not sq_html:
            return None
        n_r, n_v = len(squeeze["verso_rosso"]), len(squeeze["verso_verde"])
        pezzi = ([f"{n_r} al rosso"] if n_r else []) + ([f"{n_v} al verde"] if n_v else [])
        return "🔄 FTSE MIB: " + ", ".join(pezzi), _pagina(sq_html, url_pagina)
    blocchi = []
    for s in nuove:
        lv, v = s["livelli"], s["valuta"]
        studio = ('<p style="background:#fff8c5;padding:6px">⚠️ Sotto soglia: <b>solo studio</b>, '
                  "non per investire.</p>" if s.get("sotto_soglia") else "")
        quantita = s.get("quantita")
        capitale = f"{s.get('capitale') or 100:,.0f}".replace(",", ".")
        righe = [("Ingresso", "al mercato, all'apertura"),
                 ("Stop loss", _prezzo(lv["stop"], v)),
                 ("Pareggio (+1R): sposta lo stop all'ingresso", _prezzo(lv["pareggio"], v)),
                 ("Prima uscita (+2R): vendi metà", _prezzo(lv["prima_uscita"], v)),
                 ("Il resto", "vendi dopo una chiusura sotto la media a 20 giorni (ti avviso io)")]
        if quantita:
            righe.append((f"Quantità ({capitale} € per questo mercato)", f"{quantita:g}".replace(".", ",")))
        elif quantita == 0:
            righe.append(("Quantità", f"con {capitale} € non puoi comprarne nemmeno una"))
        else:
            righe.append(("Quantità", "mercato non incluso nel tuo conto IBKR: solo simulazione"))
        tabella = "".join(f"<tr><td style='padding:4px 8px'>{html_lib.escape(a)}</td>"
                          f"<td style='padding:4px 8px'><b>{html_lib.escape(b)}</b></td></tr>" for a, b in righe)
        tws = _istruzioni_tws(s, oggi) if quantita and not s.get("sotto_soglia") else ""
        blocchi.append(f"<h3>{html_lib.escape(s['nome'])} ({html_lib.escape(s['simbolo'])})</h3>{studio}"
                       f"<table style='border-collapse:collapse'>{tabella}</table>{tws}")
    blocchi.append(f'<p style="font-size:13px">Non esegui un ordine? <a href="{URL_SEGNA}">Segnalo qui</a>: '
                   "Run workflow → comando <b>segna</b>, scegli il mercato ed eseguita <b>no</b>. "
                   "L'agente la seguirà solo su carta e il giorno dopo potrà proporne una nuova.</p>")
    oggetto = "📈 Nuova operazione: " + ", ".join(s["nome"] for s in nuove)
    return oggetto, _pagina("".join(blocchi) + sq_html, url_pagina)


def email_sera(messaggi: list[Messaggio], url_pagina: str) -> tuple[str, str] | None:
    if not messaggi:
        return None
    n = len(messaggi)
    oggetto = f"🔔 Maestro del mattino: {n} aggiornament{'o' if n == 1 else 'i'}"
    elenco = "".join(f"<li style='margin:6px 0'>{html_lib.escape(m.testo)}</li>" for m in messaggi)
    return oggetto, _pagina(f"<ul>{elenco}</ul>", url_pagina)
