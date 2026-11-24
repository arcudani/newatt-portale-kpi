# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cos'è (da novembre 2026: Portale KPI del gruppo NeWatt)

**Portale KPI NeWatt** (decisione utente 24/11/2026: "portale NeWatt, stessa app"). Grafica NeWatt
(blu notte `#080337`, blu `#0000FF`, Poppins) e a sinistra le tre società del gruppo — **LifeGate
Energy · Gazel · Migliora** — ognuna con una dashboard nei suoi colori e logo (`branding.TEMI`,
`branding.applica_tema`). I KPI vengono dal **foglio DASHBOARD** dell'Excel mensile «Dashboard KPI»
di ogni società (stessi KPI per tutte), caricato in app da admin e caricatori (Daniele, Virginia):
- `kpi_catalogo.py` — 37 **misure** (una per cella: etichetta, M o M-1, unità, natura flusso/stock/
  rapporto) e 20 **tessere** (Livello I e II × Finanziario/Vendite/Cliente; regola: nessuna tessera
  divisa per commodity, il dettaglio luce/gas sta dentro).
- `kpi_import.py` — lettura per **etichetta** (non per cella), titolo «KPI MONITORING <SOCIETÀ>
  <MESE> <ANNO>» → società e mese; `ImportKPIError` con messaggi per chi carica (.xls, csv, protetto,
  danneggiato, senza DASHBOARD, foglio sbagliato) e avvisi (mancanti, #DIV/0!, celle vuote).
- `kpi_dati.py` — IO sul progetto Supabase **`cte-newatt`** (db base `"newatt"`, env `NEWATT_DB_URL`)
  con l'utente di database dedicato **`kpi_portale`** (vede solo `kpi_*`; migrazioni `kpi001`,
  `kpi002`). Storico: ogni Excel = un record `kpi_caricamenti` + `kpi_valori`; ricaricare un mese crea
  una nuova versione (vale l'ultima non annullata, vista `kpi_valori_correnti`); l'admin può annullare.
  I valori sono **year-to-date**: il valore del singolo mese dei flussi si ricava per differenza.
- `ui_kpi.py` — dashboard di società (`pagina_societa`) e panoramica di gruppo (`panoramica`).
- Login su `kpi_utenti` (`auth.py`): ruoli admin / caricatore / lettore, **perimetro** di società
  (vuoto = tutto il gruppo). Gli utenti si creano dalla pagina **Utenti e accessi** (solo admin,
  `moduli/utenti_accessi.py` + `utenti.py`): l'utente nasce senza password e riceve un'email (Brevo
  SMTP: `BREVO_LOGIN`, `BREVO_SMTP_KEY`, `MAIL_FROM`, link su `PORTALE_URL`) con username, società e un
  link personale `/?invito=<token>` (monouso, 7 giorni, nel DB solo lo SHA-256: tabella `kpi_inviti`,
  migrazione `kpi004`) dove sceglie la password (`accesso.py`, gestito in `app.py` PRIMA del login).
  Senza SMTP configurato il link compare in pagina da consegnare a mano. `imposta_pwd.py` resta per
  l'emergenza da riga di comando. Il Business Plan Migliora (viste V1-V11 +
  Catalogo, sotto) resta nel portale come sezione **solo admin**, nello stile Migliora, sui dati
  `bp_*` del progetto `bros-consulenza` (env `SUPABASE_DB_URL`).
- Test del portale: `test_kpi.py` (Excel DASHBOARD fittizio in `dati_prova.workbook_kpi`).

### Storia: Controllo BP Migliora

**Controllo BP Migliora** — quarta app Streamlit di Bros Consulenza (dopo `C:\Code\App_Offerte`,
`C:\Code\Bros_ERP`, `C:\Code\Gas_Monitor`): la dashboard di controllo del Business Plan 2026-2030 di
Migliora (gruppo NeWatt), costruita sul **blueprint DeD 3-30-300** (`Blueprint_Dashboard_BP_Migliora_3-30-300.docx`)
e sui requisiti `Requisiti_Modulo_BP_Migliora.md` v0.1, entrambi in
`G:\Drive condivisi\Migliora Energia in NeWatt\BP\`. Tutto in italiano (UI, commenti, testi).

App **separata** dall'ERP (scelta utente 11/09/2026): utenti e ruoli propri, così il management NeWatt
accede senza entrare nell'ERP Bros. Nell'ERP c'è solo la tile "Migliora" (solo admin) che punta qui
via `MIGLIORA_APP_URL`. Stato: **fase 1 (lettura)** in locale, **non ancora pubblicata**.

## Comandi (dalla cartella `app/`, con il python della venv)

venv: `C:\Code\Migliora_BP\app\.venv\Scripts\python.exe` (Python 3.12, Streamlit 1.63). Su Windows
anteporre `$env:PYTHONUTF8='1'` ai comandi che stampano €/Δ.

```bash
python -m streamlit run app.py --server.port 8540     # avvio (dietro login bp_utenti)
python run_tests.py                                   # tutta la suite (4 file)
python test_pagine.py                                 # un file (script standalone, exit 0/1)
python importa_bp.py "<BP.xlsx>" --nome "BP v6" --prova   # lettura + quadratura, nessuna scrittura
python importa_bp.py "<BP.xlsx>" --nome "BP v6"           # nuova versione in BOZZA su Supabase
python imposta_pwd.py Nome --ruolo admin --societa Bros   # utente/password (interattivo)
```

Test: **non pytest**, script con `if __name__ == "__main__"` e righe `OK - ...`. Girano offline su
dati **fittizi** (`dati_prova.py`: un BP Excel inventato con la stessa struttura del v5); solo il gate di
login reale e il controllo sul BP reale (se il Drive è montato) toccano risorse vere, e si saltano se
mancano. Le AppTest devono seminare `authentication_status`, `utente_autenticato`, `ruolo` e simulare
`auth.require_login`/`auth.ruolo` e `bp_dati.carica_*` (vedi `test_pagine._apptest`).

⚠️ Il dev server **non ricarica i moduli importati** (`bp_*`, `ui`, `filtri`, `branding`, `registro_moduli`):
dopo averli toccati riavviare. Le pagine in `moduli/` si ricaricano da sole.

## Architettura

**Shell + viste** (stesso pattern di Bros_ERP/Gas_Monitor, la danza navigation/login è load-bearing):
`app.py` fa bridge secrets → `set_page_config` → CSS → `st.navigation` (sempre, subito, una volta) →
**filtri globali in sidebar** (solo se già autenticato, così stanno sopra "Esci") → gate login →
`pg.run()`. Le viste in `moduli/` sono script top-level: niente `set_page_config`, login o CSS.
Aggiungere una vista = 1 file + 1 riga in `registro_moduli.MODULI` (codice V1..V11 del blueprint,
sezione L3/L30/L300, ruoli ammessi).

**Separazione puro / IO** (le funzioni pure sono testate offline):
- `bp_import.py` — **puro**: legge i valori calcolati del BP Excel (content-first: colonne dei mesi dalla
  riga d'intestazione con le date, righe per etichetta normalizzata cercata DOPO un'ancora di sezione,
  mai coordinate fisse). `VOCI` è il piano voci CE (codice, gerarchia, natura, famiglia CtS) e la fonte
  di `bp_voci`; `SPEC_DRIVER` i driver fisici con dimensioni conformi; `quadratura()` confronta le somme
  annue con il foglio Riepilogo (±0,1% o 1 €).
- `bp_calcoli.py` — **puro**: `Dati` (CE + driver di una versione), un calcolo per codice KPI registrato
  con `@kpi(...)`, `confronta()` (semaforo con soglia e **direzione** dal catalogo, non ±10% unico),
  aggregazioni per grafici/tabelle (ponte ricavi→utile, CE sintetico, heatmap, CtS per famiglia).
- `formato.py` — **puro**: numeri e date in italiano; None/NaN → "n.d." (mai 0 o #DIV/0!).
- `bp_dati.py` — IO Supabase (cache 5'): versioni, CE, driver, catalogo; `salva_versione` (COPY in una
  transazione), `aggiorna_stato` (approvazione vietata se quadratura KO: vincolo nella WHERE),
  `elimina_bozza`.
- `filtri.py` — filtri globali (versione, confronto, anno, periodo) e `contesto()` per le viste.
- `ui.py` — testata con **stato dati** sempre visibile, tessere KPI generate dal **catalogo**, pannelli,
  export Excel, grafici di confronto. `branding.py` — CSS, colori, `altair_it()` (usare SEMPRE questa:
  numeri italiani negli assi via labelExpr, Streamlit filtra le locale Vega). **Logo Migliora** in
  `assets/` (ricavato dal logo ufficiale, colori di marca esatti su trasparente): `Logo_Migliora.png`
  con claim per il login, `Logo_Migliora_marchio.png` per la barra laterale,
  `Logo_Migliora_marchio_bianco.png` (monocromatico, regola del brand book su fondo blu) per la testata,
  `Icona_Migliora.png` per scheda e sidebar chiusa. Quando arriva il file ufficiale
  `migliora-logo-bianco.png` (o il vettoriale) va sostituito a quello ricavato.

**Design system: Migliora Design System + handoff «Dashboard KPI Migliora — Riquadri esecutivi»**
(15/10/2026, `G:\Drive condivisi\Migliora Energia in NeWatt\E_KPI\Dashboard Migliora con KPI.zip`:
README, brand book, mock `.dc.html`). Vale per **tutta l'app**. Token: blu `#28326f`, teal `#009ebd`
(testo `#00738a`), azzurro `#97c7ec`, surface `#f5f8fd`, ink `#1a2044`, ink-muted `#5a6389`, line
`#d4dcee`; **Outfit** per i titoli, **Manrope** per testo e numeri (cifre tabulari); card su bordo
`line`, **nessuna ombra**; primario teal con testo bianco a 18px bold. Componenti (`ui.py` +
`branding.py`): **testata blu** con logo bianco, titolo, claim «Tutto cambia, tu decidi.»
(obbligatorio sotto il logo), «Aggiornato al …» (ultimo movimento della versione) e chip di stato
dati (`ui.testata`; il Cruscotto non ha `st.title`); **fasce per ambito** = contenitore orizzontale
con colonna colorata 140-168 px (blu / teal-testo / ink-muted / blu-scuro) e area riquadri a griglia
auto-fill (container query: 4 per riga da ~880 px, poi 3/2/1) (`ui.ambiti`); **riquadro KPI** tutti
uguali (`ui._modello` decide, `branding.riquadro_kpi` disegna): nome + chip di stato, cifra 44px con
**alone** del colore di stato (o «In attesa dati»), sparkline (fuori dal Cruscotto), **dettaglio per
commodity** con lampadina gialla / fiamma azzurra, «Rif. …», note, owner e codice. **Regola degli
stati** (scelta utente 15/10/2026): verde/giallo/rosso solo contro un riferimento reale — versione di
confronto (soglie), benchmark del catalogo, avvisi del KPI contro il piano (gap FTE); altrimenti
«Valore BP» / «Ipotesi BP» (teal) o «In attesa» (pending, riquadro tratteggiato). Il Cruscotto ha in
più la **barra filtri** (`ui.barra_filtri_cruscotto`): slicer Periodo (dai filtri globali), Commodity
(`f_commodity`: sui KPI con dettaglio la cifra diventa quella della commodity, `Misura.commodity_valori`;
gli altri dicono «non ripartito»), Canale (solo Agenti), e i **contatori per stato**. Le altre viste
tengono titolo, domanda, destinatari e selettore 3″/30″/300″. I mini-indicatori di Versioni e Catalogo
usano le classi `mg-hk*` (blocco di compatibilità nel CSS).

**Catalogo KPI su DB** (`bp_kpi_catalogo`): nome, definizione, unità, direzione, owner, fonte, stato
(attivo/segnaposto), fonte prevista, codice DeD, benchmark (testo + intervallo numerico
`bench_min`/`bench_max` da cui nascono avvisi e insight), **ambito** (raggruppamento delle tessere),
soglie, visibilità (`tutti`/`bros`), drill.
Le tessere si generano da qui; un codice attivo senza `@kpi` compare come "calcolo non implementato"
(`test_calcoli.test_catalogo_coerente` lo impedisce). Il seme è `migrations/bp002_catalogo_kpi.sql`
(`ON CONFLICT DO NOTHING`: le modifiche fatte sul DB non vengono sovrascritte).

**Ruoli** (`bp_utenti.ruolo`, blueprint §9): admin (Bros: tutto, approva/archivia), editor (analisti Bros:
bozze, import), viewer (NeWatt: solo versioni **approvate**, niente KPI/voci con visibilità `bros`, niente
Consuntivo). Il perimetro riservato è configurazione (catalogo + `ui.voci_riservate`), non codice sparso.

## Modello dati (Supabase `bros-consulenza`, prefisso `bp_`, migrazioni `bp###`)

`bp001_modello_dati.sql`: `bp_utenti`, `bp_versioni` (stato bozza/approvata/archiviata + esito
quadratura jsonb), `bp_voci`, `bp_ce_mensile` (versione, voce, anno, mese, importo), `bp_driver_mensile`
(driver + canale/segmento/commodity/prodotto_vas/ruolo; `''` = non applicabile), `bp_kpi_catalogo`,
vista `v_bp_annuale` (security_invoker). `bp003_ambiti_benchmark.sql`: colonne `ambito`,
`bench_min`, `bench_max` del catalogo (raggruppamento delle tessere e benchmark numerici; il seme
è letto anche da `dati_prova.catalogo_seed`, così i test vedono lo stesso catalogo del DB).
`bp004_cruscotto_kpi_l1.sql` (solo dati, nessun DDL), `bp005_clt_unico.sql`, `bp006_churn_unico.sql` e `bp007_sales_plan_unico.sql`: i **9 KPI di primo livello** fissati da
Migliora il 15/10/2026 sostituiscono i 9 del Cruscotto (Economico-finanziario: EBITDA, PFN,
% Insoluto · Commerciale: Sales plan, Churn LTM · Cliente e servizio: NPS, Costo per
cliente, Cost-to-Serve, CLT unico). **Regola: nessuna tessera per singola commodity**: Sales plan, Churn e CLT sono UN KPI con il dettaglio per commodity in piccolo sotto il numero (`Misura.commodity`, reso da `branding.dettaglio_commodity` con lampadina gialla per EE e fiamma blu per il gas). Fino al consuntivo: valore BP dove c'è, «ipotesi BP» per il
churn, «in attesa dati» con l'obiettivo di attivazioni per il Sales plan; PFN, Insoluto, NPS e CLT
non sono nel BP. Utile, Forecast e Margine unitario passano in V2, Mix e Churn totale in V3 (i
codici `L3_*` restano: sono identificativi); `L3_RICAVI` e `L3_PDP` sono **cancellati** perché
duplicavano `V2_FATTURATO` e `V3_PDP` (unica eccezione, di dati, alla regola additiva).
`catalogo_seed` applica bp002 → bp003 → bp004 nell'ordine. Convenzioni del DB condiviso: **solo additive**, **RLS abilitata
senza policy** (deny-all via PostgREST; l'app usa il ruolo postgres col Transaction pooler,
`prepare_threshold=None`). I file `.sql` sono la fonte di verità; applicati via MCP `apply_migration`.

Versione 1 = "BP v5 FTE" (Bozza_2026.08, v5), importata l'11/09/2026 in **bozza**, quadratura 95/95.

## Regole di contenuto (non "correggerle" senza decisione)

- **Costi con segno negativo** come nel BP: sulle voci CE uno scostamento positivo è sempre favorevole;
  nelle tessere i costi si mostrano in valore assoluto con direzione ↓.
- **IRES/IRAP** esistono solo come totale annuo: imputate a **dicembre**, e il risultato netto di dicembre è
  rettificato delle stesse imposte (così la somma dei mesi quadra col Riepilogo).
- **Piano da ottobre 2026** (`INIZIO_PIANO`); il **2026 è avviamento**: valori assoluti visibili, rapporti e
  unitari "n.d. — avviamento".
- **PdP = POD + PDR del canale Agenti**: nel v5 i PdP del canale VAS sono un "di cui" (canale fantasma, vedi
  `Nota_ricostruzione_VAS_BP_Migliora.md`); le viste V4 e V9 lo segnalano da sole.
- **Unitari su PdP medi** (catalogo del blueprint), annualizzati; la **"riga BP"** (su PdP a fine anno: CtS
  29/18/12/11, EBITDA/PdP 158…320) è mostrata come nota nelle tessere per riconciliare con l'Excel.
- Le righe VAS gas del foglio "CdV - Calcolo PM VAS" sono etichettate "Power" nel v5: si leggono per
  posizione dopo l'ancora "Margine Totale Gas Retail".
- "Apertura Sportelli" nel v5 è un flag (1 = sportello operativo), non un conteggio di aperture.

## GDPR / riservatezza

Nessun numero del BP nel repo: `.xlsx/.csv/.pdf`, `.env` e `_dev_data/` sono gitignored; i test usano
`dati_prova.py` (inventati) e sul BP reale verificano solo l'esito della quadratura.

## Fasi (blueprint §11) e prossimi passi

1 **Lettura** (fatto): V1 Cruscotto, V2-V5 Tactical, V6 Scostamenti, V9 FTE, V11 Versioni, Catalogo;
V7/V8/V10 segnaposto. Poi: 0 motore Python che riproduce l'Excel (quadratura ±0,1%, chiusura rilievi:
rinnovi positivi, VAS cross-sell, doppio conteggio FTE, costi VAS = 0) · 2 scrittura (V7/V8 su bozze, log,
anteprima impatto) · 3 consuntivo (V10, YTD/forecast/semafori BP vs actual, note firmate) · 4 DeD.
Punti aperti da validare con NeWatt: blueprint §12 (9° KPI, mix target, definizione CtS, perimetro
riservato, soglie, owner nominativi).

## Deploy

Non ancora pubblicata. Checklist in [DEPLOY.md](DEPLOY.md). **Ogni push su `main` di un repo collegato
a Streamlit Community Cloud rideploya**: mai push senza conferma esplicita dell'utente.
