-- ============================================================
-- Migrazione bp006 — Churn come un solo KPI con il dettaglio per commodity.
--
-- Richiesta Migliora del 15/10/2026, come per il CLT (bp005): nel Cruscotto
-- il churn è UNA tessera (tutti i clienti, ultimi 12 mesi); la divisione
-- energia elettrica / gas sta nel dettaglio sotto il numero, con le icone
-- della commodity. Torna in V1 il churn totale L3_CHURN (bp004 l'aveva
-- spostato in V3) e si tolgono L3_CHURN_EE / L3_CHURN_GAS (catalogo e basta:
-- il loro valore era un calcolo sul BP, nessun dato salvato).
--
-- Stessa struttura di bp004 (letta da dati_prova.catalogo_seed), qui senza
-- INSERT e con l'aggiornamento della definizione:
--   1) UPDATE ... SET definizione = '...' WHERE codice = '...'
--   2) UPDATE ... FROM (values (codice, livello, vista, ambito, ordine, drill))
--   3) DELETE ... WHERE codice IN (...)
-- ============================================================

update public.bp_kpi_catalogo set definizione = 'Clienti cessati negli ultimi 12 mesi / base attiva media degli ultimi 12 mesi, su tutti i clienti; il dettaglio lo divide fra energia elettrica (POD) e gas naturale (PDR). In v1 è l''ipotesi del BP: il churn reale arriva dai dati operativi.' where codice = 'L3_CHURN';

update public.bp_kpi_catalogo as c
set livello = v.livello, vista = v.vista, ambito = v.ambito, ordine = v.ordine, drill = v.drill
from (values
    ('L3_CHURN',         3::smallint,  'V1', 'Commerciale',            6, 'V3')
) as v(codice, livello, vista, ambito, ordine, drill)
where c.codice = v.codice;

delete from public.bp_kpi_catalogo where codice in ('L3_CHURN_EE', 'L3_CHURN_GAS');
