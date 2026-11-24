"""V8 — Modulo VAS (L300, editabile): segnaposto della fase 2."""
from __future__ import annotations

import branding
import ui

ui.testata("V8", "Quale parametro del VAS muovo nella prossima versione?", None)
branding.pannello_in_arrivo(
    "✏️", "Modulo VAS · fase 2 (scrittura)",
    "Parametri del VAS modificabili su una versione in bozza, con ricalcolo e anteprima "
    "dell'impatto sui KPI del Cruscotto. Da impostare già sulla logica di cross-sell proposta "
    "nella Nota ricostruzione VAS: il VAS eredita i punti dal portafoglio agenti.",
    [("Penetrazione per anno", "Assicurazione 20%, Manutenzione 15%, Telecomunicazioni 10% sul "
                               "portafoglio POD e PDR, modificabile anno per anno."),
     ("Margini", "120 / 120 / 180 € per punto all'anno (10-10-15 €/mese del BP 26-27)."),
     ("Costi", "Costi diretti e di erogazione (oggi 0 nel BP) ed eventuale provvigione "
               "all'agente sul VAS."),
     ("Durata", "Retention dedicata se i contratti VAS hanno durata propria (12-24 mesi)."),
     ("Totali", "Inclusione dei POD/PDR con VAS come «di cui» del portafoglio, senza doppio "
                "conteggio negli FTE."),
     ("Log", "Chi, quando, parametro, valore prima/dopo; ripristino.")])
