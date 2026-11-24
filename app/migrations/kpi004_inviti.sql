-- ============================================================
-- Migrazione kpi004 — inviti di accesso al Portale KPI NeWatt.
-- Database: progetto Supabase `cte-newatt`. Solo additiva; idempotente.
--
-- L'amministratore crea l'utente dalla pagina «Utenti e accessi»: l'utente
-- nasce SENZA password e riceve per email un link personale
-- (…/?invito=<token>) con cui sceglie la password. Nel DB sta solo lo SHA-256
-- del token, mai il token: chi legge la tabella non può usare i link.
-- Un invito vale una volta sola e scade (7 giorni); un nuovo invito annulla i
-- precedenti ancora aperti. Lo stesso meccanismo serve per reimpostare la
-- password.
-- ============================================================

create table if not exists public.kpi_inviti (
    id          bigint generated always as identity primary key,
    username    text not null references public.kpi_utenti (username)
                on update cascade on delete cascade,
    token_hash  text not null unique,                 -- sha256 esadecimale del token
    creato_da   text not null default '',
    creato_il   timestamptz not null default now(),
    scade_il    timestamptz not null,
    usato_il    timestamptz,                          -- password impostata
    annullato   boolean not null default false,       -- sostituito da un invito più recente
    email_inviata boolean not null default false
);
create index if not exists kpi_inviti_username on public.kpi_inviti (username);
comment on table public.kpi_inviti is
    'Portale KPI NeWatt: link di primo accesso / reimpostazione password (solo hash del token, monouso, con scadenza).';

alter table public.kpi_inviti enable row level security;
grant select, insert, update on public.kpi_inviti to kpi_portale;
grant usage, select on all sequences in schema public to kpi_portale;
drop policy if exists kpi_portale_tutto on public.kpi_inviti;
create policy kpi_portale_tutto on public.kpi_inviti
    for all to kpi_portale using (true) with check (true);
