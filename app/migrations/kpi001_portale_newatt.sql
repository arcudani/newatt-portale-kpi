-- ============================================================
-- Migrazione kpi001 — Portale KPI del gruppo NeWatt.
-- Database: progetto Supabase `cte-newatt` (NON bros-consulenza).
--
-- Tabelle con prefisso kpi_, separate da quelle dell'app CTE (utenti,
-- documenti, provvigioni, registro) che qui NON si toccano.
--
--   kpi_utenti       chi entra nel portale: ruolo + perimetro di società
--   kpi_caricamenti  un record per ogni Excel caricato (chi, quando, file)
--   kpi_valori       i KPI letti dal foglio DASHBOARD, uno per codice
--   kpi_valori_correnti  vista: per ogni società e mese del report vale
--                    l'ULTIMO caricamento non annullato (lo storico resta)
--
-- I valori del foglio sono year-to-date: si salvano così come sono, con il
-- mese di COMPETENZA (i KPI «M-1» sono del mese prima del report). Il valore
-- del singolo mese dei flussi si ricava in app per differenza.
--
-- RLS abilitata senza policy (deny-all via PostgREST): il portale legge e
-- scrive con il ruolo postgres attraverso il Transaction pooler.
-- Solo additiva; idempotente.
-- ============================================================

create table if not exists public.kpi_utenti (
    id             bigint generated always as identity primary key,
    username       text not null unique,
    nome           text not null default '',
    email          text not null default '',
    password_hash  text,                                   -- bcrypt; NULL = non può ancora entrare
    ruolo          text not null default 'lettore'
                   check (ruolo in ('admin', 'caricatore', 'lettore')),
    societa        text[] not null default '{}',           -- perimetro; vuoto = tutto il gruppo
    attivo         boolean not null default true,
    created_at     timestamptz not null default now(),
    constraint kpi_utenti_societa_ok
        check (societa <@ array['lifegate', 'gazel', 'migliora']::text[])
);
comment on table public.kpi_utenti is
    'Portale KPI NeWatt: utenti, ruolo (admin, caricatore, lettore) e perimetro di società (vuoto = tutto il gruppo).';

create table if not exists public.kpi_caricamenti (
    id             bigint generated always as identity primary key,
    societa        text not null check (societa in ('lifegate', 'gazel', 'migliora')),
    anno           smallint not null check (anno between 2020 and 2100),
    mese           smallint not null check (mese between 1 and 12),   -- mese del report (M)
    titolo_excel   text not null default '',
    file_nome      text not null default '',
    file_sha256    text not null default '',
    n_valori       integer not null default 0,
    caricato_da    text not null,
    caricato_il    timestamptz not null default now(),
    annullato      boolean not null default false,
    note           text not null default ''
);
create index if not exists kpi_caricamenti_periodo
    on public.kpi_caricamenti (societa, anno, mese, id desc);
comment on table public.kpi_caricamenti is
    'Un record per ogni Excel caricato: lo stesso mese caricato due volte = due versioni, vale l''ultima non annullata.';

create table if not exists public.kpi_valori (
    caricamento_id bigint not null references public.kpi_caricamenti (id) on delete cascade,
    codice         text not null,
    anno_comp      smallint not null,
    mese_comp      smallint not null check (mese_comp between 1 and 12),  -- mese di competenza
    valore         numeric,                                -- NULL = cella vuota o non numerica
    testo          text not null default '',               -- es. il mese del churn massimo
    primary key (caricamento_id, codice)
);
comment on table public.kpi_valori is
    'Valori year-to-date del foglio DASHBOARD, per caricamento e codice KPI, con il mese di competenza.';

create or replace view public.kpi_valori_correnti
with (security_invoker = true) as
select c.societa, c.anno, c.mese, c.id as caricamento_id, c.caricato_il, c.caricato_da,
       v.codice, v.anno_comp, v.mese_comp, v.valore, v.testo
from public.kpi_caricamenti c
join public.kpi_valori v on v.caricamento_id = c.id
where not c.annullato
  and c.id = (select max(c2.id) from public.kpi_caricamenti c2
              where c2.societa = c.societa and c2.anno = c.anno and c2.mese = c.mese
                and not c2.annullato);

alter table public.kpi_utenti enable row level security;
alter table public.kpi_caricamenti enable row level security;
alter table public.kpi_valori enable row level security;

-- Primi utenti (senza password: la imposta l'amministratore con imposta_pwd.py)
insert into public.kpi_utenti (username, nome, ruolo, societa)
values ('Daniele', 'Daniele Arculeo', 'admin', '{}'),
       ('Virginia', 'Virginia', 'caricatore', '{}')
on conflict (username) do nothing;
