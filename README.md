# Maestro del mattino

Agente gratuito che ogni mattina (ore 07:30) propone, per la Borsa Italiana e per gli Stati Uniti,
un'operazione completa: ingresso, stop loss, pareggio, prima uscita e regola di uscita finale.
Ogni sera (ore 22:30) segue le operazioni aperte e manda un'email quando c'è qualcosa da fare.

**Strumento personale a scopo didattico. Non è una consulenza finanziaria.**

## Le regole di un'operazione
- **1R** = 2 volte il movimento medio giornaliero (ATR 14) del titolo
- **Ingresso**: al mercato, all'apertura
- **Stop loss**: chiusura di ieri − 1R
- **Pareggio**: a +1R lo stop sale al prezzo d'ingresso
- **Prima uscita**: a +2R si vende metà
- **Il resto**: si vende all'apertura dopo una chiusura sotto la media mobile a 20 giorni (arriva l'email)
- Una sola posizione aperta per mercato. "Solo studio" = resa storica sotto +0,10R: da studiare, non da investire

## Come inserire l'operazione su IBKR (app o TWS)
1. **Ordine d'ingresso**: acquisto *al mercato* (o "MOO", market on open), con la quantità indicata nell'email
2. **Ordine bracket**: allega all'ingresso uno **stop loss** al prezzo indicato
3. **Take profit su metà**: allega un ordine limite di vendita per **metà** della quantità al prezzo "prima uscita (+2R)"
4. **Stop regolabile** (Adjusted stop): sullo stop imposta "quando il prezzo raggiunge il livello di pareggio,
   sposta lo stop al prezzo d'ingresso"
5. Quando arriva l'email "📉 ha chiuso sotto la media a 20", la mattina dopo vendi il resto all'apertura

IBKR gestisce i punti 2–4 da solo sui suoi server, anche a telefono spento.

## Come leggere la pagina
- **Oggi**: la nuova operazione con il piano, oppure lo stato della posizione già aperta
- **Posizioni aperte** e **Storico**: risultati in R
- **Statistiche**: resa media in R, conto simulato da 1.000 €, conto IBKR da 100 € con commissioni e tasse,
  prova sull'ultimo anno

## Lanciarlo a mano
Su GitHub: scheda **Actions** → "Maestro del mattino" → **Run workflow**, scegli `mattina`, `sera` o `tabella`.

Sul PC:
```
.venv\Scripts\python -m agente mattina --forza
```
(servono le variabili `GEMINI_API_KEY` e, per le email, `RESEND_API_KEY`)

## Impostazioni
Tutto in `config.yaml`: elenchi dei titoli, soglia in R, distanza dello stop, modalità studio, costi IBKR, modello Gemini, destinatario delle email.

## Documenti
- Progetto: `docs/superpowers/specs/2026-10-17-agente-trading-design.md`
- Piano di costruzione: `docs/superpowers/plans/2026-10-17-agente-trading.md`
- Versione 2 (operazioni): `docs/superpowers/specs/2026-10-17-gestione-posizioni-design.md`
