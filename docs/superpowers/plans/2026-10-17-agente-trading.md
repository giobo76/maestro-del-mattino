# Agente "Maestro del mattino": piano di costruzione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:subagent-driven-development (consigliata) oppure superpowers:executing-plans per eseguire il piano un compito alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** programma Python gratuito che ogni mattina sceglie un titolo italiano e uno americano con la probabilità storica più alta di salire tra apertura e chiusura, lo spiega in italiano e pubblica tutto su una pagina GitHub Pages con storico e statistiche.

**Architettura:** pacchetto `agente/` con un file per responsabilità (dati, segnali, probabilità, scelta, spiegazione, verifica, statistiche, pagina). Due comandi (`mattina`, `sera`) più `tabella` (ricalcolo settimanale), lanciati da GitHub Actions. Lo stato vive in file CSV/JSON in `dati/`, che il workflow salva nell'archivio a ogni esecuzione.

**Tecnologie:** Python 3.12 (Actions) / 3.13 (PC di Giovanni), pandas, yfinance, feedparser, exchange_calendars, google-genai, jinja2, matplotlib, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-10-17-agente-trading-design.md`

## Vincoli globali

- Tutto il testo visibile sulla pagina è in **italiano**; nomi di file, funzioni e variabili in italiano come nella spec
- Solo servizi gratuiti; nessuna chiave nel codice: la chiave Gemini si legge da `GEMINI_API_KEY`
- I test non usano internet: Yahoo, i feed RSS e Gemini vengono sempre simulati
- Segnali calcolati **solo con dati fino alla chiusura del giorno precedente**; l'esito è **apertura → chiusura del giorno della previsione**
- Soglia minima casi: **30**; casi virtuali per la correzione: **30**; soglia di probabilità: **0,55**
- Nessun ordine automatico sul conto IBKR
- Footer della pagina, testo esatto: "Strumento personale a scopo didattico. Non è una consulenza finanziaria."
- Gemini non produce numeri mostrati sulla pagina: probabilità, casi, prezzi e rendimenti vengono sempre dal calcolo

## Punti di attenzione (Review Focus)

1. **Riga parziale di oggi da Yahoo**: se Yahoo restituisce una riga con la data di oggi, la mattina va scartata prima di calcolare i segnali. Test in Compito 4 (`test_scarta_riga_di_oggi`)
2. **Simbolo sparito o rinominato** (titolo uscito dal FTSE MIB, fusione): viene escluso con un avviso nel log, il programma non si ferma. Test in Compito 4 (`test_simbolo_senza_dati_escluso`)
3. **Gemini risponde con JSON rotto o testo vuoto**: la scheda esce senza testi e con la nota "spiegazione non disponibile oggi". Test in Compito 5 (`test_json_rotto_restituisce_none`)
4. **Borsa aperta in un solo mercato** (es. Thanksgiving o 15 agosto): l'altro mercato viene saltato e la pagina lo scrive. Test in Compito 10 (`test_mercato_chiuso_saltato`)
5. **La sera mancano i dati di un giorno**: la previsione resta "in attesa" e viene ricontrollata la sera dopo, non segnata come sbagliata. Test in Compito 7 (`test_esito_mancante_resta_in_attesa`)

---

## Struttura dei file

```
requirements.txt
config.yaml                 liste titoli, soglie, costi, modello Gemini
agente/__init__.py
agente/__main__.py          python -m agente <comando>
agente/config.py            carica config.yaml
agente/calendario.py        giorni di borsa aperta, ora italiana
agente/segnali.py           indicatori e "situazione"
agente/probabilita.py       tabella storica, esiti, simulazione scelte
agente/dati.py              prezzi (Yahoo) e notizie (RSS)
agente/spiegazione.py       Gemini: giudizio notizie e testi
agente/scelta.py            titolo del giorno per mercato
agente/archivio.py          lettura/scrittura previsioni.csv e oggi.json
agente/verifica.py          esiti serali
agente/statistiche.py       costi IBKR, conti simulati, percentuali
agente/pagina.py            HTML + grafici
agente/templates/index.html
agente/main.py              comandi mattina / sera / tabella
tests/...
.github/workflows/agente.yml
dati/                       previsioni.csv, oggi.json, tabella_ITA.csv, tabella_USA.csv
sito/                       pagina generata (non salvata nell'archivio)
```

---

### Compito 1: Base del progetto e configurazione

**File:**
- Crea: `requirements.txt`, `config.yaml`, `agente/__init__.py`, `agente/config.py`, `.gitignore`
- Test: `tests/test_config.py`

**Interfacce:**
- Produce: `carica_config(percorso: str = "config.yaml") -> Config`, con `Config` dataclass:
  `mercati: dict[str, Mercato]`, `soglia_prob: float`, `casi_minimi: int`, `casi_virtuali: int`, `anni_storico: int`, `gemini_modello: str`, `costi: dict`, `conto_simulato_eur: float`, `ibkr_capitale_eur: float`, `ibkr_mercati: list[str]`.
  `Mercato` dataclass: `codice: str` ("ITA" | "USA"), `nome: str`, `calendario: str` ("XMIL" | "XNYS"), `indice: str` ("FTSEMIB.MI" | "^GSPC"), `valuta: str` ("EUR" | "USD"), `lingua_notizie: str` ("it" | "en"), `titoli: dict[str, str]` (simbolo → nome)

- [ ] **Passo 1: scrivere `requirements.txt`**: `pandas>=2.2`, `numpy>=1.26`, `yfinance>=0.2.50`, `feedparser>=6.0`, `exchange_calendars>=4.5`, `google-genai>=1.0`, `jinja2>=3.1`, `matplotlib>=3.8`, `PyYAML>=6.0`, `pytest>=8.0`. Creare un ambiente virtuale `.venv` e installare. `.gitignore`: `.venv/`, `sito/`, `__pycache__/`, `.env`

- [ ] **Passo 2: scrivere `config.yaml`** con questi valori:
  - `soglia_prob: 0.55`, `casi_minimi: 30`, `casi_virtuali: 30`, `anni_storico: 5`, `gemini_modello: gemini-2.5-flash`, `conto_simulato_eur: 1000`, `ibkr_capitale_eur: 100`, `ibkr_mercati: [USA]`
  - `costi`: `ita_pct: 0.0005`, `ita_minimo_eur: 1.25`, `usa_per_azione_usd: 0.0035`, `usa_minimo_usd: 0.35`, `usa_massimo_pct: 0.01`, `cambio_pct: 0.0003`, `tasse_pct: 0.26`
  - `mercati.ITA.titoli` (FTSE MIB): A2A.MI, AMP.MI, AZM.MI, BAMI.MI, BMED.MI, BMPS.MI, BPE.MI, BZU.MI, CPR.MI, DIA.MI, ENEL.MI, ENI.MI, ERG.MI, RACE.MI, FBK.MI, G.MI, HER.MI, IP.MI, ISP.MI, INW.MI, IG.MI, LDO.MI, MB.MI, MONC.MI, NEXI.MI, PIRC.MI, PST.MI, PRY.MI, REC.MI, SRG.MI, SPM.MI, STLAM.MI, STMMI.MI, TIT.MI, TEN.MI, TRN.MI, UCG.MI, UNI.MI, BC.MI, AVIO.MI, con nome leggibile
  - `mercati.USA.titoli`: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, JPM, V, MA, UNH, XOM, LLY, JNJ, PG, HD, COST, ABBV, MRK, CVX, KO, PEP, BAC, WMT, NFLX, AMD, ADBE, CRM, ORCL, CSCO, INTC, QCOM, TXN, IBM, MU, AMAT, LRCX, KLAC, PANW, NOW, UBER, PYPL, SBUX, NKE, MCD, DIS, CMCSA, T, VZ, PFE, BMY, GILD, AMGN, TMO, ABT, DHR, MDT, ISRG, CVS, CI, GS, MS, C, WFC, SCHW, AXP, BLK, BA, CAT, DE, GE, HON, LMT, RTX, UPS, FDX, UNP, F, GM, COP, SLB, OXY, NEE, DUK, SO, LIN, PLD, AMT, BKNG, ABNB, MRNA, PLTR, SHOP, COIN, SNOW, CRWD, DELL, SMCI, ARM
  - Le liste si verificano nel Compito 11 con dati veri

- [ ] **Passo 3: scrivere il test** `test_carica_config`: carica `config.yaml` e verifica `cfg.soglia_prob == 0.55`, `cfg.casi_minimi == 30`, `set(cfg.mercati) == {"ITA", "USA"}`, `cfg.mercati["ITA"].calendario == "XMIL"`, `len(cfg.mercati["USA"].titoli) >= 90`, `"ENI.MI" in cfg.mercati["ITA"].titoli`

- [ ] **Passo 4: eseguire** `pytest tests/test_config.py -v`. Atteso: FAIL (modulo mancante)

- [ ] **Passo 5: implementare `carica_config`** con `yaml.safe_load`

- [ ] **Passo 6: eseguire il test.** Atteso: PASS

- [ ] **Passo 7: commit** `feat: base del progetto e configurazione`

---

### Compito 2: Segnali e "situazione"

**File:**
- Crea: `agente/segnali.py`
- Test: `tests/test_segnali.py`

**Interfacce:**
- Consuma: niente
- Produce:
  - `calcola_indicatori(prezzi: pd.DataFrame) -> pd.DataFrame`: in ingresso colonne `Open, High, Low, Close, Volume` con `DatetimeIndex` crescente; aggiunge `sma20, sma50, rsi14, macd, macd_segnale, vol_media20, max20_prec, rend_giorno`
  - `calcola_situazione(ind: pd.DataFrame) -> pd.Series`: per ogni riga la stringa `"trend=..|rsi=..|macd=..|vol=..|rottura=..|giorno=.."`, oppure `NaN` se mancano dati (prime 50 righe)
  - `COMPONENTI = ["trend", "rsi", "macd", "vol", "rottura", "giorno"]`

Regole (riga *t* usa solo dati fino alla chiusura di *t*):
- `trend`: `su` se Close > sma20 e Close > sma50; `giu` se sotto entrambe; altrimenti `misto`
- `rsi`: RSI 14 di Wilder (`ewm(alpha=1/14, adjust=False)` su guadagni e perdite); `basso` < 30, `alto` > 70, altrimenti `normale`
- `macd`: EMA12 − EMA26, segnale = EMA9 del macd; `rialzo` se macd attraversa sopra il segnale tra *t−1* e *t*, `ribasso` se sotto, altrimenti `nessuno`
- `vol`: `alto` se Volume_t > 2 × media dei volumi da *t−20* a *t−1*, altrimenti `normale`
- `rottura`: `si` se Close_t > massimo degli High da *t−20* a *t−1*, altrimenti `no`
- `giorno`: rend_giorno = Close_t / Close_{t−1} − 1; `forte_su` > 0,02, `forte_giu` < −0,02, altrimenti `normale`

- [ ] **Passo 1: scrivere i test**
  - `test_rsi_valori_noti`: serie di 15 chiusure sempre in salita → `rsi14` dell'ultima riga == 100; serie alternata +1/−1 → RSI tra 45 e 55
  - `test_trend_su`: 60 chiusure in salita costante → ultima situazione contiene `trend=su`
  - `test_volume_alto`: volumi costanti 1000, ultimo 2500 → `vol=alto`; ultimo 1900 → `vol=normale`
  - `test_rottura`: High costante 10, ultima Close 10,5 → `rottura=si`
  - `test_giorno_forte_giu`: ultima chiusura −3% → `giorno=forte_giu`
  - `test_situazione_nan_inizio`: le prime 49 righe sono `NaN`
  - `test_nessuna_sbirciata`: la situazione della riga *k* calcolata su `prezzi[:k+1]` è uguale a quella calcolata sull'intera serie

- [ ] **Passo 2: eseguire** `pytest tests/test_segnali.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare** con pandas vettoriale (`rolling`, `ewm`, `shift`)

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: segnali tecnici e situazione`

---

### Compito 3: Probabilità storiche

**File:**
- Crea: `agente/probabilita.py`
- Test: `tests/test_probabilita.py`

**Interfacce:**
- Consuma: `calcola_indicatori`, `calcola_situazione`
- Produce:
  - `prepara_storico(prezzi: dict[str, pd.DataFrame]) -> pd.DataFrame`: una riga per (simbolo, data *t*) con colonne `simbolo, data, situazione, data_esito, salito, rend`. `data_esito` è la riga *t+1*; `salito = Close_{t+1} > Open_{t+1}`, `rend = Close_{t+1}/Open_{t+1} − 1`. Righe con situazione `NaN` o senza *t+1* escluse
  - `costruisci_tabella(storico: pd.DataFrame, fino_a: pd.Timestamp | None, casi_minimi: int, casi_virtuali: int) -> pd.DataFrame`: usa solo righe con `data_esito <= fino_a`; indice `situazione`, colonne `casi, salite, prob_grezza, prob, rend_medio`; `prob = (salite + casi_virtuali × media) / (casi + casi_virtuali)`, dove `media` = quota di salite su tutte le righe usate; esclude `casi < casi_minimi`; attributo `tabella.attrs["media"]`
  - `cerca(tabella: pd.DataFrame, situazione: str) -> dict | None`: `{"prob", "casi", "rend_medio"}` oppure `None`
  - `simula_scelte(storico: pd.DataFrame, tabella: pd.DataFrame, dal: pd.Timestamp, soglia: float) -> pd.DataFrame`: per ogni `data_esito >= dal`, sceglie la riga con `prob` più alta; se < soglia, nessuna scelta. Colonne `data_esito, simbolo, prob, salito, rend`
  - `prova_fuori_campione(storico: pd.DataFrame, casi_minimi: int, casi_virtuali: int, soglia: float) -> dict`: taglio = ultima `data_esito` − 365 giorni; tabella costruita con `fino_a = taglio`, simulazione dal giorno dopo il taglio. Restituisce `{"dal", "al", "giorni_con_scelta", "prob_media_annunciata", "percentuale_reale", "rend_medio"}`

- [ ] **Passo 1: scrivere i test**
  - `test_esito_apertura_chiusura`: riga *t+1* con Open 10, Close 10,2 → `salito == True`, `rend ≈ 0,02`
  - `test_correzione_pochi_casi`: 40 casi con 34 salite, media generale 0,5, casi_virtuali 30 → `prob ≈ (34 + 15)/70 = 0,7`
  - `test_scarta_sotto_30_casi`: situazione con 29 casi assente dalla tabella
  - `test_fino_a_non_usa_futuro`: righe con `data_esito` dopo `fino_a` non cambiano la tabella
  - `test_simula_rispetta_soglia`: tutte le prob < 0,55 → DataFrame vuoto
  - `test_prova_fuori_campione_chiavi`: su dati sintetici casuali di 3 anni restituisce tutte le chiavi e `0 <= percentuale_reale <= 1`

- [ ] **Passo 2: eseguire** `pytest tests/test_probabilita.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare** (`groupby("situazione").agg(...)` per la tabella; `merge` con la tabella + `idxmax` per data in `simula_scelte`)

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: tabella delle probabilita storiche`

---

### Compito 4: Calendario e download dei dati

**File:**
- Crea: `agente/calendario.py`, `agente/dati.py`
- Test: `tests/test_calendario.py`, `tests/test_dati.py`

**Interfacce:**
- Produce:
  - `adesso_roma() -> datetime` (fuso `Europe/Rome`)
  - `borsa_aperta(calendario: str, giorno: date) -> bool` con `exchange_calendars.get_calendar(calendario).is_session(...)`
  - `scarica_prezzi(simboli: list[str], anni: int, oggi: date) -> dict[str, pd.DataFrame]`: `yf.download(simboli, period=f"{anni}y", group_by="ticker", auto_adjust=True, progress=False)`; fino a 3 tentativi con 5 s di pausa, poi `DatiNonDisponibili`. Per ogni simbolo: scarta le righe con data `>= oggi`, toglie le righe con `Close` o `Open` vuoti, esclude (con `logging.warning`) i simboli con meno di 60 righe
  - `scarica_prezzi_giorno(simboli: list[str], giorno: date) -> dict[str, tuple[float, float]]`: (apertura, chiusura) del giorno indicato, solo per i simboli che hanno quella riga
  - `Notizia` dataclass: `titolo: str`, `link: str`, `fonte: str`, `data: datetime`
  - `scarica_notizie(nome: str, simbolo: str, lingua: str, ore: int = 24) -> list[Notizia]`: Google News RSS `https://news.google.com/rss/search?q="{nome}"+when:1d&hl={lingua}` (con `gl`/`ceid` coerenti: `IT`/`IT:it` o `US`/`US:en`) più, per gli USA, Yahoo `https://feeds.finance.yahoo.com/rss/2.0/headline?s={simbolo}&region=US&lang=en-US`. Massimo 10 notizie, le più recenti; un feed che fallisce viene saltato. Il Sole 24 Ore e Milano Finanza arrivano tramite Google News
  - `class DatiNonDisponibili(Exception)`

- [ ] **Passo 1: scrivere i test** (con `monkeypatch` su `yf.download` e `feedparser.parse`)
  - `test_borsa_aperta`: `XMIL` chiusa il 25/12/2026, `XNYS` chiusa il 26/11/2026 (Thanksgiving), `XMIL` aperta il 26/11/2026
  - `test_scarta_riga_di_oggi`: il finto download contiene la data `oggi` → assente dal risultato
  - `test_simbolo_senza_dati_escluso`: un simbolo con tutte le colonne vuote → assente, nessuna eccezione
  - `test_tre_tentativi_poi_errore`: download che solleva sempre → `DatiNonDisponibili` dopo 3 chiamate (pausa simulata)
  - `test_feed_rotto_saltato`: Google News solleva, Yahoo funziona → restituisce le notizie Yahoo

- [ ] **Passo 2: eseguire** `pytest tests/test_calendario.py tests/test_dati.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare** (pausa tra tentativi tramite parametro `pausa_s` per i test)

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: calendario e download di prezzi e notizie`

---

### Compito 5: Spiegazioni con Gemini

**File:**
- Crea: `agente/spiegazione.py`
- Test: `tests/test_spiegazione.py`

**Interfacce:**
- Consuma: `Notizia`
- Produce:
  - `Cervello` Protocol: `genera(prompt: str) -> str`
  - `CervelloGemini(modello: str, chiave: str)`: usa `google.genai.Client(api_key=chiave).models.generate_content(model=modello, contents=prompt, config={"response_mime_type": "application/json"})` e restituisce `.text`
  - `crea_cervello(cfg: Config) -> Cervello | None`: `None` se manca `GEMINI_API_KEY`
  - `giudica_notizie(cervello: Cervello | None, nome: str, notizie: list[Notizia]) -> str | None`: `"positivo" | "neutro" | "negativo"`; `"neutro"` se non ci sono notizie; `None` per errori, JSON rotto, valore fuori elenco o cervello `None`
  - `scrivi_testi(cervello: Cervello | None, scheda: dict, parole_gia_usate: list[str]) -> dict | None`: chiavi `perche, rischio, parola, parola_spiegazione`; `None` per qualsiasi errore o chiave mancante

Prompt (testo in italiano, da scrivere nel codice):
- giudizio: "Sei un analista. Leggi questi titoli di notizie su {nome} delle ultime 24 ore. Rispondi solo con JSON {"giudizio": "positivo"|"neutro"|"negativo"}. Negativo solo se la notizia può far scendere il titolo oggi (indagini, conti sotto le attese, taglio delle stime, declassamenti)."
- testi: scheda con nome, mercato, probabilità, casi, rendimento medio, stati dei segnali e titoli delle notizie; richiesta: "Scrivi per un principiante, in italiano semplice. 'perche': 4-5 frasi che spiegano i segnali e le notizie. 'rischio': 1-2 frasi sul rischio principale di oggi. 'parola': un termine tecnico presente nella scheda e non in questo elenco: {parole_gia_usate}. 'parola_spiegazione': spiegazione con un esempio, massimo 3 frasi. Non scrivere numeri diversi da quelli della scheda. Non promettere guadagni."

- [ ] **Passo 1: scrivere i test** con un `CervelloFinto` che restituisce una stringa fissa o solleva
  - `test_giudizio_valido`: risposta `{"giudizio": "negativo"}` → `"negativo"`
  - `test_nessuna_notizia_neutro`: lista vuota → `"neutro"` senza chiamare il cervello
  - `test_json_rotto_restituisce_none`: risposta `"non è json"` → `None` sia per il giudizio sia per i testi
  - `test_valore_fuori_elenco`: `{"giudizio": "boh"}` → `None`
  - `test_testi_chiave_mancante`: manca `rischio` → `None`
  - `test_cervello_none`: `None` in ingresso → `None`, nessuna eccezione
  - `test_prompt_contiene_parole_usate`: il prompt passato al cervello contiene "RSI" se è nell'elenco delle parole già usate

- [ ] **Passo 2: eseguire** `pytest tests/test_spiegazione.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare**

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: giudizio notizie e spiegazioni con Gemini`

---

### Compito 6: Scelta del titolo del giorno

**File:**
- Crea: `agente/scelta.py`
- Test: `tests/test_scelta.py`

**Interfacce:**
- Consuma: `calcola_indicatori`, `calcola_situazione`, `cerca`, `Notizia`
- Produce:
  - `Scelta` dataclass: `mercato: str`, `simbolo: str | None`, `nome: str | None`, `prob: float | None`, `casi: int | None`, `rend_medio: float | None`, `situazione: str | None`, `giudizio_notizie: str | None`, `notizie: list[Notizia]`, `scartati: list[str]` (simboli scartati per notizie negative), `nota: str` (testo per la pagina, vuoto se tutto normale)
  - `scegli(mercato: Mercato, prezzi: dict[str, pd.DataFrame], tabella: pd.DataFrame, trova_notizie: Callable[[str, str], list[Notizia]], giudica: Callable[[str, list[Notizia]], str | None], soglia: float, max_candidati: int = 5) -> Scelta`

Algoritmo: situazione dell'ultima riga di ogni titolo → `cerca` → candidati ordinati per `prob` decrescente, solo `prob >= soglia`. Per i primi `max_candidati`: scarica le notizie e chiede il giudizio; `"negativo"` → scartato e si passa al successivo; altrimenti è la scelta. Se il giudizio è `None` la scelta resta valida e `nota = "Filtro notizie non disponibile oggi."`. Nessun candidato sopra soglia → `simbolo = None`, `nota = "Oggi nessun titolo supera il 55% di probabilità storica: meglio stare fermi."` (percentuale presa dalla soglia). Tutti i candidati scartati → `simbolo = None`, `nota` che lo dice.

- [ ] **Passo 1: scrivere i test** con tabella e prezzi sintetici e funzioni finte
  - `test_sceglie_prob_piu_alta`
  - `test_scarta_notizie_negative`: il primo è negativo → viene scelto il secondo e il primo è in `scartati`
  - `test_nessuno_sopra_soglia`: `simbolo is None` e la nota contiene "55%"
  - `test_giudizio_non_disponibile`: `giudica` restituisce `None` → scelta valida, nota sul filtro
  - `test_situazione_sconosciuta_ignorata`: un titolo con situazione assente dalla tabella non è candidato

- [ ] **Passo 2: eseguire** `pytest tests/test_scelta.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare**

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: scelta del titolo del giorno`

---

### Compito 7: Archivio e verifica serale

**File:**
- Crea: `agente/archivio.py`, `agente/verifica.py`
- Test: `tests/test_archivio.py`, `tests/test_verifica.py`

**Interfacce:**
- Consuma: `Scelta`
- Produce:
  - `COLONNE = ["data", "mercato", "simbolo", "nome", "prob", "casi", "rend_medio_storico", "situazione", "giudizio_notizie", "apertura", "chiusura", "rend", "salito"]`
  - `leggi_previsioni(percorso: str) -> pd.DataFrame` (vuoto con `COLONNE` se il file non esiste)
  - `aggiungi_previsioni(prev: pd.DataFrame, giorno: date, scelte: list[Scelta]) -> pd.DataFrame`: una riga per ogni scelta con `simbolo` non nullo; se esiste già una riga per (giorno, mercato) la sostituisce
  - `salva_previsioni(prev: pd.DataFrame, percorso: str) -> None`
  - `leggi_oggi(percorso: str) -> dict | None` / `salva_oggi(percorso: str, contenuto: dict) -> None`: JSON con `data`, `schede` (una per mercato: campi di `Scelta`, testi Gemini, percorso del grafico), `fatto_mattina`, `fatto_sera` (date ISO)
  - `registra_esiti(prev: pd.DataFrame, prezzi_giorno: Callable[[list[str], date], dict[str, tuple[float, float]]], oggi: date) -> pd.DataFrame`: per le righe con `salito` vuoto e `data <= oggi` compila `apertura, chiusura, rend, salito`; se il simbolo manca dal risultato, la riga resta vuota

- [ ] **Passo 1: scrivere i test**
  - `test_aggiungi_e_rileggi`: salva e rilegge in `tmp_path`, stessi valori
  - `test_nessun_doppione`: due chiamate per lo stesso giorno e mercato → una sola riga
  - `test_registra_esito`: apertura 10, chiusura 10,3 → `salito == True`, `rend ≈ 0,03`
  - `test_esito_mancante_resta_in_attesa`: il simbolo manca → `salito` resta vuoto, la sera dopo viene compilato
  - `test_previsione_futura_non_toccata`: riga con `data > oggi` resta vuota

- [ ] **Passo 2: eseguire** `pytest tests/test_archivio.py tests/test_verifica.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare** (date salvate come `YYYY-MM-DD`)

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: archivio previsioni e verifica serale`

---

### Compito 8: Costi IBKR e statistiche

**File:**
- Crea: `agente/statistiche.py`
- Test: `tests/test_statistiche.py`

**Interfacce:**
- Consuma: previsioni (`COLONNE`), `COMPONENTI`, `Config`
- Produce:
  - `costo_andata_ritorno(mercato: str, valore_eur: float, prezzo: float, costi: dict, cambio_eur_usd: float) -> float` (in euro, acquisto + vendita): ITA → `2 × max(ita_minimo_eur, ita_pct × valore)`; USA → azioni = valore × cambio / prezzo (frazioni ammesse), per ordine `min(max(usa_minimo_usd, azioni × usa_per_azione_usd), usa_massimo_pct × valore_usd)`, ×2, convertito in euro, più `2 × cambio_pct × valore`. Tobin tax a zero perché si compra e vende in giornata
  - `simula_conto(prev: pd.DataFrame, capitale: dict[str, float], costi: dict, cambi: dict[date, float], tasse_pct: float) -> dict`: ogni giorno con esito, per ogni mercato in `capitale`, reinveste tutto il capitale del mercato: `nuovo = capitale × (1 + rend) − costo`. Restituisce `{"iniziale", "finale_lordo", "tasse", "finale_netto", "andamento": list[(data, valore)]}`; tasse = `tasse_pct × max(0, finale_lordo − iniziale)`
  - `calcola_statistiche(prev: pd.DataFrame, cfg: Config, cambi: dict[date, float], indici: dict[str, pd.Series]) -> dict` con chiavi:
    - `totale`, `azzeccate`, `percentuale` (complessivi) e `per_mercato` (stesse chiavi per mercato)
    - `calibrazione`: fasce di prob annunciata (0,55–0,58, 0,58–0,61, ≥0,61) con percentuale reale
    - `conto_simulato`: `simula_conto` con `conto_simulato_eur` diviso in parti uguali tra i mercati
    - `conto_ibkr`: `simula_conto` con `ibkr_capitale_eur` diviso tra `ibkr_mercati`
    - `indici`: per mercato, rendimento di "compra e tieni" dalla prima previsione all'ultima con esito
    - `segnali`: per ogni coppia componente=stato presente nelle previsioni, casi e percentuale di salite (solo con almeno 5 casi)

- [ ] **Passo 1: scrivere i test** (valori calcolati a mano)
  - `test_costo_ita_minimo`: 100 € → 2,50 €
  - `test_costo_ita_percentuale`: 10.000 € → 10,00 €
  - `test_costo_usa_piccolo`: 100 €, cambio 1,10, prezzo 200 $ → per ordine `min(max(0,35; 0,00193), 1,10) = 0,35 $`; totale `0,70 / 1,10 + 0,06 ≈ 0,696 €`
  - `test_simula_conto_tasse`: 2 giorni +10% e −5%, costi zero, 100 € → lordo 104,50, tasse 1,17, netto 103,33
  - `test_simula_conto_perdita_niente_tasse`
  - `test_statistiche_vuote`: nessuna previsione con esito → `totale == 0`, nessuna eccezione
  - `test_calibrazione_fasce`

- [ ] **Passo 2: eseguire** `pytest tests/test_statistiche.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare**

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: commit** `feat: costi IBKR e statistiche`

---

### Compito 9: Pagina web e grafici

**File:**
- Crea: `agente/pagina.py`, `agente/templates/index.html`
- Test: `tests/test_pagina.py`

**Interfacce:**
- Consuma: contenuto di `oggi.json`, previsioni, dizionario delle statistiche, risultato di `prova_fuori_campione`
- Produce:
  - `disegna_grafico(prezzi: pd.DataFrame, nome: str, percorso: Path) -> None`: ultimi 63 giorni, chiusura + sma20 + sma50, punto sull'ultima chiusura, PNG 800×400 con `matplotlib` backend `Agg`
  - `genera_sito(cartella: Path, oggi: dict, prev: pd.DataFrame, stat: dict, prova: dict, aggiornato: datetime) -> Path`: scrive `index.html` (e copia i grafici) e restituisce il percorso

Contenuto della pagina, in quest'ordine: intestazione "Maestro del mattino" con data e ora dell'aggiornamento; sezione **Oggi** (una scheda per mercato come da spec 3.1, oppure la `nota` se nessuna scelta o mercato chiuso); sezione **Com'è andata** (tabella dalla più recente, ✅/❌/"in attesa"); sezione **Statistiche** (come da spec 3.3, con la frase "I segnali migliori arrivano di solito al 53–60% di probabilità."); footer con il testo esatto dei vincoli globali. CSS interno, una colonna, leggibile su telefono, tema chiaro e scuro con `prefers-color-scheme`. Numeri in formato italiano (virgola decimale, `%` e `€`) tramite un filtro jinja `it_num`.

- [ ] **Passo 1: scrivere i test**
  - `test_pagina_contiene_scheda`: con una scheda ENI la pagina contiene "Eni", "57,0%", "142 casi" e il footer esatto
  - `test_pagina_senza_testi`: scheda con testi `None` → contiene "Spiegazione non disponibile oggi"
  - `test_pagina_nessuna_scelta`: mostra la `nota`
  - `test_pagina_statistiche_vuote`: nessuna previsione → contiene "Ancora nessun risultato"
  - `test_grafico_creato`: il PNG esiste e non è vuoto

- [ ] **Passo 2: eseguire** `pytest tests/test_pagina.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare**

- [ ] **Passo 4: eseguire i test.** Atteso: PASS

- [ ] **Passo 5: aprire** `sito/index.html` generato dai dati di prova nel browser e controllare a larghezza telefono (360 px) che non ci sia scorrimento orizzontale

- [ ] **Passo 6: commit** `feat: pagina web e grafici`

---

### Compito 10: Comandi mattina, sera e tabella

**File:**
- Crea: `agente/main.py`, `agente/__main__.py`
- Test: `tests/test_main.py`

**Interfacce:**
- Consuma: tutte le funzioni precedenti
- Produce:
  - `deve_partire(comando: str, adesso: datetime, oggi_json: dict | None) -> bool`: `mattina` se ora di Roma ≥ 07:00 e `fatto_mattina` ≠ oggi; `sera` se ora di Roma ≥ 22:00 e `fatto_sera` ≠ oggi; `tabella` sempre
  - `esegui_mattina(cfg, cartella_dati: Path, cartella_sito: Path, oggi: date, servizi: Servizi) -> None`
  - `esegui_sera(cfg, cartella_dati, cartella_sito, oggi, servizi) -> None`
  - `esegui_tabella(cfg, cartella_dati, oggi, servizi) -> None`: per mercato scarica `anni_storico` anni, `prepara_storico`, `costruisci_tabella(fino_a=None)`, salva `tabella_{codice}.csv` e `prova_{codice}.json` (risultato di `prova_fuori_campione`)
  - `Servizi` dataclass con le dipendenze esterne iniettabili: `scarica_prezzi`, `scarica_prezzi_giorno`, `scarica_notizie`, `cervello`, `cambi` (`Callable[[date, date], dict[date, float]]`, da Yahoo `EURUSD=X`), `indici` (`Callable[[str, date], pd.Series]`)
  - `main(argv: list[str]) -> int`: `python -m agente mattina|sera|tabella [--forza]`; `--forza` ignora `deve_partire`

Flusso **mattina**: se manca una tabella, esegue prima `esegui_tabella`. Per ogni mercato: se `borsa_aperta` è falso → scheda con nota "Borsa chiusa oggi."; altrimenti `scarica_prezzi(anni=1)`, `scegli`, grafico, `scrivi_testi` (con le parole già usate prese da `oggi.json` precedenti, salvate in `dati/parole.json`). Poi `aggiungi_previsioni`, `salva_oggi` con `fatto_mattina = oggi`, statistiche, `genera_sito`. Se `scarica_prezzi` solleva `DatiNonDisponibili` per un mercato → scheda con nota "Dati non disponibili oggi." e l'altro mercato prosegue.

Flusso **sera**: `registra_esiti`, statistiche, `genera_sito` con le schede di `oggi.json`, `fatto_sera = oggi`.

- [ ] **Passo 1: scrivere i test** con `Servizi` finti e `tmp_path`
  - `test_deve_partire_ora_legale`: 05:30 UTC del 15/07/2026 → `mattina` sì; 06:30 UTC dello stesso giorno con `fatto_mattina` = oggi → no
  - `test_deve_partire_ora_solare`: 05:30 UTC del 15/01/2026 → no (sono le 06:30 a Roma); 06:30 UTC → sì
  - `test_mattina_completa`: crea `previsioni.csv`, `oggi.json` e `sito/index.html`
  - `test_mercato_chiuso_saltato`: 26/11/2026 → nessuna previsione USA, scheda USA con "Borsa chiusa oggi.", previsione ITA presente
  - `test_dati_non_disponibili_un_mercato`: `scarica_prezzi` solleva solo per USA → ITA prosegue
  - `test_sera_compila_esiti`

- [ ] **Passo 2: eseguire** `pytest tests/test_main.py -v`. Atteso: FAIL

- [ ] **Passo 3: implementare** (log con `logging` a livello INFO)

- [ ] **Passo 4: eseguire tutti i test** `pytest -v`. Atteso: tutti PASS

- [ ] **Passo 5: commit** `feat: comandi mattina, sera e tabella`

---

### Compito 11: Prova con dati veri sul PC

**File:**
- Modifica: `config.yaml` (solo per correggere simboli e modello)

- [ ] **Passo 1:** `python -m agente tabella`. Atteso: `dati/tabella_ITA.csv` e `dati/tabella_USA.csv` con almeno 50 situazioni ciascuna, e i file `prova_*.json`. Dal log, togliere da `config.yaml` i simboli esclusi per mancanza di dati (o correggerli)
- [ ] **Passo 2:** Giovanni crea la chiave su Google AI Studio (guida passo passo) e la imposta in `GEMINI_API_KEY`. Verificare che il modello `gemini_modello` esista nel piano gratuito; se no, impostare il modello Flash gratuito attuale
- [ ] **Passo 3:** `python -m agente mattina --forza`. Atteso: `sito/index.html` con due schede (o note motivate), testi in italiano, grafici
- [ ] **Passo 4:** aprire la pagina nel browser e controllarla insieme a Giovanni
- [ ] **Passo 5:** riportare a Giovanni i numeri della prova fuori campione (`prova_*.json`), anche se deludenti
- [ ] **Passo 6: commit** `chore: liste titoli verificate con dati reali` (senza `dati/` di prova, che va ripulita)

---

### Compito 12: Automazione su GitHub

**File:**
- Crea: `.github/workflows/agente.yml`, `README.md` (breve, in italiano)

**Workflow:**
- `on.schedule`: `30 5 * * 1-5` e `30 6 * * 1-5` (mattina), `30 20 * * 1-5` e `30 21 * * 1-5` (sera), `0 8 * * 6` (tabella del sabato); `workflow_dispatch` con input `comando` (mattina/sera/tabella) e `forza` (booleano)
- `permissions`: `contents: write`, `pages: write`, `id-token: write`; `concurrency: agente` per non avere due esecuzioni insieme
- passi: checkout → `actions/setup-python` 3.12 con cache pip → `pip install -r requirements.txt` → `python -m agente <comando>` con `GEMINI_API_KEY` dai segreti (il comando si ricava dall'orario cron o dall'input) → se `dati/` è cambiata, commit e push di `dati/` come "agente-bot" → `actions/upload-pages-artifact` (cartella `sito/`) → `actions/deploy-pages`
- se `deve_partire` restituisce falso, il programma esce con codice 0 e scrive `nessun_lavoro` in `$GITHUB_OUTPUT`; caricamento e pubblicazione della pagina vengono saltati

- [ ] **Passo 1:** scrivere il workflow e il README (cos'è, come leggere la pagina, come lanciare a mano)
- [ ] **Passo 2:** creare l'archivio pubblico su GitHub dall'account di Giovanni (`gh repo create` se `gh` è installato e collegato, altrimenti guida), push di `main`
- [ ] **Passo 3:** aggiungere il segreto `GEMINI_API_KEY` e attivare Pages con origine "GitHub Actions"
- [ ] **Passo 4:** lanciare a mano `tabella`, poi `mattina` con `forza`. Atteso: entrambe verdi e pagina raggiungibile all'indirizzo `https://<utente>.github.io/<archivio>/`
- [ ] **Passo 5:** lanciare a mano `sera` con `forza`. Atteso: verde, commit di `dati/` fatto dal bot
- [ ] **Passo 6: commit** `ci: esecuzione automatica su GitHub Actions`
- [ ] **Passo 7:** controllare nei 2 giorni successivi che le esecuzioni programmate partano da sole (criterio di riuscita della spec: 2 settimane senza interventi)
