-- ============================================================
-- Migrazione bp004 — nuovi KPI di primo livello del Cruscotto (V1).
--
-- Migliora/NeWatt ha fissato 12 KPI di primo livello in tre colonne:
--   Economico-finanziario · EBITDA, PFN, % Insoluto
--   Commerciale           · Sales plan e churn per commodity
--   Cliente e servizio    · NPS, Costo per cliente, Cost-to-Serve, CLT
-- Scelte del 15/10/2026: sostituiscono i 9 KPI precedenti; fino al
-- consuntivo la tessera mostra il valore del BP dove il BP lo contiene,
-- altrimenti «in attesa dati»; churn sugli ultimi 12 mesi; CLT = anzianità
-- media dei clienti attivi.
--
-- I KPI che escono dal Cruscotto non si perdono: Risultato netto, Forecast
-- EBITDA e Margine unitario passano in V2, Mix Retail e Churn totale in V3
-- (i codici L3_* restano gli stessi: sono identificativi, non livelli).
-- Ricavi e PdP attivi si cancellano perché duplicano V2_FATTURATO e V3_PDP.
--
-- Struttura (letta anche da dati_prova.catalogo_seed per i test):
--   1) INSERT ... ON CONFLICT DO NOTHING  (stesse colonne di bp002)
--   2) UPDATE ... FROM (values (codice, livello, vista, ambito, ordine, drill))
--   3) DELETE ... WHERE codice IN (...)
-- ============================================================

insert into public.bp_kpi_catalogo
    (codice, nome, livello, vista, ordine, definizione, unita, direzione, owner,
     fonte, stato, fonte_prevista, rif_ded, benchmark, soglia_gialla, soglia_rossa,
     visibilita, drill)
values
('L3_PFN', 'PFN', 3, 'V1', 2,
 'Posizione finanziaria netta a fine periodo: debiti finanziari meno cassa e crediti finanziari. Convenzione di segno da confermare (nell''esempio di Migliora il valore è negativo). Il BP importato contiene solo conto economico e driver: serve lo stato patrimoniale o il rendiconto finanziario.',
 '€', 0, 'CFO', 'CONS', 'segnaposto', 'Contabilità / tesoreria (fase 3)', '', '', null, null, 'tutti', 'V2'),
('L3_INSOLUTO', '% Insoluto', 3, 'V1', 3,
 'Crediti scaduti e non incassati / fatturato scaduto del periodo. Il BP prevede solo l''accantonamento per perdite su crediti (vista Operations).',
 '%', -1, 'Resp. Credito', 'OPER', 'segnaposto', 'Billing / gestione del credito (fase 4)', '', '', 0.5, 1, 'tutti', 'V5'),
('L3_SALES_EE', 'Sales plan energia elettrica', 3, 'V1', 4,
 'Contratti di energia elettrica (POD) attivati nel periodo / attivazioni previste dal BP nello stesso periodo. Fino al consuntivo la tessera mostra l''obiettivo del BP.',
 '%', 1, 'Dir. Commerciale', 'BP + CONS', 'segnaposto', 'CRM agenti / switch-in (fase 3)', 'SAL-01', '', 5, 10, 'tutti', 'V3'),
('L3_SALES_GAS', 'Sales plan gas naturale', 3, 'V1', 5,
 'Contratti gas (PDR) attivati nel periodo / attivazioni previste dal BP nello stesso periodo. Fino al consuntivo la tessera mostra l''obiettivo del BP.',
 '%', 1, 'Dir. Commerciale', 'BP + CONS', 'segnaposto', 'CRM agenti / switch-in (fase 3)', 'SAL-01', '', 5, 10, 'tutti', 'V3'),
('L3_CHURN_EE', 'Churn energia elettrica', 3, 'V1', 6,
 'POD cessati negli ultimi 12 mesi / POD attivi medi degli ultimi 12 mesi. In v1 è l''ipotesi del BP: il churn reale arriva dai dati operativi.',
 '%', -1, 'Retention', 'OPER', 'segnaposto', 'CRM / billing (fase 4)', 'CLI-03', '', 3, 6, 'tutti', 'V3'),
('L3_CHURN_GAS', 'Churn gas naturale', 3, 'V1', 7,
 'PDR cessati negli ultimi 12 mesi / PDR attivi medi degli ultimi 12 mesi. In v1 è l''ipotesi del BP: il churn reale arriva dai dati operativi.',
 '%', -1, 'Retention', 'OPER', 'segnaposto', 'CRM / billing (fase 4)', 'CLI-03', '', 3, 6, 'tutti', 'V3'),
('L3_NPS', 'NPS', 3, 'V1', 8,
 'Net Promoter Score: % di promotori (voto 9-10) meno % di detrattori (voto 0-6) sulle risposte all''indagine di soddisfazione del periodo. Scala da -100 a +100.',
 'pt', 1, 'Customer Care', 'OPER', 'segnaposto', 'Indagine di soddisfazione clienti (da attivare)', 'CLI-01', '', null, null, 'tutti', 'V5'),
('L3_COSTO_CLIENTE', 'Costo per cliente', 3, 'V1', 9,
 'Tutti i costi fra primo margine lordo ed EBITDA (costi operativi del Cost-to-Serve più provvigioni e spese point) / PdP attivi medi, annualizzato. Definizione proposta da Bros, da validare con Migliora.',
 '€/PdP', -1, 'CFO', 'BP + CONS', 'attivo', '', '', '', 5, 10, 'tutti', 'V5'),
('L3_CLT_EE', 'CLT energia elettrica', 3, 'V1', 11,
 'Customer lifetime: anzianità media dei clienti di energia elettrica attivi a fine periodo, in giorni dalla data di attivazione della fornitura.',
 'gg', 1, 'Dir. Commerciale', 'OPER', 'segnaposto', 'CRM / billing: date di attivazione (fase 4)', '', '', null, null, 'tutti', 'V3'),
('L3_CLT_GAS', 'CLT gas naturale', 3, 'V1', 12,
 'Customer lifetime: anzianità media dei clienti gas attivi a fine periodo, in giorni dalla data di attivazione della fornitura.',
 'gg', 1, 'Dir. Commerciale', 'OPER', 'segnaposto', 'CRM / billing: date di attivazione (fase 4)', '', '', null, null, 'tutti', 'V3')
on conflict (codice) do nothing;

update public.bp_kpi_catalogo as c
set livello = v.livello, vista = v.vista, ambito = v.ambito, ordine = v.ordine, drill = v.drill
from (values
    ('L3_EBITDA',        3::smallint,  'V1', 'Economico-finanziario',  1, 'V2'),
    ('L3_PFN',           3::smallint,  'V1', 'Economico-finanziario',  2, 'V2'),
    ('L3_INSOLUTO',      3::smallint,  'V1', 'Economico-finanziario',  3, 'V5'),
    ('L3_SALES_EE',      3::smallint,  'V1', 'Commerciale',            4, 'V3'),
    ('L3_SALES_GAS',     3::smallint,  'V1', 'Commerciale',            5, 'V3'),
    ('L3_CHURN_EE',      3::smallint,  'V1', 'Commerciale',            6, 'V3'),
    ('L3_CHURN_GAS',     3::smallint,  'V1', 'Commerciale',            7, 'V3'),
    ('L3_NPS',           3::smallint,  'V1', 'Cliente e servizio',     8, 'V5'),
    ('L3_COSTO_CLIENTE', 3::smallint,  'V1', 'Cliente e servizio',     9, 'V5'),
    ('L3_CTS',           3::smallint,  'V1', 'Cliente e servizio',    10, 'V5'),
    ('L3_CLT_EE',        3::smallint,  'V1', 'Cliente e servizio',    11, 'V3'),
    ('L3_CLT_GAS',       3::smallint,  'V1', 'Cliente e servizio',    12, 'V3'),
    ('L3_UTILE',         30::smallint, 'V2', 'Risultato',              7, ''),
    ('L3_FORECAST',      30::smallint, 'V2', 'Risultato',              8, ''),
    ('L3_MARGINE_UNIT',  30::smallint, 'V2', 'Risultato',              9, ''),
    ('L3_MIX',           30::smallint, 'V3', 'Portafoglio',            7, ''),
    ('L3_CHURN',         30::smallint, 'V3', 'Portafoglio',            8, '')
) as v(codice, livello, vista, ambito, ordine, drill)
where c.codice = v.codice;

delete from public.bp_kpi_catalogo where codice in ('L3_RICAVI', 'L3_PDP');
