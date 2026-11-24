"""V10 — Consuntivo (L300, admin/editor): segnaposto della fase 3."""
from __future__ import annotations

import branding
import ui

ui.testata("V10", "Il mese è chiuso, caricato e quadrato?", None)
branding.pannello_in_arrivo(
    "📥", "Consuntivo · fase 3",
    "Import del conto economico mensile di Migliora e mapping dei conti contabili sulle voci "
    "del BP. È la sorgente del badge «stato dati» e dell'attivazione di YTD, forecast "
    "full-year e semafori BP vs consuntivo in tutte le viste.",
    [("Import", "CSV/XLSX del CE mensile dalla contabilità; sostituzione controllata di un mese "
                "già caricato."),
     ("Mapping conti", "Conto contabile → voce BP con conferma dell'operatore e memoria (i conti "
                       "del foglio IPO - Costi sono il punto di partenza)."),
     ("Quadratura", "Controllo sul totale importato prima di rendere il mese leggibile."),
     ("Calendario", "Stato per mese: caricato / mancante / rettificato; YTD solo sui mesi chiusi."),
     ("Note", "Commenti agli scostamenti firmati dagli owner, con visibilità Bros o NeWatt."),
     ("Accesso", "Solo admin ed editor Bros; il viewer NeWatt non vede questa vista.")])
