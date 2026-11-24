"""
V1 — Cruscotto KPI (L3 · 3 secondi). Blueprint §5 + handoff «Dashboard KPI
Migliora — Riquadri esecutivi» (15/10/2026, layout stile report Power BI).

Una domanda: «il piano sta tenendo?». Testata blu, barra filtri (Periodo dai
filtri globali, Commodity, Canale) con i contatori per stato, poi una fascia
per ambito con i 9 KPI di primo livello fissati da Migliora (catalogo,
migrazioni bp004-bp007): economico-finanziario, commerciale, cliente e
servizio. Riquadri tutti uguali; i grafici sono tolti per ora (handoff).
Finché il consuntivo non è caricato il riquadro mostra il valore del BP dove
il BP lo contiene e «In attesa dati» altrimenti. Ogni riquadro apre la vista
L30 del suo dominio con i filtri globali già impostati.
"""
from __future__ import annotations

import streamlit as st

import ui

ctx = ui.carica_contesto()
ui.testata("V1", "Il piano sta tenendo? Dove guardare per primo?", ctx)
ui.richiedi_versione(ctx)

righe = ui.barra_filtri_cruscotto(ctx)
ui.ambiti(ctx, "V1", drill=True, per_riga=4, righe=righe)
st.caption("Clicca un riquadro per aprire il dettaglio · passa il mouse per la definizione del "
           "KPI · il semaforo si accende solo contro un riferimento (versione di confronto o "
           "benchmark): senza, il riquadro dice «Valore BP» o «Ipotesi BP».")
