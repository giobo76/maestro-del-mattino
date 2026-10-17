# Maestro del mattino

Agente gratuito che ogni mattina (ore 07:30) sceglie un titolo italiano e uno americano con la
probabilità storica più alta di salire tra apertura e chiusura, lo spiega in italiano semplice e
la sera (ore 22:30) controlla com'è andata.

**Strumento personale a scopo didattico. Non è una consulenza finanziaria.**

## Come leggere la pagina
- **Oggi**: i titoli del giorno. L'etichetta "solo studio" vuol dire che la probabilità è sotto il 55%:
  serve per imparare, non per investire.
- **Com'è andata**: tutte le previsioni con il risultato reale.
- **Statistiche**: percentuale di previsioni giuste, conto simulato da 1.000 €, il conto IBKR da 100 €
  con commissioni e tasse, confronto con gli indici e prova sull'ultimo anno.

## Lanciarlo a mano
Su GitHub: scheda **Actions** → "Maestro del mattino" → **Run workflow**, scegli `mattina`, `sera` o `tabella`.

Sul PC:
```
.venv\Scripts\python -m agente mattina --forza
```
(la chiave di Gemini va nella variabile `GEMINI_API_KEY`)

## Impostazioni
Tutto in `config.yaml`: elenchi dei titoli, soglia, modalità studio, costi IBKR, modello Gemini.

## Documenti
- Progetto: `docs/superpowers/specs/2026-10-17-agente-trading-design.md`
- Piano di costruzione: `docs/superpowers/plans/2026-10-17-agente-trading.md`
