# Maestro del mattino 2: piano di costruzione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:subagent-driven-development (consigliata) oppure superpowers:executing-plans per eseguire il piano un compito alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** sostituire la previsione "sale tra apertura e chiusura" con operazioni complete (ingresso, stop a 2×ATR, pareggio a +1R, metà a +2R, resto fino alla chiusura sotto la SMA20), scelte per resa media storica in R, seguite ogni sera e notificate per email via Resend.

**Architettura:** un cuore puro `agente/operazione.py` (livelli + regole giorno per giorno) usato sia dal calcolo storico (`agente/storico_r.py`) sia dal controllo serale delle operazioni vere (`agente/operazioni.py`). Così passato e presente seguono esattamente le stesse regole. Scelta, statistiche, pagina e comandi vengono adattati; `probabilita.py`, `verifica.py` e la parte "previsioni" di `archivio.py` vengono eliminati.

**Tecnologie:** come la versione 1; email con `urllib` verso l'API HTTP di Resend (nessuna libreria nuova).

**Spec:** `docs/superpowers/specs/2026-10-17-gestione-posizioni-design.md` (che modifica `docs/superpowers/specs/2026-10-17-agente-trading-design.md`)

## Vincoli globali

- Testo visibile in italiano; numeri all'italiana
- Ogni regola giorno per giorno vive **solo** in `operazione.avanza`: storico e operazioni vere la chiamano, non la ricopiano
- Caso peggiore: lo stop si controlla prima degli obiettivi; il pareggio protegge solo dal giorno dopo
- Stop = `C − atr_mult × ATR14`, `atr_mult: 2.0`; soglia resa `soglia_r: 0.10`; casi minimi 30; casi virtuali 30
- Modalità studio invariata: sotto soglia l'operazione esce con l'etichetta ed è seguita, ma esclusa dai conti simulati
- Una posizione non chiusa alla volta per mercato
- Chiave Resend solo da `RESEND_API_KEY`; destinatario in `config.yaml` (`email_destinatario: bonolinigiovanni@gmail.com`), mittente `Maestro del mattino <onboarding@resend.dev>`
- I test non usano internet
- Footer invariato: "Strumento personale a scopo didattico. Non è una consulenza finanziaria."

## Punti di attenzione (Review Focus)

1. **Il titolo di un'operazione aperta sparisce da Yahoo** (sospeso, delistato): l'operazione resta aperta, la pagina e l'email serale dicono "dati non disponibili per X da N giorni". Test in Compito 4 (`test_titolo_senza_dati_segnalato`)
2. **Sera eseguita due volte o recupero di più giorni** (es. GitHub salta una sera): ogni giorno viene applicato una sola volta, in ordine. Test in Compito 4 (`test_giorni_applicati_una_volta`)
3. **Apertura sopra il livello +2R il giorno d'ingresso**: metà chiusa all'apertura, risultato coerente. Test in Compito 1 (`test_apertura_sopra_2r`)
4. **ATR nullo o negativo** (titolo fermo, dati sbagliati): niente operazione su quel titolo. Test in Compito 1 (`test_atr_nullo_niente_livelli`)
5. **Resend risponde con errore o non risponde**: l'agente registra l'errore e prosegue. Test in Compito 5 (`test_errore_resend_non_blocca`)

---

## Struttura dei file

```
agente/operazione.py      NUOVO  Livelli, Operazione, calcola_livelli, avanza, risultato
agente/storico_r.py       NUOVO  simulazione 5 anni, tabella in R, prova fuori campione
agente/operazioni.py      NUOVO  operazioni.csv, nuova_operazione, aggiorna_operazioni
agente/posta.py           NUOVO  invio Resend, testi email mattina/sera
agente/segnali.py         MODIFICA  + atr14
agente/dati.py            MODIFICA  + scarica_dal
agente/scelta.py          MODIFICA  scelta per resa in R
agente/spiegazione.py     MODIFICA  prompt con livelli e resa in R
agente/statistiche.py     RISCRITTO statistiche in R e conti simulati
agente/pagina.py, templates/index.html  RISCRITTI per operazioni
agente/main.py            MODIFICA  flussi mattina/sera/tabella
agente/archivio.py        MODIFICA  restano solo leggi_oggi/salva_oggi
agente/probabilita.py, agente/verifica.py  ELIMINATI (con i loro test)
config.yaml, agente/config.py  + atr_mult, soglia_r, email_destinatario; soglia_prob rimossa
.github/workflows/agente.yml   + RESEND_API_KEY
```

---

### Compito 1: Livelli e regole giorno per giorno

**File:**
- Crea: `agente/operazione.py`; Modifica: `agente/segnali.py`
- Test: `tests/test_operazione.py`, `tests/test_segnali.py`

**Interfacce:**
- Produce:
  - in `segnali.calcola_indicatori` la colonna `atr14` (Wilder: true range = max(H−L, |H−C_prec|, |L−C_prec|), `ewm(alpha=1/14, adjust=False, min_periods=14)`)
  - `Livelli` dataclass: `riferimento, r, stop, pareggio, prima_uscita: float`
  - `calcola_livelli(prezzi: pd.DataFrame, atr_mult: float) -> Livelli | None`: dall'ultima riga; `None` se ATR mancante o ≤ 0
  - `Operazione` dataclass: `id: str, mercato, simbolo, nome: str, data_segnale: str, riferimento, r, stop_iniziale, pareggio, prima_uscita: float, sotto_soglia: bool, resa_attesa: float, casi: int`, e stato con default: `stato: str = "in attesa"` (valori: `in attesa`, `aperta`, `meta chiusa`, `uscita domani`, `chiusa`), `ingresso, data_ingresso, stop, pareggio_attivo (False), prezzo_meta, data_meta, prezzo_uscita, data_uscita, ultimo_giorno, ultimo_prezzo, motivo, giorni_senza_dati (0)`
  - `avanza(op: Operazione, giorno: str, o: float, h: float, l: float, c: float, sma20: float) -> list[str]`: applica il giorno (spec §3) e restituisce i codici evento in ordine tra `ingresso`, `stop`, `pareggio_stop`, `apertura_sotto_stop`, `pareggio`, `prima_uscita`, `sotto_media`, `uscita_finale`; aggiorna `ultimo_giorno` e `ultimo_prezzo`. Non fa nulla su un'operazione `chiusa`
  - `risultato_r(op) -> float | None` e `rendimento(op) -> float | None`: media delle due metà se c'è `prezzo_meta`, altrimenti uscita unica; `None` se non chiusa. R = `(prezzo − ingresso) / r`; rendimento = `prezzo / ingresso − 1`

Algoritmo di `avanza` (in quest'ordine):
1. `in attesa` → `ingresso = o`, `stop = stop_iniziale`, stato `aperta`, evento `ingresso`; se `o <= stop_iniziale` → chiusa a `o`, evento `apertura_sotto_stop`, fine
2. `uscita domani` → chiusa a `o`, evento `uscita_finale`, fine
3. se `l <= stop` → chiusa a `min(o, stop)`; evento `pareggio_stop` se `pareggio_attivo` altrimenti `stop`; fine
4. stato `aperta` e `h >= prima_uscita` → `prezzo_meta = max(o, prima_uscita)`, stato `meta chiusa`, evento `prima_uscita`
5. non `pareggio_attivo` e `h >= pareggio` → `pareggio_attivo = True`, `stop = ingresso`, evento `pareggio`
6. stato `meta chiusa` e `c < sma20` → stato `uscita domani`, evento `sotto_media`

- [ ] **Passo 1: scrivere i test** (operazione con riferimento 100, r 4: stop 96, pareggio 104, prima uscita 108)
  - `test_atr_wilder`: barre con H−L costante 2 e chiusure ferme → `atr14` ultima riga == 2
  - `test_calcola_livelli`: ultima chiusura 100, ATR 2, `atr_mult=2` → `Livelli(100, 4, 96, 104, 108)`
  - `test_atr_nullo_niente_livelli`: prezzi fermi con H==L → `None`
  - `test_ingresso_e_stop`: giorno (100, 101, 95, 96) → eventi `["ingresso", "stop"]`, chiusa a 96, `risultato_r == -1`
  - `test_apertura_sotto_stop`: apertura 94 → chiusa a 94, eventi `["ingresso", "apertura_sotto_stop"]`, `risultato_r == -1.5`
  - `test_stop_prima_degli_obiettivi`: giorno (100, 109, 95, 107) → chiusa a 96 (caso peggiore), nessun `prima_uscita`
  - `test_pareggio_dal_giorno_dopo`: giorno 1 (100, 105, 99, 104) → `pareggio`, stop 100; giorno 2 (103, 103, 99.5, 100) → chiusa a 100, evento `pareggio_stop`, `risultato_r == 0`
  - `test_percorso_completo`: giorno 1 (100, 105, 99, 104); giorno 2 (104, 109, 103, 108, sma 101) → metà a 108; giorno 3 (110, 115, 109, 114, sma 103); giorno 4 (113, 113, 105, 106, sma 107) → `sotto_media`; giorno 5 apertura 105 → `uscita_finale`; `risultato_r == (2 + 1.25) / 2`
  - `test_apertura_sopra_2r`: giorno d'ingresso apertura 100, giorno 2 apertura 110 → metà a 110
  - `test_chiusa_non_cambia`: `avanza` su un'operazione chiusa restituisce `[]`

- [ ] **Passo 2: eseguire** `pytest tests/test_operazione.py tests/test_segnali.py -v`. Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire i test.** Atteso: PASS
- [ ] **Passo 5: commit** `feat: livelli e regole giorno per giorno delle operazioni`

---

### Compito 2: Storico in R e prova fuori campione

**File:**
- Crea: `agente/storico_r.py`; Elimina: `agente/probabilita.py`, `tests/test_probabilita.py`
- Test: `tests/test_storico_r.py`

**Interfacce:**
- Consuma: `calcola_indicatori`, `calcola_situazione`, `calcola_livelli` (sulle righe fino a *t*), `Operazione`, `avanza`, `risultato_r`
- Produce:
  - `simula_storico(prezzi: dict[str, pd.DataFrame], atr_mult: float) -> pd.DataFrame`: per ogni simbolo e ogni riga *t* con situazione e livelli validi, un'operazione che entra all'apertura di *t+1* e avanza fino alla chiusura o alla fine dei dati. Colonne: `simbolo, data_segnale, situazione, data_uscita, chiusa (bool), risultato_r, esito` (`stop` | `pareggio` | `prima_uscita` | `apertura_sotto_stop` | `aperta`). Per velocità: indicatori calcolati una volta per simbolo; i livelli di *t* si leggono dalle colonne (`Close`, `atr14`) senza ricalcolare
  - `costruisci_tabella_r(storico, fino_a: pd.Timestamp | None, casi_minimi: int, casi_virtuali: int) -> pd.DataFrame`: solo operazioni `chiusa` con `data_uscita <= fino_a`; indice `situazione`, colonne `casi, resa_grezza, resa, pct_stop, pct_2r`; `resa = (somma_r + casi_virtuali × media) / (casi + casi_virtuali)`, `media` = resa media di tutte le operazioni usate, in `attrs["media"]`
  - `cerca(tabella, situazione) -> dict | None`: `{"resa", "casi", "pct_stop", "pct_2r"}`
  - `prova_fuori_campione_r(storico, casi_minimi, casi_virtuali, soglia: float) -> dict`: taglio = ultima `data_segnale` − 365 giorni; tabella con `fino_a = taglio`; poi, giorno per giorno dopo il taglio, se non c'è un'operazione in corso (`giorno >= data_uscita` della precedente) prende tra le operazioni con quel `data_segnale` quella con `resa` più alta e ≥ soglia. Restituisce `{"dal", "al", "operazioni", "ancora_aperte", "resa_annunciata", "resa_reale", "pct_stop", "pct_2r"}` (valori `None` se nessuna operazione chiusa)

- [ ] **Passo 1: scrivere i test**
  - `test_simula_salita_costante`: 120 giorni in salita regolare con H/L ±1 → nessuna operazione con esito `stop` dopo il riscaldamento e almeno una `prima_uscita`
  - `test_simula_usa_avanza`: su una serie costruita a mano, il `risultato_r` della riga *t* è uguale a quello ottenuto chiamando `avanza` a mano sui giorni successivi
  - `test_nessuna_sbirciata`: aggiungere giorni dopo la `data_uscita` di un'operazione non ne cambia il risultato
  - `test_tabella_correzione_e_scarto`: situazione A con 40 operazioni a +1R e B con 40 a −1R (media generale 0) → `resa` di A ≈ 40/70; situazione C con 29 operazioni assente
  - `test_tabella_ignora_aperte`
  - `test_prova_una_posizione_alla_volta`: due segnali sovrapposti → conta solo il primo
  - `test_prova_chiavi`: su dati casuali di 3 anni restituisce tutte le chiavi

- [ ] **Passo 2: eseguire** `pytest tests/test_storico_r.py -v`. Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire i test.** Atteso: PASS
- [ ] **Passo 5: commit** `feat: storico delle operazioni in R e prova fuori campione`

---

### Compito 3: Scelta per resa in R e testi Gemini

**File:**
- Modifica: `agente/scelta.py`, `agente/spiegazione.py`, `config.yaml`, `agente/config.py`
- Test: `tests/test_scelta.py`, `tests/test_spiegazione.py`, `tests/test_config.py`

**Interfacce:**
- Consuma: `storico_r.cerca`, `calcola_livelli`
- Produce:
  - Config: `+ atr_mult: float`, `+ soglia_r: float`, `+ email_destinatario: str`; `soglia_prob` rimossa
  - `Scelta`: campi `prob`/`rend_medio` sostituiti da `resa: float | None`, `pct_stop: float | None`, `pct_2r: float | None`; nuovo `livelli: Livelli | None`
  - `scegli(mercato, prezzi, tabella, trova_notizie, giudica, soglia: float, atr_mult: float, max_candidati=5, studio=False) -> Scelta`: come prima ma ordina per `resa`; i titoli con `calcola_livelli` `None` sono esclusi; note: sotto soglia → "Sotto soglia: solo per studio, non per investire."; nessun candidato → "Oggi nessun titolo ha una resa storica di almeno +0,10R: meglio stare fermi." (valore dalla soglia)
  - `scrivi_testi`: la scheda contiene `resa, casi, pct_stop, pct_2r, livelli (riferimento, stop, pareggio, prima_uscita)`; il prompt spiega il piano (ingresso all'apertura, stop, pareggio a +1R, metà a +2R, resto fino alla media a 20) e chiede nel `rischio` di dire quanto si perde se scatta lo stop in percentuale

- [ ] **Passo 1: adattare i test** di scelta (tabella con colonna `resa`, soglia 0.10, nota "+0,10R"; nuovo `test_atr_nullo_escluso`), spiegazione (`test_prompt_contiene_livelli`: il prompt contiene lo stop "96,00" e "+0,25R") e config (`cfg.soglia_r == 0.10`, `cfg.atr_mult == 2.0`)
- [ ] **Passo 2: eseguire.** Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire** `pytest tests/test_scelta.py tests/test_spiegazione.py tests/test_config.py -v`. Atteso: PASS
- [ ] **Passo 5: commit** `feat: scelta per resa in R`

---

### Compito 4: Archivio e controllo serale delle operazioni

**File:**
- Crea: `agente/operazioni.py`; Modifica: `agente/dati.py`, `agente/archivio.py`; Elimina: `agente/verifica.py`, `tests/test_verifica.py`
- Test: `tests/test_operazioni.py`, `tests/test_dati.py`, `tests/test_archivio.py`

**Interfacce:**
- Produce:
  - `dati.scarica_dal(simboli: list[str], dal: date) -> dict[str, pd.DataFrame]`: barre giornaliere da `dal` a oggi (stesse regole di pulizia di `scarica_prezzi`, senza minimo di righe e senza scartare oggi)
  - `leggi_operazioni(percorso) -> list[Operazione]`, `salva_operazioni(ops, percorso)`: CSV con un campo per colonna, in ordine di `data_segnale`
  - `nuova_operazione(scelta: Scelta, giorno: date) -> Operazione`: `id = f"{giorno}-{mercato}"`, `data_segnale` = giorno della proposta
  - `aperta_nel_mercato(ops, mercato) -> Operazione | None`
  - `Messaggio` dataclass: `operazione_id, nome, evento, testo`
  - `aggiorna_operazioni(ops, barre: Callable[[list[str], date], dict[str, pd.DataFrame]], oggi: date, chiusa: Callable[[str, date], bool]) -> list[Messaggio]`: per ogni operazione non chiusa applica `avanza` ai giorni con data > `ultimo_giorno` (o ≥ `data_segnale` se mai controllata, escluso il `data_segnale` stesso), ≤ oggi e con seduta chiusa; `sma20` calcolata sulle barre scaricate (dal `data_segnale` − 45 giorni); se il simbolo non ha barre nuove incrementa `giorni_senza_dati` e, da 2 in su, produce l'evento `senza_dati`
  - testi dei messaggi (spec §5), per esempio `stop` → "🔴 Campari: stop toccato a 6,38 €. Operazione chiusa a −1,00R."
  - `archivio.py`: restano solo `leggi_oggi`, `salva_oggi`

- [ ] **Passo 1: scrivere i test**
  - `test_salva_e_rileggi_operazioni`
  - `test_aggiorna_percorso_completo`: barre finte che portano a pareggio, +2R e uscita → messaggi nell'ordine giusto, stato `chiusa`
  - `test_giorni_applicati_una_volta`: due chiamate consecutive con le stesse barre → la seconda non produce messaggi
  - `test_recupero_piu_giorni`: tre giorni non controllati applicati in ordine
  - `test_seduta_non_chiusa_non_applicata`
  - `test_titolo_senza_dati_segnalato`: 2 sere senza barre → evento `senza_dati`, operazione non chiusa
  - `test_aperta_nel_mercato`
  - `test_scarica_dal` (download finto, chiede `start`)

- [ ] **Passo 2: eseguire.** Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire** `pytest tests/test_operazioni.py tests/test_dati.py tests/test_archivio.py -v`. Atteso: PASS
- [ ] **Passo 5: commit** `feat: archivio e controllo serale delle operazioni`

---

### Compito 5: Email con Resend

**File:**
- Crea: `agente/posta.py`
- Test: `tests/test_posta.py`

**Interfacce:**
- Produce:
  - `invia(oggetto: str, html: str, destinatario: str, chiave: str | None, apri=urllib.request.urlopen) -> bool`: POST `https://api.resend.com/emails` con JSON `{"from": "Maestro del mattino <onboarding@resend.dev>", "to": [destinatario], "subject", "html"}` e header `Authorization: Bearer <chiave>`, timeout 20 s; `False` (con log) se chiave assente, errore HTTP o rete
  - `email_mattina(schede: list[dict], url_pagina: str) -> tuple[str, str] | None`: `None` se nessuna scheda ha una nuova operazione; oggetto "📈 Nuova operazione: Campari" (più titoli separati da virgola); corpo con tabella dei livelli e quantità, etichetta "solo studio" se presente, link alla pagina
  - `email_sera(messaggi: list[Messaggio], url_pagina: str) -> tuple[str, str] | None`: `None` se lista vuota; oggetto "🔔 Maestro del mattino: N aggiornamenti"

- [ ] **Passo 1: scrivere i test**
  - `test_invia_corpo_e_header`: apertura finta che registra la richiesta → URL, header Bearer, JSON con `to == ["x@y.it"]`
  - `test_senza_chiave_non_invia`
  - `test_errore_resend_non_blocca`: l'apertura solleva `HTTPError` → `False`, nessuna eccezione
  - `test_email_sera_vuota_none`, `test_email_mattina_senza_operazioni_none`
  - `test_email_mattina_livelli`: contiene "Stop" con il prezzo all'italiana e "solo studio" quando serve

- [ ] **Passo 2: eseguire** `pytest tests/test_posta.py -v`. Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire.** Atteso: PASS
- [ ] **Passo 5: commit** `feat: email con Resend`

---

### Compito 6: Statistiche in R e conti simulati

**File:**
- Riscrivi: `agente/statistiche.py`
- Test: `tests/test_statistiche.py`

**Interfacce:**
- Consuma: `Operazione`, `risultato_r`, `rendimento`
- Produce:
  - `costo_ordine(mercato, valore_eur, prezzo, costi, cambio) -> float` (un solo ordine; stesse formule della v1, cambio incluso per USA)
  - `simula_conto(ops, capitale: dict[str, float], costi, cambi, tasse_pct) -> dict`: per mercato, in ordine di `data_uscita`, solo operazioni chiuse e non `sotto_soglia`: `nuovo = capitale × (1 + rendimento) − costi`, dove i costi sono 1 ordine d'ingresso + 1 o 2 ordini d'uscita (2 se c'è `prezzo_meta`, ciascuno su metà del valore). Restituisce le stesse chiavi della v1
  - `calcola_statistiche(ops, cfg, cambi, indici) -> dict` con: `consigli` e `studio` (ciascuno `{"chiuse", "resa_media", "pct_stop", "pct_pareggio", "pct_2r", "somma_r"}`), `aperte` (numero), `conto_simulato`, `conto_ibkr`, `indici` (come v1, dalla prima `data_ingresso`)

- [ ] **Passo 1: riscrivere i test**: `test_costo_ordine_ita_minimo` (100 € → 1,25), `test_costo_usa_piccolo` (100 €, cambio 1,10, prezzo 200 → 0,35/1,10 + 0,03), `test_conto_con_meta` (operazione +2R su metà e +1R sul resto, r=4% → rendimento 6%, costi zero → 106), `test_conto_esclude_studio`, `test_statistiche_vuote`, `test_percentuali_esiti`
- [ ] **Passo 2: eseguire.** Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire** `pytest tests/test_statistiche.py -v`. Atteso: PASS
- [ ] **Passo 5: commit** `feat: statistiche in R`

---

### Compito 7: Pagina

**File:**
- Riscrivi: `agente/pagina.py` (le parti su previsioni), `agente/templates/index.html`
- Test: `tests/test_pagina.py`

**Interfacce:**
- Produce:
  - `disegna_grafico(prezzi, nome, percorso, livelli: Livelli | None = None)`: come prima più linee orizzontali tratteggiate per stop (rosso), pareggio (giallo), prima uscita (verde)
  - `genera_sito(cartella, oggi: dict, ops: list[Operazione], stat: dict, prova: dict, aggiornato: datetime) -> Path`
  - Sezioni: **Oggi** (scheda nuova operazione: tabella livelli con prezzo e distanza in %, quantità e perdita massima in euro con `ibkr_capitale_eur`, resa storica "+0,25R su 140 operazioni", percentuali stop/+2R, testi, notizie; oppure scheda "Posizione aperta" con stato), **Posizioni aperte**, **Storico** (data ingresso, titolo, ingresso, uscita, risultato R con ✅/❌/➖, motivo), **Statistiche** (consigli e studio separati, conti, prova fuori campione in R, nota sulle commissioni con 100 €)
  - Quantità: Italia `floor(capitale / riferimento)` azioni con avviso se 0; USA `capitale × cambio / riferimento` arrotondato a 4 decimali

- [ ] **Passo 1: riscrivere i test**: `test_scheda_livelli` (contiene "96,00", "104,00", "108,00", "+0,25R"), `test_scheda_posizione_aperta`, `test_quantita_italia_zero` ("con 100 € non puoi comprarne nemmeno una"), `test_storico_risultato_r`, `test_statistiche_vuote`, `test_grafico_con_livelli`, più i test v1 ancora validi (footer, data analisi, analisi vecchia, testi mancanti)
- [ ] **Passo 2: eseguire.** Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire** `pytest tests/test_pagina.py -v`. Atteso: PASS
- [ ] **Passo 5: commit** `feat: pagina delle operazioni`

---

### Compito 8: Comandi mattina, sera, tabella

**File:**
- Modifica: `agente/main.py`, `.github/workflows/agente.yml`, `README.md`
- Test: `tests/test_main.py`

**Interfacce:**
- `Servizi`: `scarica_prezzi_giorno` sostituito da `scarica_dal`; aggiunto `invia: Callable[[str, str], bool]`
- `esegui_tabella`: `simula_storico` → `costruisci_tabella_r` → `tabella_{codice}.csv`; `prova_fuori_campione_r` → `prova_{codice}.json`
- `esegui_mattina`: per ogni mercato aperto **senza** `aperta_nel_mercato` → scelta, livelli, grafico con livelli, testi, `nuova_operazione`; con posizione aperta → scheda di stato. Salva `operazioni.csv`, `oggi.json`, pubblica, poi `email_mattina` e `invia`
- `esegui_sera`: `aggiorna_operazioni` (chiusa = `seduta_chiusa` con `servizi.adesso()`), salva, pubblica, poi `email_sera` e `invia`
- `url_pagina` costante: `https://giobo76.github.io/maestro-del-mattino/`
- workflow: `RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}` nell'ambiente del passo che esegue l'agente
- README: sezione "Come inserire un'operazione su IBKR" (bracket con stop, take profit su metà, stop regolabile a pareggio)

- [ ] **Passo 1: adattare i test**: `test_mattina_crea_operazioni` (2 operazioni `in attesa`, 1 email inviata), `test_mattina_non_apre_seconda_posizione`, `test_mercato_chiuso_saltato`, `test_sera_aggiorna_e_avvisa` (barre finte che toccano lo stop → email con "stop"), `test_sera_senza_novita_niente_email`, `test_dati_non_disponibili_un_mercato`, `test_deve_partire_*` invariati
- [ ] **Passo 2: eseguire.** Atteso: FAIL
- [ ] **Passo 3: implementare**
- [ ] **Passo 4: eseguire tutta la suite** `pytest -q`. Atteso: tutti PASS
- [ ] **Passo 5: commit** `feat: comandi per le operazioni`

---

### Compito 9: Prova reale e pubblicazione

- [ ] **Passo 1:** `python -m agente tabella --dati dati_prova --sito sito_prova`. Atteso: tabelle con almeno 30 situazioni per mercato e `prova_*.json`; durata annotata (deve stare sotto i 15 minuti su Actions)
- [ ] **Passo 2:** `python -m agente mattina --forza --giorno 2026-10-19 --dati dati_prova --sito sito_prova` con Gemini; controllare la pagina a 360 px
- [ ] **Passo 3:** Giovanni crea la chiave Resend (guida) e la inserisce in GitHub come segreto `RESEND_API_KEY`; prova di invio dal PC
- [ ] **Passo 4:** riportare a Giovanni i numeri della prova fuori campione in R, anche se deludenti
- [ ] **Passo 5:** archiviare `dati/previsioni.csv` (`git rm`), push, lanciare su Actions `tabella` e `mattina` con forza; verificare la pagina online
- [ ] **Passo 6: commit** finale se servono correzioni di configurazione
