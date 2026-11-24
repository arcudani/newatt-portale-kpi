-- ============================================================
-- Migrazione kpi003 — obiettivi (soglie del semaforo) dei KPI.
-- Database: progetto Supabase `cte-newatt`.
--
-- Una riga per società × anno × riquadro KPI (codice della Tessera del
-- catalogo, es. EBITDA, CHURN, PDP_ATTIVI). Valori nella stessa unità
-- dei dati salvati: euro per gli importi, frazione per le percentuali
-- (3% = 0.03). La pagina «Obiettivi KPI» converte da/verso k€ e %.
--   direzione  +1 = più alto è meglio, -1 = più basso è meglio
--   obiettivo  sopra (o sotto) = «In target»
--   soglia     facoltativa: tra soglia e obiettivo = «Da attenzionare»,
--              oltre la soglia = «Critico» (senza soglia: mancato
--              obiettivo = «Critico»)
-- Per i flussi da inizio anno (EBITDA, fatturato, MWh…) l'obiettivo è
-- ANNUO e si confronta in proporzione ai mesi di competenza (ottobre =
-- 10/12): lo fa l'app, qui si salva il valore annuo.
-- Le righe eliminate dalla pagina si cancellano: la data e l'autore
-- dell'ultima modifica restano su ogni riga.
-- ============================================================

create table if not exists public.kpi_obiettivi (
    societa        text        not null check (societa in ('lifegate', 'gazel', 'migliora')),
    anno           integer     not null check (anno between 2024 and 2100),
    codice         text        not null,
    direzione      smallint    not null check (direzione in (1, -1)),
    obiettivo      numeric     not null,
    soglia         numeric,
    aggiornato_da  text        not null,
    aggiornato_il  timestamptz not null default now(),
    primary key (societa, anno, codice),
    check (soglia is null
           or (direzione = 1 and soglia <= obiettivo)
           or (direzione = -1 and soglia >= obiettivo))
);

alter table public.kpi_obiettivi enable row level security;

grant select, insert, update, delete on public.kpi_obiettivi to kpi_portale;
drop policy if exists kpi_portale_tutto on public.kpi_obiettivi;
create policy kpi_portale_tutto on public.kpi_obiettivi
    for all to kpi_portale using (true) with check (true);
