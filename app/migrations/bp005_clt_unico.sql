-- ============================================================
-- Migrazione bp005 — CLT come un solo KPI con il dettaglio per commodity.
--
-- Richiesta Migliora del 15/10/2026: il Customer Lifetime nel Cruscotto è
-- UNA tessera; la divisione energia elettrica / gas sta nel suo dettaglio
-- (riga sotto il numero), non in due tessere. Sostituisce L3_CLT_EE e
-- L3_CLT_GAS introdotti da bp004 (mai alimentati: nessun dato da perdere).
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
('L3_CLT', 'CLT', 3, 'V1', 11,
 'Customer lifetime: anzianità media dei clienti attivi a fine periodo, in giorni dalla data di attivazione della fornitura. Il numero è su tutti i clienti; il dettaglio lo divide fra energia elettrica e gas naturale.',
 'gg', 1, 'Dir. Commerciale', 'OPER', 'segnaposto', 'CRM / billing: date di attivazione (fase 4)', '', '', null, null, 'tutti', 'V3')
on conflict (codice) do nothing;

update public.bp_kpi_catalogo as c
set livello = v.livello, vista = v.vista, ambito = v.ambito, ordine = v.ordine, drill = v.drill
from (values
    ('L3_CLT',           3::smallint,  'V1', 'Cliente e servizio',    11, 'V3')
) as v(codice, livello, vista, ambito, ordine, drill)
where c.codice = v.codice;

delete from public.bp_kpi_catalogo where codice in ('L3_CLT_EE', 'L3_CLT_GAS');
