# Agente di trading "Maestro del mattino": progetto

Data: 17 ottobre 2026
Stato: in attesa di approvazione di Giovanni

## 1. Obiettivo

Uno strumento **gratuito** che ogni mattina, nei giorni di borsa aperta, pubblica su una pagina web
personale **un titolo italiano e un titolo americano** con la probabilità storica più alta di salire
durante la giornata. Ogni scelta è accompagnata da una spiegazione in italiano semplice.

Lo scopo principale è **imparare** come funzionano i mercati e l'analisi tecnica, e **misurare con
numeri veri** se i segnali funzionano, prima di rischiare soldi.

### Cosa ha deciso Giovanni
- Obiettivo: imparare, partendo con previsioni simulate (senza soldi veri)
- Livello: base (conosce azioni ed ETF, non sa leggere grafici e notizie finanziarie)
- Mercati: Borsa Italiana + Stati Uniti, un titolo per mercato al giorno
- Risultato: pagina web con il consiglio del giorno, lo storico e le statistiche
- Dove gira: GitHub (cloud gratuito), anche con il PC spento
- Fonti: solo gratuite
- Metodo: regole chiare di analisi tecnica, probabilità misurate sul passato, spiegazione scritta dall'AI
- Conto reale: ha un conto IBKR con 100 € e potrebbe portarlo a 500–1.000 €. Il progetto simula anche questo conto

### Cosa ho dedotto io (da confermare)
- Nessun collegamento automatico al conto IBKR: gli ordini, se e quando li vorrà fare, li mette Giovanni a mano
- I primi 2 mesi sono solo simulati. Poi Giovanni decide guardando le statistiche
- La pagina è pubblica (serve per l'hosting gratuito) ma non contiene dati personali e l'indirizzo
  non è pubblicizzato
- La pagina riporta in modo chiaro: "Strumento personale a scopo didattico, non è una consulenza finanziaria"

### Cosa NON fa (per ora)
- Non compra né vende da solo
- Non usa X (Twitter): l'accesso automatico costa oltre 100 € al mese
- Non manda email o notifiche col consiglio del giorno (solo email di GitHub in caso di errore)
- Non fa previsioni su più giorni: solo sulla singola giornata

## 2. Come sceglie il titolo

### 2.1 Il gruppo di partenza
- **Italia**: i circa 40 titoli del FTSE MIB (simboli Yahoo con `.MI`, es. `ENI.MI`)
- **USA**: circa 100 titoli tra i più scambiati dell'S&P 500
- Le liste stanno in un file di configurazione facile da modificare

### 2.2 Il momento della previsione
- I segnali usano **solo i dati fino alla chiusura del giorno prima**
- La previsione riguarda **il giorno stesso, dall'apertura alla chiusura**: "se compro all'apertura
  e vendo alla chiusura, ci guadagno?". È la cosa che Giovanni può fare davvero, perché legge la
  pagina prima che la borsa apra
- "Salito" significa: prezzo di chiusura superiore al prezzo di apertura

### 2.3 I segnali tecnici
Ogni segnale viene ridotto a pochi stati semplici, così le combinazioni restano poche e le statistiche affidabili:

| Segnale | Stati |
|---|---|
| Trend | prezzo sopra entrambe le medie mobili (20 e 50 giorni) / sotto entrambe / misto |
| RSI a 14 giorni | ipervenduto (sotto 30) / normale / ipercomprato (sopra 70) |
| MACD | incrocio rialzista ieri / incrocio ribassista ieri / nessun incrocio |
| Volumi | ieri oltre 2 volte la media dei 20 giorni / normali |
| Rottura | chiusura sopra il massimo dei 20 giorni precedenti / no |
| Giornata di ieri | forte rialzo (oltre +2%) / forte ribasso (oltre −2%) / normale |

La combinazione degli stati di un titolo è la sua **"situazione"**.

### 2.4 Le probabilità misurate sul passato
- Si scaricano **5 anni di prezzi giornalieri** per tutti i titoli di un mercato
- Per ogni giorno storico si calcola la situazione di ogni titolo e si annota se il giorno dopo è salito
  dall'apertura alla chiusura (come al punto 2.2)
- I dati di tutti i titoli dello stesso mercato vengono **messi insieme**: un singolo titolo non ha
  abbastanza casi per ogni situazione
- Per ogni situazione si calcolano: numero di casi, percentuale di volte in salita, guadagno medio
- **Correzione per i pochi casi**: la percentuale viene "tirata" verso la media generale del mercato
  quando i casi sono pochi (media pesata con 30 casi "virtuali" pari alla media). Così una situazione
  vista 12 volte con 10 rialzi non risulta "83%"
- Situazioni con **meno di 30 casi** vengono scartate

### 2.5 La scelta del giorno
1. Si calcola la situazione di oggi per ogni titolo e la probabilità corrispondente
2. Si ordinano i titoli dalla probabilità più alta
3. **Filtro notizie**: Gemini legge i titoli delle notizie delle ultime 24 ore sul candidato. Se sono
   chiaramente negative (es. indagine, profitti molto sotto le attese), il titolo viene scartato e si
   passa al successivo
4. Se il migliore rimasto è **sotto il 55%** (soglia modificabile), la pagina scrive "oggi niente di
   interessante" e spiega perché

**Perché le notizie sono un filtro e non entrano nella probabilità:** non esistono archivi gratuiti di
5 anni di notizie per titolo, quindi il loro effetto non si può misurare sul passato. L'agente però
registra ogni giorno il giudizio sulle notizie, così dopo qualche mese si potrà vedere se il filtro aiuta.

### 2.6 Controlli contro le illusioni
- **Niente "sbirciata nel futuro"**: nel calcolo storico, la probabilità usata per un giorno passato
  si basa solo sui giorni precedenti. Un test automatico lo verifica
- **Prova su dati mai visti**: le probabilità vengono calcolate sui primi 4 anni e verificate
  sull'ultimo anno. Il risultato di questa prova viene mostrato sulla pagina, nella sezione statistiche
- Aspettativa onesta, scritta sulla pagina: i segnali migliori arrivano di solito al 53–60%

## 3. La pagina web

Ottimizzata per il telefono, in italiano, aggiornata due volte al giorno.

### 3.1 "Oggi"
Due schede (Italia e USA), ciascuna con:
- nome del titolo, prezzo di chiusura di ieri, **probabilità storica** e numero di casi
  (es. "57% su 142 casi simili") e guadagno medio storico
- grafico degli ultimi 3 mesi con le medie mobili e il punto del segnale
- **"Perché questo titolo"**: 4–5 righe che uniscono segnali e notizie
- **"Cosa potrebbe andare storto"**: il rischio principale del giorno
- **"Parola del giorno"**: un termine tecnico spiegato con un esempio
- giudizio sulle notizie (positivo / neutro / negativo) con i link alle fonti

### 3.2 "Com'è andata"
Tabella di tutte le previsioni: data, mercato, titolo, probabilità annunciata, apertura, chiusura,
risultato (✅ / ❌ e percentuale).

### 3.3 "Statistiche"
- percentuale di previsioni azzeccate, in totale e per mercato
- confronto tra probabilità annunciata e risultati reali (es. "le previsioni al 57% sono state giuste il 54% delle volte")
- **Conto simulato da 1.000 €**: 500 € per mercato. Ogni giorno si investe tutta la quota del
  mercato nel titolo scelto, all'apertura, e si vende alla chiusura. Commissioni incluse
- **Conto IBKR reale simulato**: 100 € (importo modificabile), con commissioni IBKR, costo del cambio
  euro/dollaro e tasse del 26% sui guadagni
- confronto con chi ha comprato e tenuto l'indice (FTSE MIB e S&P 500) nello stesso periodo
- quali segnali hanno funzionato meglio e peggio
- risultato della prova sui dati mai visti (punto 2.6)

### 3.4 Costi usati nelle simulazioni (valori iniziali, da verificare sul conto di Giovanni)
| Voce | Valore |
|---|---|
| Titoli italiani, IBKR Tiered | 0,05% del valore, minimo 1,25 € per ordine |
| Titoli USA, IBKR Tiered | 0,0035 $ per azione, minimo 0,35 $, massimo 1% del valore |
| Cambio euro/dollaro | da verificare (conversione automatica o manuale) |
| Tobin tax Italia | 0,1% sugli acquisti, esclusa se compro e vendo nella stessa giornata |
| Tasse sui guadagni | 26%, compensando le perdite |

Tutti i valori stanno in un file di configurazione.

## 4. Come è costruito

### 4.1 Tecnologie (tutte gratuite)
- **Python 3** con `yfinance` (prezzi), `pandas` (calcoli), `feedparser` (notizie RSS),
  `exchange_calendars` (giorni di borsa aperta), `google-genai` (Gemini), `jinja2` (pagina), `pytest` (test)
- **Gemini**: modello Flash del piano gratuito (il nome esatto si verifica durante la costruzione).
  Circa 10 richieste al giorno, molto sotto il limite gratuito
- **GitHub**: archivio pubblico (le "Actions" sono gratuite e illimitate per gli archivi pubblici),
  GitHub Actions per l'esecuzione automatica, GitHub Pages per la pagina
- Grafici: immagini generate in Python con `matplotlib`, così la pagina resta semplice

### 4.2 I pezzi
Ogni file fa una sola cosa:

| File | Cosa fa |
|---|---|
| `agente/config.py` | legge le liste dei titoli, le soglie e i costi |
| `agente/dati.py` | scarica prezzi (Yahoo Finance) e notizie (Google News RSS, Yahoo Finance RSS, Il Sole 24 Ore, Milano Finanza) |
| `agente/segnali.py` | calcola gli indicatori e la "situazione" di ogni titolo |
| `agente/probabilita.py` | costruisce la tabella storica delle probabilità e la consulta |
| `agente/scelta.py` | sceglie il titolo del giorno per ogni mercato, applica il filtro notizie e la soglia |
| `agente/spiegazione.py` | chiede a Gemini il giudizio sulle notizie e i testi; riceve i numeri già calcolati e non può cambiarli |
| `agente/verifica.py` | la sera registra apertura e chiusura e aggiorna lo storico |
| `agente/statistiche.py` | calcola percentuali, conti simulati con i costi e confronto con gli indici |
| `agente/pagina.py` | genera la pagina HTML e i grafici |
| `agente/main.py` | comandi `mattina` e `sera` |
| `dati/previsioni.csv` | storico di tutte le previsioni e dei risultati |
| `tests/` | test automatici |

Fonti di notizie nel filtro: Google News RSS (anche in italiano), Yahoo Finance RSS, Il Sole 24 Ore,
Milano Finanza. Reddit resta fuori dalla prima versione: il suo accesso automatico richiede una
registrazione e non è necessario per il filtro.

### 4.3 Orari
- **Mattina, ore 07:30 italiane**: analisi e pubblicazione
- **Sera, ore 22:30 italiane**: verifica dei risultati, aggiornamento di storico e statistiche
- GitHub usa l'ora UTC e non segue il passaggio tra ora legale e solare: il lavoro viene programmato
  in entrambi gli orari UTC possibili e il programma esegue solo quello giusto per l'ora italiana
- GitHub può partire con qualche minuto di ritardo: c'è comunque margine prima dell'apertura delle 9:00
- La tabella delle probabilità storiche si ricalcola una volta a settimana (sabato)
- Nei giorni di borsa chiusa il mercato corrispondente viene saltato e la pagina lo dice

### 4.4 Se qualcosa si rompe
| Problema | Cosa succede |
|---|---|
| Yahoo Finance non risponde | 3 tentativi, poi la scheda mostra "dati non disponibili oggi", nessun consiglio |
| Dati di un titolo incompleti o strani | il titolo viene escluso quel giorno |
| Gemini non risponde o supera i limiti | la scheda esce con numeri e segnali, senza testi e senza filtro notizie (e lo scrive) |
| Un feed di notizie non risponde | si usano gli altri |
| Qualsiasi errore non previsto | il lavoro di GitHub fallisce e GitHub manda un'email a Giovanni; la pagina del giorno prima resta online |

La chiave di Gemini sta nei "segreti" di GitHub, mai nel codice.

### 4.5 Test
- calcolo degli indicatori confrontato con valori noti
- costruzione della situazione su casi di esempio
- **nessuna sbirciata nel futuro**: aggiungere dati di giorni successivi non deve cambiare la probabilità di un giorno passato
- correzione per i pochi casi e scarto sotto i 30 casi
- conti simulati: commissioni minime, massime e tasse su casi calcolati a mano
- scelta del giorno: soglia, filtro notizie, nessun candidato
- gestione degli errori (Yahoo e Gemini simulati non funzionanti)
- i test non usano internet: i dati esterni vengono simulati

## 5. Cosa deve fare Giovanni
1. Creare un account GitHub gratuito (con guida passo passo)
2. Creare una chiave gratuita di Google Gemini (con guida passo passo)
3. Controllare sul conto IBKR il piano commissioni (Tiered o Fixed) e come avviene il cambio euro/dollaro

## 6. Quando il progetto è riuscito
- La pagina si aggiorna da sola ogni mattina e ogni sera per 2 settimane di fila senza interventi
- Ogni consiglio mostra probabilità, numero di casi, spiegazione e rischio
- Dopo 2–3 mesi le statistiche permettono di rispondere con i numeri: "conviene usare i 100 € su IBKR, sì o no?"
