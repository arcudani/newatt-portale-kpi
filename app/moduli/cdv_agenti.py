"""V7 — Modulo CdV Agenti (L300, editabile): segnaposto della fase 2."""
from __future__ import annotations

import streamlit as st

import branding
import ui

ctx = ui.carica_contesto()
ui.testata("V7", "Quale parametro del canale agenti muovo nella prossima versione?", ctx)
branding.pannello_in_arrivo(
    "✏️", "Modulo CdV Agenti · fase 2 (scrittura)",
    "Qui si modificheranno i parametri del canale agenti su una versione in bozza, con "
    "ricalcolo del BP e anteprima dell'impatto sui 9 KPI del Cruscotto prima di confermare. "
    "Prerequisito: il motore Python che riproduce l'Excel entro ±0,1% (fase 0).",
    [("Griglia parametri", "Sportelli e aperture, produzione per sportello, split Retail/Business "
                           "e Power/Gas, sopravvivenza e churn mensile, prezzi e profili di consumo."),
     ("Provvigioni", "Gettoni G18/G20/G22, una tantum e base ricorrente esplicitata (delta netto "
                     "vs stock attivo dal 13° mese), ENASARCO."),
     ("Evidenza modifiche", "Celle cambiate rispetto alla versione approvata in giallo, con "
                            "validazione di intervallo e unità."),
     ("Anteprima impatto", "Δ sui KPI L3 dell'anno e del piano, grafico dei driver prima/dopo."),
     ("Log", "Chi, quando, parametro, valore prima/dopo; ripristino."),
     ("Ruoli", "Admin ed editor scrivono sulle bozze; il viewer legge i parametri approvati.")])
st.markdown("<div class='mg-side-label' style='margin-top:18px'>Segnaposto DeD</div>",
            unsafe_allow_html=True)
ui.tessere_vista(ctx, "V7", per_riga=2)
