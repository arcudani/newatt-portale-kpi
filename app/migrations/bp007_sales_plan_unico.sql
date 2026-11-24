-- ============================================================
-- Migrazione bp007 — Sales plan come un solo KPI con il dettaglio per commodity.
--
-- Regola di Migliora (15/10/2026): nel Cruscotto nessuna tessera è divisa per
-- commodity; la divisione energia elettrica / gas sta DENTRO la tessera, in
-- piccolo sotto il numero (come Churn, bp006, e CLT, bp005). Sostituisce
-- L3_SALES_EE e L3_SALES_GAS di bp004 (solo catalogo: nessun dato salvato).
--
-- Stessa struttura di bp004 (letta da dati_prova.catalogo_seed):
--   1) INSERT ... ON CONFLICT DO NOTHING
--   2) UPDATE ... FROM (values (codice, livello, vista, ambito, ordine, drill))
--   3) DELETE ... WHERE codice IN (...)
-- ============================================================

insert into public.bp_kpi_catalogo
    (codice, nome, livello, vista, ordine, definizione, unita, direzione, owner,
     fonte, stato, fonte_prevista, rif_ded, benchmark, soglia_gialla, soglia_rossa,
     visibilita, drill)
values
('L3_SALES', 'Sales plan', 3, 'V1', 4,
 'Contratti attivati nel periodo / attivazioni previste dal BP nello stesso periodo, su tutti i clienti; il dettaglio lo divide fra energia elettrica (POD) e gas naturale (PDR). Fino al consuntivo il dettaglio mostra l''obiettivo di attivazioni del BP.',
 '%', 1, 'Dir. Commerciale', 'BP + CONS', 'segnaposto', 'CRM agenti / switch-in (fase 3)', 'SAL-01', '', 5, 10, 'tutti', 'V3')
on conflict (codice) do nothing;

update public.bp_kpi_catalogo as c
set livello = v.livello, vista = v.vista, ambito = v.ambito, ordine = v.ordine, drill = v.drill
from (values
    ('L3_SALES',         3::smallint,  'V1', 'Commerciale',            4, 'V3')
) as v(codice, livello, vista, ambito, ordine, drill)
where c.codice = v.codice;

delete from public.bp_kpi_catalogo where codice in ('L3_SALES_EE', 'L3_SALES_GAS');
