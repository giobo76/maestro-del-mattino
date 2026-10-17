# Maestro del mattino 2: operazioni con stop, pareggio e uscita sulla media a 20

Data: 17 ottobre 2026
Stato: in attesa di approvazione di Giovanni
Sostituisce, nella scelta e nelle statistiche, il metodo "sale tra apertura e chiusura" della prima versione
(`2026-10-17-agente-trading-design.md`). Restano invariati: fonti gratuite, GitHub Actions e Pages, Gemini,
modalità studio, orari 07:30 e 22:30.

## 1. Obiettivo

Ogni mattina l'agente propone, per ciascun mercato senza una posizione già aperta, **un'operazione completa**:
prezzo d'ingresso, stop loss, livello di pareggio, livello di prima uscita e regola di uscita finale. Poi
**segue l'operazione ogni sera** e manda un'email quando c'è qualcosa da fare.

### Cosa ha deciso Giovanni
- Rischio definito in **R** (distanza tra ingresso e stop), con l'obiettivo di guadagnare molte volte il rischio
- Nessun limite di giorni: l'operazione resta aperta finché una regola non la chiude
- Gestione: **pareggio a +1R**, **metà chiusa a +2R**, **il resto chiude sotto la media mobile a 20 giorni**
- Solo la variante a +2R (niente confronto con +1R)
- Ordini gestiti da IBKR (bracket e stop regolabile). Nessun bot che compra o vende
- L'agente **segue le operazioni che propone** (non legge il conto IBKR)
- Avvisi per **email**, tramite il suo account Resend, all'indirizzo bonolinigiovanni@gmail.com

### Cosa ho deciso io (da confermare)
- Una posizione aperta alla volta per mercato
- Stop a 2 volte l'ATR a 14 giorni (movimento medio giornaliero) sotto la chiusura di ieri
- Con 100 € si investe tutto il capitale in un'operazione (non si dimensiona sul rischio: il capitale è troppo piccolo)

### Cosa NON fa
- Non legge le posizioni vere da IBKR (Flex Query: possibile più avanti)
- Non compra né vende
- Non usa prezzi minuto per minuto

## 2. I livelli di un'operazione

Calcolati la mattina con i dati fino alla chiusura di ieri (`C` = chiusura di ieri, `ATR` = ATR 14 di Wilder):

| Livello | Formula | Cosa fa Giovanni su IBKR |
|---|---|---|
| Riferimento | `C` | – |
| Stop iniziale | `C − 2 × ATR` | stop loss dell'ordine bracket |
| 1R | `2 × ATR` | – |
| Pareggio | `C + 1R` | stop regolabile: raggiunto questo prezzo, lo stop sale al prezzo d'ingresso |
| Prima uscita | `C + 2R` | take profit su **metà** posizione |
| Uscita finale | prima chiusura sotto la SMA20 dopo la prima uscita | vende il resto all'apertura del giorno dopo, quando arriva l'email |

- **Ingresso**: ordine al mercato all'apertura. Il prezzo d'ingresso reale è l'apertura del giorno (`A`)
- Il risultato in R di ogni parte è `(prezzo di uscita − A) / 1R`. Risultato dell'operazione = media delle due metà
- **Quantità** con il capitale IBKR configurato: Italia azioni intere (`floor(capitale / C)`; se è 0 la pagina lo dice),
  USA frazioni ammesse. La pagina mostra anche la perdita in euro se scatta lo stop

## 3. Regole giorno per giorno (usate sia nel passato sia nelle operazioni vere)

Per ogni giorno con apertura `O`, massimo `H`, minimo `L` e chiusura `Cg`, in quest'ordine:
1. **Giorno d'ingresso**: ingresso a `O`. Se `O` è già sotto lo stop, l'operazione si chiude subito a `O`
2. **Stop** (iniziale o di pareggio): se `L ≤ stop`, chiude tutto ciò che resta a `min(O, stop)`
3. **Prima uscita**: se `H ≥ C + 2R`, chiude metà a `max(O, C + 2R)`
4. **Pareggio**: se `H ≥ C + 1R`, lo stop sale al prezzo d'ingresso `A` dal giorno dopo
5. **Uscita sulla media**: solo dopo la prima uscita, se `Cg < SMA20`, il resto chiude all'apertura del giorno dopo

**Caso peggiore**: se nello stesso giorno sono toccati sia lo stop sia un obiettivo, conta lo stop (punto 2 prima del 3).
Il pareggio vale dal giorno dopo: nel giorno in cui scatta non protegge, così il calcolo non è mai ottimista.
Le operazioni ancora aperte alla fine dei dati non entrano nelle statistiche storiche.

## 4. Scelta del titolo

- Si riusa la "situazione" dei segnali della prima versione
- Per ogni giorno storico (5 anni) e ogni titolo si simula un'operazione con le regole del punto 3, a partire dall'apertura del giorno dopo
- Per ogni situazione: numero di operazioni chiuse, **resa media in R**, percentuale di stop pieni, di pareggi e di operazioni arrivate a +2R
- Correzione per i pochi casi come nella prima versione (30 casi virtuali con la resa media del mercato); scartate le situazioni con meno di 30 operazioni
- Ogni mattina, per ogni mercato **senza posizione aperta**, si sceglie il titolo con la resa media più alta; filtro notizie come prima
- **Soglia**: resa media ≥ **+0,10R** (modificabile). Sotto la soglia vale la modalità studio: l'operazione esce lo stesso, con l'etichetta
  "solo studio", ed è seguita come le altre ma esclusa dai conti simulati
- **Prova sull'ultimo anno**: tabella costruita sui primi 4 anni, operazioni simulate sull'ultimo, una posizione per mercato alla volta;
  mostra resa media reale contro quella annunciata

## 5. Controllo serale (22:30) ed email

Il file `dati/operazioni.csv` contiene tutte le operazioni: stato (`in attesa d'ingresso`, `aperta`, `metà chiusa`, `uscita domani`, `chiusa`),
livelli, stop attuale, prezzi e date di uscita, risultato in R, motivo di chiusura, etichetta studio.

Ogni sera, per ogni operazione non chiusa e per ogni mercato con la seduta finita, si applicano le regole del punto 3
ai giorni non ancora controllati. Ogni cambiamento produce un messaggio:
- 🔴 stop toccato: chiusa a X R
- 🟡 +1R raggiunto: controlla che lo stop sia salito al prezzo d'ingresso
- 🟢 +2R raggiunto: metà chiusa, il resto corre
- 📉 chiusura sotto la media a 20: domattina chiudi il resto all'apertura
- ✅ resto chiuso all'apertura: risultato finale X R

**Email**
- Sera: una sola email con tutti i messaggi, **solo se ce n'è almeno uno**
- Mattina: una email **solo se c'è una nuova operazione**, con i livelli pronti da inserire su IBKR
- Invio tramite l'API di Resend, chiave nel segreto GitHub `RESEND_API_KEY`, mittente `onboarding@resend.dev`,
  destinatario in `config.yaml`
- Se Resend non risponde, l'agente prosegue e pubblica comunque la pagina (il messaggio resta visibile lì)

## 6. La pagina

- **Oggi**: per ogni mercato la nuova operazione (livelli, quantità, perdita massima in euro, perché, rischio, parola del giorno,
  grafico con stop e livelli disegnati) oppure lo stato della posizione già aperta
- **Posizioni aperte**: ingresso, stop attuale, ultimo prezzo, risultato in R e in euro
- **Storico**: operazioni chiuse con risultato in R e motivo di chiusura
- **Statistiche**: resa media in R (consigli veri e "solo studio" separati), percentuali di stop, pareggi e +2R,
  conto simulato da 1.000 €, conto IBKR da 100 € con commissioni (ingresso + fino a 2 uscite) e tasse, prova sull'ultimo anno

**Nota onesta mostrata sulla pagina**: con 100 € le commissioni minime italiane (1,25 € a ordine, fino a 3 ordini)
possono valere quasi 1R. Il conto IBKR simulato lo mostra con i numeri.

## 7. Cosa si toglie dalla prima versione
- Previsione "sale tra apertura e chiusura", relativa tabella e statistiche
- `dati/previsioni.csv` (contiene solo prove; si archivia)

## 8. Cosa deve fare Giovanni
- Creare una chiave API su resend.com e inserirla come segreto `RESEND_API_KEY` su GitHub (con guida)

## 9. Quando è riuscito
- Ogni nuova operazione arriva per email con livelli coerenti con le formule del punto 2
- Le email serali arrivano solo quando c'è un cambiamento
- Lo storico e le statistiche in R si aggiornano da soli per 2 settimane senza interventi
