-- ============================================================
-- Migrazione bp003 — ambiti e benchmark numerici del catalogo KPI.
--
-- * ambito: raggruppa le tessere di una vista in colonne/fasce (stile
--   dashboard DeD: Vendite / Operation / Cliente). L'ordine degli ambiti
--   in una vista segue il minimo «ordine» dei suoi KPI.
-- * bench_min / bench_max: intervallo sano del KPI (blueprint §10 punto 9,
--   «benchmark DeD accanto al target BP»). Fuori intervallo la tessera
--   mostra un avviso; dentro, un insight. Sulle percentuali: frazioni.
-- Solo additiva; idempotente (ADD COLUMN IF NOT EXISTS + UPDATE).
-- ============================================================

alter table public.bp_kpi_catalogo
    add column if not exists ambito    text not null default '',
    add column if not exists bench_min numeric,
    add column if not exists bench_max numeric;

comment on column public.bp_kpi_catalogo.ambito is
    'Gruppo della tessera nella vista (colonna in L3, fascia in L30).';
comment on column public.bp_kpi_catalogo.bench_min is
    'Limite inferiore dell''intervallo sano (benchmark/target); NULL = nessuno.';
comment on column public.bp_kpi_catalogo.bench_max is
    'Limite superiore dell''intervallo sano (benchmark/target); NULL = nessuno.';

update public.bp_kpi_catalogo as c
set ambito = v.ambito, ordine = v.ordine, bench_min = v.bench_min, bench_max = v.bench_max
from (values
    ('L3_RICAVI',        'Conto economico',        1, null::numeric, null::numeric),
    ('L3_EBITDA',        'Conto economico',        2, null, null),
    ('L3_UTILE',         'Conto economico',        3, null, null),
    ('L3_PDP',           'Portafoglio',            4, null, null),
    ('L3_MIX',           'Portafoglio',            5, 0.75, 0.85),
    ('L3_CHURN',         'Portafoglio',            6, null, null),
    ('L3_CTS',           'Efficienza',  7, 10, 15),
    ('L3_MARGINE_UNIT',  'Efficienza',  8, null, null),
    ('L3_FORECAST',      'Efficienza',  9, null, null),
    ('V2_FATTURATO',     'Ricavi e margini',       1, null, null),
    ('V2_PM_PCT',        'Ricavi e margini',       2, null, null),
    ('V2_EBITDA',        'Ricavi e margini',       3, null, null),
    ('V2_COSTO_APPR',    'Costi',                  4, null, null),
    ('V2_PROVV_PM',      'Costi',                  5, null, null),
    ('V2_COSTI_GEN',     'Costi',                  6, null, null),
    ('V3_PRODUZIONE',    'Acquisizione',           1, null, null),
    ('V3_AVANZAMENTO',   'Acquisizione',           2, null, null),
    ('V3_CAC',           'Acquisizione',           3, null, null),
    ('V3_PDP',           'Portafoglio',            4, null, null),
    ('V3_SWITCH_OUT',    'Portafoglio',            5, null, null),
    ('V3_NET_ADDS',      'Portafoglio',            6, null, null),
    ('V4_VAS_ATTIVI',    'Portafoglio VAS',        1, null, null),
    ('V4_PENETRAZIONE',  'Portafoglio VAS',        2, 0.45, null),
    ('V4_EXTRA_PROFITTO','Economia VAS',           3, null, null),
    ('V4_MARGINE_MEDIO', 'Economia VAS',           4, null, null),
    ('V4_COSTI_VAS',     'Economia VAS',           5, null, null),
    ('V5_CTS',           'Costo del servizio',     1, 10, 15),
    ('V5_NEWATT_PUNTO',  'Costo del servizio',     2, null, null),
    ('V5_PERDITE',       'Costo del servizio',     3, null, null),
    ('V5_FTE_CC',        'Struttura',              4, null, null),
    ('V5_FTE_OP',        'Struttura',              5, null, null),
    ('V5_COSTO_FTE',     'Struttura',              6, null, null),
    ('V5_PUNT_SWITCH',   'Qualità del servizio',   7, null, null),
    ('V5_FATT_ONTIME',   'Qualità del servizio',   8, null, null),
    ('V5_RECLAMI',       'Qualità del servizio',   9, null, null),
    ('V5_TTA',           'Qualità del servizio',  10, null, null),
    ('V7_PERF_SPORTELLO','Canale agenti',          1, null, null),
    ('V7_COORTI',        'Canale agenti',          2, null, null),
    ('V9_SDD',           'Servizio clienti e incassi', 1, null, null),
    ('V9_BACKLOG',       'Servizio clienti e incassi', 2, null, null),
    ('V9_FCR',           'Servizio clienti e incassi', 3, null, null),
    ('V9_ACCURATEZZA',   'Servizio clienti e incassi', 4, null, null)
) as v(codice, ambito, ordine, bench_min, bench_max)
where c.codice = v.codice;
