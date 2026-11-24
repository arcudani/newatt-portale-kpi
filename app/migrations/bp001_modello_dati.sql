-- ============================================================
-- Migrazione bp001 — modello dati del Controllo BP Migliora.
--
-- App Streamlit SEPARATA (repo Migliora_BP) sullo stesso DB Supabase di
-- ERP, App_Offerte ed Energy Market Monitor. Convenzioni:
--   * prefisso bp_*, numerazione bp###_ (non collide con 000x_ di
--     App_Offerte e g###_ del Gas Monitor);
--   * SOLO ADDITIVA (DB condiviso con la produzione);
--   * RLS abilitata senza policy (deny-all via PostgREST): l'app si
--     connette col ruolo postgres come le altre;
--   * viste con security_invoker, così non scavalcano la RLS.
--
-- Fase 1 (lettura): utenti, versioni, piano voci, CE e driver mensili,
-- catalogo KPI. Consuntivo, mapping conti, parametri editabili e log
-- modifiche arrivano con le fasi 2-3 (migrazioni successive).
-- ============================================================

-- ---------- UTENTI (separati da public.utenti dell'ERP) ----------
create table public.bp_utenti (
    id            bigint generated always as identity primary key,
    username      text not null unique,
    password_hash text,                                   -- bcrypt; NULL = mai impostata
    ruolo         text not null default 'viewer'
                  check (ruolo in ('admin','editor','viewer')),
    societa       text not null default 'NeWatt'
                  check (societa in ('Bros','NeWatt','Migliora')),
    email         text not null default '',
    attivo        boolean not null default true,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);
comment on table public.bp_utenti is
    'Utenti del Controllo BP Migliora. SEPARATI da public.utenti: chi sta qui NON accede a ERP/app Offerte.';
comment on column public.bp_utenti.ruolo is
    'admin = Bros (tutto, approvazione versioni); editor = analisti Bros (bozze); viewer = management NeWatt (solo versioni approvate).';

-- ---------- VERSIONI DEL BP ----------
create table public.bp_versioni (
    id            bigint generated always as identity primary key,
    nome          text not null unique,
    descrizione   text not null default '',
    stato         text not null default 'bozza'
                  check (stato in ('bozza','approvata','archiviata')),
    origine       text not null default '',               -- file Excel importato / 'motore'
    quadratura_ok boolean,                                -- esito vs Riepilogo Excel (±0,1%)
    quadratura    jsonb not null default '[]'::jsonb,     -- dettaglio per voce/anno
    creata_da     text not null default '',
    created_at    timestamptz not null default now(),
    stato_da      text not null default '',               -- ultimo cambio stato: chi
    stato_il      timestamptz                             -- ultimo cambio stato: quando
);
comment on table public.bp_versioni is
    'Versioni del BP Migliora. Il viewer vede solo le approvate; una versione fuori quadratura non è approvabile.';

-- ---------- PIANO DELLE VOCI (base comune a BP e consuntivo) ----------
create table public.bp_voci (
    codice       text primary key,
    etichetta    text not null,
    padre        text references public.bp_voci(codice),
    livello      smallint not null check (livello between 1 and 3),
    ordine       integer not null,
    natura       text not null check (natura in ('ricavo','costo','margine')),
    commodity    text not null default '',                -- dimensione conforme (Power/Gas)
    famiglia_cts text not null default ''                 -- famiglia di costo per il Cost-to-Serve
);
comment on table public.bp_voci is
    'Voci del conto economico del BP con gerarchia (livello 1-3). I costi hanno segno negativo come nel BP.';

-- ---------- CONTO ECONOMICO MENSILE ----------
create table public.bp_ce_mensile (
    versione_id bigint   not null references public.bp_versioni(id) on delete cascade,
    voce        text     not null references public.bp_voci(codice),
    anno        smallint not null,
    mese        smallint not null check (mese between 1 and 12),
    importo     numeric  not null,
    primary key (versione_id, voce, anno, mese)
);
comment on table public.bp_ce_mensile is
    'CE mensilizzato per versione (ott 2026 - dic 2030). IRES/IRAP sono annuali: imputate a dicembre.';

-- ---------- DRIVER FISICI MENSILI (dimensioni conformi) ----------
create table public.bp_driver_mensile (
    versione_id  bigint   not null references public.bp_versioni(id) on delete cascade,
    driver       text     not null,                       -- es. pdp_attivi, produzione, fte_necessari
    canale       text     not null default '',            -- Agenti / VAS
    segmento     text     not null default '',            -- Retail / Business
    commodity    text     not null default '',            -- Power / Gas
    prodotto_vas text     not null default '',            -- Assicurazione / Manutenzione / Telecomunicazioni
    ruolo        text     not null default '',            -- ruolo FTE
    anno         smallint not null,
    mese         smallint not null check (mese between 1 and 12),
    valore       numeric  not null,
    primary key (versione_id, driver, canale, segmento, commodity, prodotto_vas, ruolo, anno, mese)
);
comment on table public.bp_driver_mensile is
    'Driver fisici del BP per mese e versione. Dimensione vuota ('''') = non applicabile.';

-- ---------- CATALOGO KPI (una definizione, un owner, una fonte) ----------
create table public.bp_kpi_catalogo (
    codice         text primary key,
    nome           text not null,
    livello        smallint not null check (livello in (3,30,300)),
    vista          text not null,                          -- V1..V11
    ordine         smallint not null default 0,
    definizione    text not null default '',
    unita          text not null default '',
    direzione      smallint not null default 1 check (direzione in (-1,0,1)),
    owner          text not null default '',
    frequenza      text not null default 'mensile',
    fonte          text not null default 'BP',
    stato          text not null default 'attivo' check (stato in ('attivo','segnaposto')),
    fonte_prevista text not null default '',               -- per i segnaposto: da dove arriverà il dato
    rif_ded        text not null default '',               -- codice del catalogo DeD (52 KPI)
    benchmark      text not null default '',
    soglia_gialla  numeric,                                -- % (o punti % se unita = '%')
    soglia_rossa   numeric,
    visibilita     text not null default 'tutti' check (visibilita in ('tutti','bros')),
    drill          text not null default ''                -- vista aperta dal click sulla tessera
);
comment on table public.bp_kpi_catalogo is
    'Catalogo KPI 3-30-300: genera le tessere delle viste. direzione +1 = più alto è meglio, -1 = più basso è meglio, 0 = neutro.';

-- ---------- VISTA DI SINTESI ANNUALE (leggibile anche da Power BI) ----------
create view public.v_bp_annuale with (security_invoker = true) as
select c.versione_id, v.nome as versione, c.voce, x.etichetta, x.livello, x.natura,
       c.anno, sum(c.importo) as importo
from public.bp_ce_mensile c
join public.bp_versioni v on v.id = c.versione_id
join public.bp_voci x on x.codice = c.voce
group by c.versione_id, v.nome, c.voce, x.etichetta, x.livello, x.natura, c.anno;

-- ---------- RLS: abilitata senza policy (deny-all) ----------
alter table public.bp_utenti          enable row level security;
alter table public.bp_versioni        enable row level security;
alter table public.bp_voci            enable row level security;
alter table public.bp_ce_mensile      enable row level security;
alter table public.bp_driver_mensile  enable row level security;
alter table public.bp_kpi_catalogo    enable row level security;
