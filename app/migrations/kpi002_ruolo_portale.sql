-- ============================================================
-- Migrazione kpi002 — utente di database dedicato al portale KPI.
-- Database: progetto Supabase `cte-newatt`.
--
-- Il portale NON usa la password principale (postgres) del progetto: entra
-- come `kpi_portale`, che vede e scrive SOLO le tabelle kpi_*. Le tabelle
-- dell'app CTE (utenti, documenti, provvigioni, registro) gli restano chiuse.
--
-- La password NON sta in questo file: si imposta a parte con
--   alter role kpi_portale password '<verificatore SCRAM>';
-- e la connection string va nel .env (NEWATT_DB_URL, utente
-- kpi_portale.<ref progetto> sul Transaction pooler, porta 6543).
--
-- RLS: le tabelle kpi_* restano deny-all per anon/authenticated (PostgREST);
-- le policy qui sotto aprono solo a kpi_portale.
-- ============================================================

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'kpi_portale') then
        create role kpi_portale login noinherit;
    end if;
end $$;

grant usage on schema public to kpi_portale;
grant select, insert, update on public.kpi_utenti to kpi_portale;
grant select, insert, update on public.kpi_caricamenti to kpi_portale;
grant select, insert on public.kpi_valori to kpi_portale;
grant select on public.kpi_valori_correnti to kpi_portale;
grant usage, select on all sequences in schema public to kpi_portale;

drop policy if exists kpi_portale_tutto on public.kpi_utenti;
create policy kpi_portale_tutto on public.kpi_utenti
    for all to kpi_portale using (true) with check (true);
drop policy if exists kpi_portale_tutto on public.kpi_caricamenti;
create policy kpi_portale_tutto on public.kpi_caricamenti
    for all to kpi_portale using (true) with check (true);
drop policy if exists kpi_portale_tutto on public.kpi_valori;
create policy kpi_portale_tutto on public.kpi_valori
    for all to kpi_portale using (true) with check (true);
