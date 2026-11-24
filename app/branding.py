"""
Design system del Controllo BP Migliora — CSS, colori, componenti HTML,
tema Altair.

Linguaggio visivo: **Migliora Design System** (brand book v1.0) con le deroghe
dell'handoff «Dashboard KPI Migliora — Riquadri esecutivi» (15/10/2026):
testata blu con logo bianco e claim, barra filtri a slicer con contatori per
stato, fasce per ambito con la colonna del titolo colorata, riquadri KPI tutti
uguali con chip di stato, alone dietro la cifra, dettaglio per commodity
(lampadina / fiamma), «Rif.», nota, owner e codice. Outfit per i titoli,
Manrope per testo e numeri (sempre cifre tabulari). Card su bordo `line`,
nessuna ombra.

Stati dei KPI (deroga richiesta dal committente per la dashboard interna:
semaforo e icone non stanno nei materiali per i Clienti):
    ok      In target        verde   #1f7a4d
    warn    Da attenzionare  giallo  #f5c400 (testo #8a6a00)
    crit    Critico          rosso   #b23a32
    bp      Valore/Ipotesi BP teal   #00738a  (nessun riferimento reale)
    pend    In attesa        neutro  (nessun alone)
Il semaforo si accende solo contro un riferimento reale (versione di
confronto, benchmark del catalogo, piano FTE): il BP confrontato con se stesso
non è «in target».

Serie dei grafici: versione di riferimento = blu Migliora, versione di
confronto = teal; categoriche Okabe-Ito (leggibili con discromatopsie).
"""
from __future__ import annotations

import base64
import functools
from html import escape
from pathlib import Path

import altair as alt
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
# Logo Migliora (ricavato dal logo ufficiale, colori di marca su trasparente):
# completo con claim per il login, marchio per la barra laterale, marchio
# BIANCO per la testata blu (regola del brand book: su blu la versione bianca).
LOGO_PATH = APP_DIR / "assets" / "Logo_Migliora_marchio.png"
LOGO_LOGIN_PATH = APP_DIR / "assets" / "Logo_Migliora.png"
LOGO_BIANCO_PATH = APP_DIR / "assets" / "Logo_Migliora_marchio_bianco.png"
ICONA_PATH = APP_DIR / "assets" / "Icona_Migliora.png"
CLAIM = "Tutto cambia, tu decidi."

# ---- Token Migliora (brand book) ----
BLU, BLU_SCURO = "#28326f", "#1c2454"
AZZURRO, AZZURRO_TENUE = "#97c7ec", "#e3f0fb"
TEAL, TEAL_TESTO = "#009ebd", "#00738a"
SURFACE, INK, INK_MUTED, LINE = "#f5f8fd", "#1a2044", "#5a6389", "#d4dcee"

# ---- Serie dei grafici ----
C_BP = BLU                 # versione di riferimento
C_CONFRONTO = TEAL         # versione di confronto
C_CONSUNTIVO = "#1a2044"   # consuntivo (fase 3): inchiostro, da rivedere con i dati reali
# ---- Toni (barre, heatmap, anelli): sempre con testo, mai solo colore ----
C_BUONO, C_ATTENZIONE, C_CATTIVO, C_NEUTRO = "#1f7a4d", "#f5c400", "#b23a32", "#b9c6e2"
TONO_COLORE = {"buono": C_BUONO, "attenzione": C_ATTENZIONE, "cattivo": C_CATTIVO,
               "neutro": C_NEUTRO}
STATO_TONO = {"ok": "buono", "warn": "attenzione", "crit": "cattivo", "neutral": "neutro"}
# ---- Categoriche (Okabe-Ito, ordine fisso) ----
C_COMMODITY = {"Power": "#0072B2", "Gas": "#E69F00"}
C_SEGMENTO = {"Retail": "#009E73", "Business": "#CC79A7"}
C_PRODOTTO = {"Assicurazione": "#0072B2", "Manutenzione": "#009E73",
              "Telecomunicazioni": "#CC79A7"}
CATEGORICHE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#44AA99", "#F0E442"]
# ---- Colonna colorata delle fasce per ambito (testo bianco sopra) ----
C_AMBITI = [BLU, TEAL_TESTO, INK_MUTED, BLU_SCURO]

# ---- Stati dei riquadri KPI (handoff, tabella «Stati KPI») ----
STATI_KPI = {
    "ok": {"label": "In target", "glow": "rgba(31,122,77,0.38)"},
    "warn": {"label": "Da attenzionare", "glow": "rgba(245,196,0,0.55)"},
    "crit": {"label": "Critico", "glow": "rgba(178,58,50,0.38)"},
    "bp": {"label": "Valore BP", "glow": "rgba(151,199,236,0.75)"},
    "pend": {"label": "In attesa", "glow": ""},
}
ORDINE_CONTATORI = [("ok", "In target"), ("warn", "Da attenzionare"), ("crit", "Critico"),
                    ("bp", "Valore BP"), ("pend", "In attesa dati")]

MIGLIORA_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root {
        --mg-blu:#28326f; --mg-blu-scuro:#1c2454; --mg-azzurro:#97c7ec; --mg-azzurro-tenue:#e3f0fb;
        --mg-teal:#009ebd; --mg-teal-testo:#00738a; --mg-surface:#f5f8fd; --mg-ink:#1a2044;
        --mg-mut:#5a6389; --mg-line:#d4dcee; --mg-line-ph:#b9c6e2; --mg-track:#e9eef7;
        --mg-ok:#1f7a4d; --mg-ok-bg:#e6f3ec; --mg-warn:#f5c400; --mg-warn-ink:#8a6a00;
        --mg-warn-bg:#fff6d1; --mg-crit:#b23a32; --mg-crit-bg:#fbe9e7;
        --mg-font:"Manrope","Segoe UI",system-ui,sans-serif;
        --mg-font-t:"Outfit","Trebuchet MS",system-ui,sans-serif;
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    .stApp, button, input, textarea, select {
        font-family: var(--mg-font) !important; -webkit-font-smoothing: antialiased;
    }
    .stApp { background: var(--mg-surface); color: var(--mg-ink); font-variant-numeric: tabular-nums; }
    /* la barra di Streamlit (Deploy/menu) è in overlay: senza questo spazio
       la testata ci finisce sotto e il logo si taglia */
    .block-container { padding-top: 2.9rem !important; max-width: 1500px; }
    *:focus-visible { outline: 2px solid var(--mg-teal) !important; outline-offset: 2px; }

    /* === Titoli: Outfit, peso 600, blu === */
    h1 { font-family: var(--mg-font-t) !important; font-size: 28px !important; line-height: 34px !important;
         font-weight: 600 !important; letter-spacing: -.01em; color: var(--mg-titolo, var(--mg-blu)) !important;
         margin: 14px 0 2px !important; padding: 0 !important; }
    h1::after { display: none !important; }
    h2 { font-family: var(--mg-font-t) !important; font-size: 22px !important; font-weight: 600 !important;
         color: var(--mg-ink) !important; }
    h3 { font-family: var(--mg-font-t) !important; font-size: 17px !important; font-weight: 600 !important;
         color: var(--mg-titolo, var(--mg-blu)) !important; }
    h4, h5, h6 { font-weight: 700 !important; color: var(--mg-mut) !important; }

    /* === Testata blu: logo bianco + titolo + claim, a destra aggiornamento e stato dati === */
    .mg-top { background: var(--mg-top-bg, var(--mg-blu)); color:var(--mg-top-ink, #fff);
        border-bottom: var(--mg-top-bordo, 0 solid transparent); border-radius: var(--mg-r-card, 12px); padding: 12px 24px;
        border-left: var(--mg-top-accento, 0 solid transparent); box-shadow: var(--mg-sh, none);
        outline: var(--mg-top-contorno, 0 solid transparent); outline-offset: -1px;
        display:flex; align-items:center; justify-content:space-between; gap: 12px 24px; flex-wrap: wrap;
        margin-bottom:12px; }
    .mg-top-l { display:flex; align-items:center; gap:16px; min-width:0; }
    .mg-top-logo { display:block; width:auto; height:var(--mg-logo-h, 40px); max-width:220px; flex:none; }
    .mg-top-word { font-family: var(--mg-font-t); font-weight:700; font-size:26px; letter-spacing:-.02em;
        line-height:1; white-space:nowrap; }
    .mg-top-brand { font-family: var(--mg-font-t); font-weight: 700; font-size: 24px; color:#fff; }
    .mg-top-txt { display:flex; flex-direction:column; }
    .mg-top-tit { font-family: var(--mg-font-t); font-size:17px; line-height:22px; font-weight:600; }
    .mg-top-claim { font-size:12px; line-height:16px; }
    .mg-top-r { display:flex; flex-direction:column; align-items:flex-end; gap:6px; margin-left:auto; }
    .mg-top-agg { font-size:14px; line-height:20px; white-space:nowrap; }
    .mg-chips { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
    .mg-chip { display:inline-flex; align-items:center; gap:6px; background:var(--mg-chip-bg, rgba(255,255,255,.10));
        border:1px solid var(--mg-chip-bd, rgba(255,255,255,.30)); color:var(--mg-top-ink, #fff); font-size:12px; line-height:16px;
        font-weight:600; padding:3px 10px; border-radius:999px; white-space:nowrap; }
    .mg-chip b { font-weight:800; }
    .mg-chip.warn { background:var(--mg-warn-bg); border-color:var(--mg-warn); color:var(--mg-warn-ink); }
    .mg-chip.crit { background:var(--mg-crit-bg); border-color:var(--mg-crit); color:var(--mg-crit); }
    .mg-chip i { width:8px; height:8px; border-radius:999px; background:var(--c); display:inline-block;
        flex:none; border:1.5px solid #fff; }
    .mg-dom { font-size:14px; line-height:20px; color:var(--mg-mut); margin:10px 0 0; }
    .mg-dom:last-child { margin-bottom:14px; }   /* aria prima del pannello che segue */
    .mg-aud { font-size:12px; line-height:16px; color:var(--mg-mut); margin:4px 0 2px;
        font-weight:700; letter-spacing:.06em; text-transform:uppercase; }

    /* === Selettore di livello 3" / 30" / 300" (page_link a pillola) === */
    .st-key-mg_liv { background: var(--mg-track); border-radius:999px; padding:4px; width:max-content;
        gap:2px !important; margin: 10px 0 14px; flex-wrap: nowrap !important; }
    .st-key-mg_liv [data-testid="stPageLink"] a p { white-space: nowrap; }
    /* niente larghezze uguali tra le pillole: ognuna larga quanto il suo testo */
    .st-key-mg_liv [data-testid="stElementContainer"],
    .st-key-mg_liv [data-testid="stVerticalBlock"],
    .st-key-mg_liv [data-testid="stPageLink"] { flex:0 0 auto !important; width:max-content !important; }
    .st-key-mg_liv [data-testid="stPageLink"] a { padding:5px 15px !important; border-radius:999px;
        width:max-content; }
    .st-key-mg_liv [data-testid="stPageLink"] a p { font-weight:700 !important; font-size:13px !important;
        color: var(--mg-mut) !important; }
    .st-key-mg_liv [class*="st-key-liv_on"] [data-testid="stPageLink"] a { background:#fff;
        border:1px solid var(--mg-line); }
    .st-key-mg_liv [class*="st-key-liv_on"] [data-testid="stPageLink"] a p { color: var(--mg-blu) !important; }

    /* === Barra filtri (slicer) con contatori per stato === */
    .st-key-mg_slicer { background:#fff; border:1px solid var(--mg-line); border-radius:var(--mg-r-card, 12px);
        box-shadow:var(--mg-sh, none);
        padding:12px 16px !important; margin:0 0 4px; }
    .st-key-mg_slicer [data-testid="stHorizontalBlock"] { align-items:center; }
    /* slicer: etichetta maiuscoletta sopra, casella con bordo line; il Periodo
       (sola lettura) ha la stessa geometria delle tendine accanto */
    .st-key-mg_slicer [data-testid="stHorizontalBlock"] { align-items:flex-end !important; }
    .mg-slicer { display:flex; flex-direction:column; gap:0; }
    .mg-slicer-l, .st-key-mg_slicer [data-testid="stWidgetLabel"] p { font-size:11px !important;
        line-height:14px !important; font-weight:700 !important; letter-spacing:.06em;
        text-transform:uppercase; color:var(--mg-mut) !important; }
    .mg-slicer-l { display:flex; align-items:center; min-height:1.5rem; margin-bottom:.25rem; }
    .mg-slicer-v { height:40px; display:flex; align-items:center; padding:0 12px; border:1px solid var(--mg-line);
        border-radius:6px; background:var(--mg-surface); font-size:14px; font-weight:600; color:var(--mg-ink);
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .st-key-mg_slicer [data-baseweb="select"] > div { border-radius:6px !important; min-height:40px;
        background:#fff !important; border:1px solid var(--mg-line) !important; }
    .st-key-mg_slicer [data-baseweb="select"] div { font-weight:600; color:var(--mg-ink); }
    .mg-cnt { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .mg-cnt span.c { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px;
        font-size:12px; line-height:16px; font-weight:700; background:var(--sb); color:var(--sc);
        white-space:nowrap; }
    .mg-cnt span.c i, .mg-st i { width:8px; height:8px; border-radius:999px; background:var(--sd);
        border:1.5px solid var(--sc); flex:none; }
    .ok { --sc:#1f7a4d; --sb:#e6f3ec; --sd:#1f7a4d; }
    .warn { --sc:#8a6a00; --sb:#fff6d1; --sd:#f5c400; }
    .crit { --sc:#b23a32; --sb:#fbe9e7; --sd:#b23a32; }
    .bp { --sc:#00738a; --sb:#e3f0fb; --sd:#00738a; }
    .pend { --sc:#5a6389; --sb:#ffffff; --sd:transparent; }
    .mg-cnt span.c.pend { border:1px solid var(--mg-line); }

    /* === Fasce per ambito: colonna del titolo colorata + riquadri === */
    /* fascia = contenitore orizzontale: colonna titolo 120-168 px + area riquadri */
    div[class*="st-key-band_"] { background:#fff; border:1px solid var(--mg-line); border-radius:var(--mg-r-card, 12px);
        box-shadow:var(--mg-sh, none);
        overflow:hidden; padding:0 !important; gap:0 !important; margin-bottom:4px;
        flex-direction:row !important; flex-wrap:nowrap !important; align-items:stretch !important; }
    /* Streamlit avvolge ogni contenitore in uno stLayoutWrapper: è lui l'elemento flex */
    div[class*="st-key-band_"] > [data-testid="stLayoutWrapper"]:first-child {
        flex:0 0 clamp(140px, 18%, 168px) !important; width:auto !important; max-width:168px; }
    div[class*="st-key-band_"] > [data-testid="stLayoutWrapper"]:last-child {
        flex:1 1 0 !important; min-width:0; width:auto !important; }
    div[class*="st-key-bandh_"] { background:var(--amb, var(--mg-blu)); color:#fff;
        height:100%; padding:16px !important; justify-content:center; }
    div[class*="st-key-bandh_"][class*="_a0"] { --amb:var(--amb0, #28326f); }
    div[class*="st-key-bandh_"][class*="_a1"] { --amb:var(--amb1, #00738a); }
    div[class*="st-key-bandh_"][class*="_a2"] { --amb:var(--amb2, #5a6389); }
    div[class*="st-key-bandh_"][class*="_a3"] { --amb:var(--amb3, #1c2454); }
    /* area riquadri: come grid auto-fill minmax(210px,1fr) dell'handoff, con le
       container query (4 per riga a ~1280 px, poi 3 / 2 / 1) */
    div[class*="st-key-bandk_"] { width:auto !important;
        padding:12px !important; container-type:inline-size;
        flex-direction:row !important; flex-wrap:wrap !important; gap:12px !important;
        align-items:stretch !important; align-content:flex-start; }
    div[class*="st-key-bandk_"] > div { flex:0 0 100%; min-width:0; width:auto !important; }
    @container (min-width: 432px) { div[class*="st-key-bandk_"] > div { flex-basis:calc((100% - 12px) / 2); } }
    @container (min-width: 654px) { div[class*="st-key-bandk_"] > div { flex-basis:calc((100% - 24px) / 3); } }
    @container (min-width: 876px) { div[class*="st-key-bandk_"] > div { flex-basis:calc((100% - 36px) / 4); } }
    @media (max-width: 700px) {
        div[class*="st-key-band_"] { flex-direction:column !important; }
        div[class*="st-key-band_"] > [data-testid="stLayoutWrapper"]:first-child {
            flex-basis:auto !important; max-width:none; }
    }
    @container (min-width: 432px) { div[class*="st-key-bandk_G_"] > div { flex-basis:calc((100% - 12px) / 2); } }
    @container (min-width: 1000px) { div[class*="st-key-bandk_G_"] > div { flex-basis:calc((100% - 36px) / 4); } }
    div[class*="st-key-bandk_G_"] > div:has([class*="_vuoto"]) { flex-basis:100% !important; }
    div[class*="st-key-kpi_G_"][class*="_vuoto"] .mg-k { min-height:0; }
    .mg-amb-ico { width:32px; height:32px; display:block; margin-bottom:10px; flex:none; }
    .mg-amb-title { font-family: var(--mg-font-t); font-size:17px; line-height:22px; font-weight:600;
        color:#fff; display:block; overflow-wrap:normal; word-break:normal; hyphens:none; }
    .mg-amb-cnt { font-size:12px; line-height:16px; font-weight:700; letter-spacing:.06em;
        text-transform:uppercase; color:#fff; display:block; margin-top:4px; }

    /* === Riquadro KPI (tutti uguali) === */
    /* stessa altezza nella riga: ogni anello della catena Streamlit
       (wrapper -> contenitore -> elemento -> markdown) cresce fino al riquadro */
    div[class*="st-key-kpi_"] { position:relative; flex:1 1 auto; }
    div[class*="st-key-kpi_"] > [data-testid="stElementContainer"]:first-child { flex:1 1 auto;
        display:flex; flex-direction:column; }
    div[class*="st-key-kpi_"] > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"],
    div[class*="st-key-kpi_"] > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] > div,
    div[class*="st-key-kpi_"] [data-testid="stMarkdownContainer"] { flex:1 1 auto; display:flex;
        flex-direction:column; margin-bottom:0 !important; }
    div[class*="st-key-kpi_"] .mg-k { flex:1 1 auto; }
    .mg-k { position:relative; overflow:hidden; background:#fff; border:1px solid var(--mg-line);
        border-radius:var(--mg-r-card, 12px); box-shadow:var(--mg-sh-k, none); padding:16px; display:flex; flex-direction:column; gap:8px;
        min-height:184px; height:100%; box-sizing:border-box; }
    .mg-k.pend { background:var(--mg-surface); border:1px dashed var(--mg-line-ph); }
    .mg-k-head { display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:nowrap;
        gap:8px; min-height:32px; }
    .mg-k-name { font-size:12px; line-height:16px; font-weight:700; letter-spacing:.06em;
        text-transform:uppercase; color:var(--mg-mut); min-width:0; padding-top:2px; }
    .mg-st { display:inline-flex; align-items:center; gap:6px; padding:2px 8px; border-radius:999px;
        background:var(--sb); color:var(--sc); flex-shrink:0; font-size:11px; line-height:16px;
        font-weight:700; white-space:nowrap; }
    .mg-st i { width:6px; height:6px; }
    .mg-st.pend { border:1px solid var(--mg-line); }
    .mg-k-val { position:relative; display:flex; align-items:baseline; gap:4px; padding:6px 0; }
    .mg-k-val .glow { position:absolute; left:-14px; top:50%; width:96px; height:96px; transform:translateY(-50%);
        border-radius:999px; background:radial-gradient(circle, var(--glow) 0%, rgba(255,255,255,0) 70%);
        pointer-events:none; }
    .mg-k-val .n { position:relative; font-size:44px; line-height:1; font-weight:800; letter-spacing:-.03em;
        color:var(--mg-ink); font-variant-numeric:tabular-nums; white-space:nowrap; }
    .mg-k-val .u { position:relative; font-size:16px; line-height:20px; font-weight:600; color:var(--mg-ink); }
    .mg-k-val.nd .n { font-size:24px; color:var(--mg-mut); }
    .mg-k-pend { font-family: var(--mg-font-t); font-size:20px; line-height:26px; font-weight:600;
        color:var(--mg-mut); padding:6px 0; }
    .mg-split { display:flex; flex-direction:column; gap:4px; }
    .mg-split-r { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:4px 8px;
        border-radius:6px; background:#fff; border:1px solid var(--mg-line); font-size:13px; line-height:18px; }
    .mg-split-r .l { display:flex; align-items:center; gap:6px; min-width:0; color:var(--mg-mut); }
    .mg-split-r .l span { overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
    .mg-split-r b { font-weight:700; color:var(--mg-ink); white-space:nowrap; font-variant-numeric:tabular-nums; }
    .mg-com-ico { width:14px; height:14px; display:block; flex:none; }
    .mg-k-rif { font-size:13px; line-height:18px; color:var(--mg-ink); }
    .mg-k-rif b { font-weight:700; }
    .mg-k-note { font-size:13px; line-height:18px; color:var(--mg-mut); }
    .mg-delta { font-weight:700; white-space:nowrap; }
    .mg-delta.buono { color:var(--mg-ok); } .mg-delta.cattivo { color:var(--mg-crit); }
    .mg-delta.attenzione { color:var(--mg-warn-ink); } .mg-delta.neutro { color:var(--mg-mut); }
    .mg-pill { display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700;
        padding:2px 8px; border-radius:999px; width:max-content; }
    .mg-pill.cattivo { background:var(--mg-crit-bg); color:var(--mg-crit); }
    .mg-pill.attenzione { background:var(--mg-warn-bg); color:var(--mg-warn-ink); }
    .mg-pill.buono { background:var(--mg-ok-bg); color:var(--mg-ok); }
    .mg-pill.neutro { background:var(--mg-azzurro-tenue); color:var(--mg-teal-testo); }
    .mg-pill .ico { width:13px; height:13px; border-radius:50%; border:1.6px solid currentColor;
        display:inline-flex; align-items:center; justify-content:center; font-size:9px; line-height:1; flex:none; }
    .mg-k-foot { margin-top:auto; display:flex; flex-wrap:wrap; justify-content:space-between;
        align-items:center; gap:4px 8px; }
    .mg-k-owner { font-size:12px; line-height:16px; color:var(--mg-mut); }
    .mg-k-code { font-size:11px; line-height:16px; font-weight:700; letter-spacing:.06em; color:var(--mg-mut); }
    .mg-hk-spark { width:100%; height:34px; display:block; overflow:visible; }
    /* mini-indicatori delle viste Versioni e Catalogo (stessa grammatica, senza riquadro) */
    .mg-hk { position:relative; display:flex; flex-direction:column; gap:5px; }
    .mg-hk.vsep { border-left:1px solid var(--mg-line); padding-left:16px; }
    .mg-hk-top { display:flex; align-items:center; justify-content:space-between; gap:8px; }
    .mg-hk-label { font-size:12px; line-height:16px; font-weight:700; letter-spacing:.06em;
        text-transform:uppercase; color:var(--mg-mut); }
    .mg-hk-val { display:flex; align-items:baseline; gap:4px; font-weight:800; font-size:36px; line-height:1;
        letter-spacing:-.03em; color:var(--mg-ink); font-variant-numeric:tabular-nums; white-space:nowrap; }
    .mg-hk-val small { font-size:16px; font-weight:600; letter-spacing:0; color:var(--mg-ink); }
    .mg-hk-val.nd { font-size:20px; color:var(--mg-mut); }
    .mg-hk-sub { font-size:13px; line-height:18px; color:var(--mg-mut); }
    .mg-hk-sub b { color:var(--mg-ink); font-weight:700; }
    .mg-hk-badges { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }

    /* page_link disteso e invisibile sul riquadro (drill L3 -> L30) */
    div[class*="st-key-kpi_"] [data-testid="stElementContainer"]:has([data-testid="stPageLink"]) {
        position:absolute; inset:0; z-index:6; margin:0; width:auto !important; height:auto !important; }
    div[class*="st-key-kpi_"] [data-testid="stPageLink"],
    div[class*="st-key-kpi_"] [data-testid="stPageLink"] a {
        position:absolute; inset:0; margin:0; padding:0; width:auto !important; height:auto !important; }
    div[class*="st-key-kpi_"] [data-testid="stPageLink"] a { opacity:0; border-radius:12px; }
    div[class*="st-key-kpi_"] [data-testid="stPageLink"] a:focus-visible { opacity:1;
        outline:2px solid var(--mg-teal); outline-offset:2px; background:transparent; }
    div[class*="st-key-kpi_"]:hover .mg-k { border-color:var(--mg-azzurro); }

    /* === Stato vuoto (società senza report) === */
    .mg-vuoto { display:flex; gap:18px; align-items:center; padding:22px 24px; margin-top:12px;
        background:#fff; border:1px dashed var(--mg-line-ph, #b9c6e2); border-radius:var(--mg-r-card, 12px); }
    .mg-vuoto svg { width:52px; height:52px; padding:12px; border-radius:14px; flex:none; box-sizing:border-box;
        background:var(--mg-azzurro-tenue); color:var(--mg-blu); }
    .mg-vuoto-t { font-family:var(--mg-font-t); font-size:17px; line-height:22px; font-weight:600;
        color:var(--mg-blu); }
    .mg-vuoto-d { font-size:14px; line-height:20px; color:var(--mg-mut); margin-top:2px; }

    /* === Barre orizzontali con delta === */
    .mg-bars { display:flex; flex-direction:column; gap:11px; }
    .mg-bar-top { display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-bottom:5px; }
    .mg-bar-name { font-size:13px; color:var(--mg-ink); font-weight:600; }
    .mg-bar-right { display:flex; align-items:baseline; gap:7px; }
    .mg-bar-val { font-size:14px; font-weight:700; color:var(--mg-ink); font-variant-numeric:tabular-nums; }
    .mg-bar-track { height:8px; background:var(--mg-track); border-radius:999px; overflow:hidden; }
    .mg-bar-fill { height:100%; border-radius:999px; background:var(--c,#5a6389); }
    .mg-bar-delta { font-size:12px; font-weight:700; white-space:nowrap; }

    /* === Pannelli e tabelle: card su bordo line, senza ombra === */
    div[class*="st-key-panel_"] { background:#fff !important; border:1px solid var(--mg-line) !important;
        border-radius:var(--mg-r-card, 12px) !important; padding:16px 18px 14px !important;
        box-shadow:var(--mg-sh, none) !important; }
    .mg-panel-title { font-family: var(--mg-font-t); font-size:17px; line-height:22px; font-weight:600;
        color:var(--mg-titolo, var(--mg-blu)); margin:0 0 12px; }
    [data-testid="stDataFrame"] { border:1px solid var(--mg-line) !important; border-radius:12px; overflow:hidden; }
    [data-testid="stCaptionContainer"] { color:var(--mg-mut) !important; font-size:12px !important; }
    [data-testid="stAlert"] { border-radius:12px; border:1px solid var(--mg-line); }
    hr { border-color: var(--mg-line) !important; opacity:1 !important; }

    /* === Widget: segmentati a pillola, bottoni, select === */
    [data-testid="stButtonGroup"] { background:var(--mg-track); border-radius:999px; padding:3px;
        width:max-content; gap:2px; }
    [data-testid="stButtonGroup"] button { border:none !important; background:transparent !important;
        border-radius:999px !important; padding:5px 14px !important; }
    [data-testid="stButtonGroup"] button p { font-weight:700 !important; font-size:13px !important;
        color:var(--mg-mut) !important; }
    [data-testid="stButtonGroup"] button[aria-checked="true"],
    [data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
    [data-testid="stButtonGroup"] button[aria-pressed="true"] { background:#fff !important;
        box-shadow:0 0 0 1px var(--mg-line) inset; }
    [data-testid="stButtonGroup"] button[aria-checked="true"] p,
    [data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p,
    [data-testid="stButtonGroup"] button[aria-pressed="true"] p { color:var(--mg-blu) !important; }
    /* primario: teal con testo bianco a 18px bold (il teal regge il bianco solo così) */
    .stButton > button[kind="primary"] { background:var(--mg-teal) !important; border:none !important;
        border-radius:var(--mg-btn-r, 12px) !important; box-shadow:var(--mg-btn-sh, none); }
    .stButton > button[kind="primary"] p { font-size:var(--mg-btn-fs, 18px) !important; font-weight:700 !important; color:#fff !important; }
    .stButton > button[kind="primary"]:hover { background:var(--mg-teal-testo) !important; }
    .stButton > button[kind="secondary"] { border-radius:12px !important; border:2px solid var(--mg-blu) !important;
        background:transparent !important; }
    .stButton > button[kind="secondary"] p { font-weight:700 !important; color:var(--mg-blu) !important; }
    .stButton > button[kind="secondary"]:hover { background:var(--mg-azzurro-tenue) !important; }
    [data-testid="stDownloadButton"] button { border-radius:12px !important; border:2px solid var(--mg-blu) !important; }
    [data-testid="stDownloadButton"] button p { font-weight:700 !important; color:var(--mg-blu) !important; }
    [data-baseweb="select"] > div { border-radius:6px !important; border-color:var(--mg-line) !important; }
    [data-baseweb="tag"] { border-radius:6px !important; background:var(--mg-azzurro-tenue) !important; }
    [data-baseweb="tag"] span { color:var(--mg-blu) !important; }

    /* i blocchi markdown che portano solo <style> non devono occupare spazio
       (ognuno aggiungeva 16 px di gap sopra la testata) */
    [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > style:only-child) {
        display:none !important; }

    /* === Sidebar === */
    [data-testid="stSidebarHeader"] { height:auto !important; min-height:0 !important; padding:8px 0 0 !important; }
    [data-testid="stSidebarNav"] a span { white-space:normal !important; }
    [data-testid="stSidebar"] { background:#ffffff; border-right:1px solid var(--mg-line); }
    [data-testid="stSidebarNav"] a { border-radius:6px; margin:1px 8px; }
    [data-testid="stSidebarNav"] a:hover { background:var(--mg-surface); }
    [data-testid="stSidebarNav"] a[aria-current="page"] { background:var(--mg-azzurro-tenue) !important;
        box-shadow: inset 3px 0 0 var(--mg-blu); }
    [data-testid="stSidebarNav"] a[aria-current="page"] span { color:var(--mg-blu) !important;
        font-weight:700 !important; }
    [data-testid="stSidebarNav"] header { font-weight:700; letter-spacing:.06em; font-size:11px;
        text-transform:uppercase; color:var(--mg-mut); }
    .mg-side-label { font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
        color:var(--mg-mut); margin:14px 0 4px; }

    /* === Form di login: card su bordo line, senza ombra === */
    [data-testid="stForm"] { max-width:420px; margin:.4rem auto 0; padding:1.5rem 1.8rem 1.2rem;
        background:#fff; border:1px solid var(--mg-line); border-radius:12px; }
    [data-testid="stForm"] .stButton > button,
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button { width:100%; min-height:42px;
        background:var(--mg-teal) !important; border:none !important;
        border-radius:var(--mg-btn-r, 12px) !important; box-shadow:var(--mg-btn-sh, none); }
    [data-testid="stForm"] .stButton > button p,
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button p { color:#fff !important;
        font-size:var(--mg-btn-fs, 18px) !important; font-weight:700 !important; }

    @media (max-width: 760px) {
        .block-container { padding-left:.9rem !important; padding-right:.9rem !important; }
        .mg-k-val .n { font-size:36px; }
        .mg-top-r { align-items:flex-start; margin-left:0; }
    }
</style>
"""


def apply_base(logo: bool = True) -> None:
    """CSS globale (+ logo Migliora in sidebar se logo=True). Chiamare sempre,
    prima del login; il tema della pagina si applica dopo (applica_tema)."""
    st.markdown(MIGLIORA_CSS, unsafe_allow_html=True)
    if logo and LOGO_PATH.exists():
        icona = str(ICONA_PATH) if ICONA_PATH.exists() else None
        try:
            st.logo(str(LOGO_PATH), size="large", icon_image=icona)
        except (AttributeError, TypeError):
            pass


# =============================================================================
# Tema Altair (stesso linguaggio dei componenti HTML)
# =============================================================================

def _tema_altair() -> dict:
    return {"config": {
        "font": "Manrope, Segoe UI, sans-serif",
        "view": {"stroke": "transparent"},
        "axis": {"labelColor": INK_MUTED, "titleColor": INK_MUTED, "gridColor": "#e9eef7",
                 "domainColor": LINE, "tickColor": LINE, "labelFontSize": 12,
                 "titleFontSize": 12, "titleFontWeight": 700, "labelFont": "Manrope"},
        "legend": {"labelColor": INK_MUTED, "titleColor": INK, "labelFontSize": 12,
                   "titleFontSize": 12, "orient": "top"},
        "bar": {"cornerRadiusEnd": 3},
        "line": {"strokeWidth": 2.4},
        "range": {"category": CATEGORICHE},
    }}


def enable_altair_theme() -> None:
    """Tema unico per i grafici (API nuova di Altair 5.5+/6, fallback vecchia)."""
    try:
        alt.theme.register("migliora", enable=True)(_tema_altair)
        return
    except Exception:
        pass
    try:
        alt.themes.register("migliora", _tema_altair)
        alt.themes.enable("migliora")
    except Exception:
        pass


# Numeri degli assi in italiano via labelExpr (Streamlit filtra le locale
# Vega: vedi Gas_Monitor/branding.altair_it, stesso problema già pagato).
_LABEL_NUM_IT = ("replace(replace(replace(format(datum.value, ','), ',', '\\u00a7'), "
                 "'.', ','), '\\u00a7', '.')")


def altair_it(chart, **kwargs):
    """st.altair_chart con i numeri degli assi in formato italiano.
    Usare SEMPRE questa al posto di st.altair_chart."""
    kwargs.setdefault("width", "stretch")
    spec = chart.to_dict()
    cfg = spec.setdefault("config", {})
    cfg.setdefault("axisQuantitative", {}).setdefault("labelExpr", _LABEL_NUM_IT)
    return st.vega_lite_chart(spec, **kwargs)


@functools.lru_cache(maxsize=4)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else ""


def logo_bianco_html() -> str:
    """Marchio Migliora bianco per la testata blu (140 px, larghezza minima a
    schermo del brand book); ripiega sul nome in testo."""
    b64 = _b64(LOGO_BIANCO_PATH)
    if not b64:
        return "<span class='mg-top-brand'>migliora</span>"
    return f"<img class='mg-top-logo' src='data:image/png;base64,{b64}' alt='Migliora'/>"


# =============================================================================
# Temi del portale NeWatt: uno per il gruppo e uno per società
# =============================================================================
# Colori e font letti dai siti ufficiali (newatt.it, energylifegate.it,
# gazelitalia.it, 24/11/2026) e dal brand book Migliora. Ogni tema ridefinisce
# le variabili CSS del design system: la struttura dei componenti non cambia.
# `logo` = file in assets/ (None = nome in testo finché non arriva il file).
# Design system NeWatt: lo stesso dello strumento CTE (G_Modulistica\CTE# Strumento_CTE\srcpp.css, grafica del 23/11/2026): blu #0000FF, testo blu
# #0000D6, blu tenue #F1F1FF, linee #E2E5EE, fondo #F4F6FB, inchiostro
# #14162B / #434861 / #656B82, Poppins, schede raggio 18 con ombra morbida,
# bottoni a pillola. Vale per tutto il portale; le società tengono dentro la
# pagina il loro logo a colori e il loro colore d'accento (testata e fasce).
_NEWATT = {"titolo": "#14162B", "surface": "#F4F6FB", "ink": "#14162B", "mut": "#434861",
           "line": "#E2E5EE", "azzurro": "#C5C5FF", "azzurro-tenue": "#F1F1FF",
           "r-card": "18px", "sh": "0 1px 2px rgba(20,22,43,.05),0 6px 20px rgba(20,22,43,.05)",
           "sh-k": "0 1px 2px rgba(20,22,43,.05)", "btn-r": "999px", "btn-fs": "15px",
           "btn-sh": "0 2px 8px rgba(0,0,255,.24)", "top-bg": "#FFFFFF", "top-ink": "#14162B",
           "top-contorno": "1px solid #E2E5EE", "chip-bg": "#F4F6FB", "chip-bd": "#E2E5EE"}
_POPPINS = "'Poppins', 'Segoe UI', system-ui, -apple-system, Roboto, Arial, sans-serif"
TEMI = {
    "newatt": dict(
        nome="NeWatt", claim="Il tuo partner strategico nel mondo dell’energia.",
        logo=None, parola="", logo_h="0px", fonts="family=Poppins:wght@400;500;600;700",
        font=_POPPINS, font_t=_POPPINS,
        v={**_NEWATT, "blu": "#0000FF", "blu-scuro": "#0000C4", "teal": "#0000FF",
           "teal-testo": "#0000D6", "top-accento": "6px solid #0000FF",
           "amb0": "#0000FF", "amb1": "#0000C4", "amb2": "#14162B", "amb3": "#434861"}),
    "lifegate": dict(
        nome="LifeGate Energy", claim="Rinnovabili dal primo kWh.",
        logo="Logo_LifeGate.png", parola="LIFEGATE | ENERGY", logo_h="30px",   # da energylifegate.it
        fonts="family=Poppins:wght@400;500;600;700", font=_POPPINS, font_t=_POPPINS,
        v={**_NEWATT, "blu": "#006454", "blu-scuro": "#004236", "teal": "#006454",
           "teal-testo": "#006454", "azzurro-tenue": "#E6F2EE", "top-ink": "#006454",
           "top-accento": "6px solid #006454",
           "amb0": "#005345", "amb1": "#008354", "amb2": "#3E5B52", "amb3": "#004236"}),
    "gazel": dict(
        nome="Gazel", claim="L’energia non è uguale per tutti",
        logo="Logo_Gazel.png", parola="GAZEL", logo_h="58px",
        fonts="family=Poppins:wght@400;500;600;700", font=_POPPINS, font_t=_POPPINS,
        v={**_NEWATT, "blu": "#354697", "blu-scuro": "#26346F", "teal": "#354697",
           "teal-testo": "#354697", "azzurro-tenue": "#FFF3D6", "top-ink": "#354697",
           "top-accento": "6px solid #FFAE00",
           "amb0": "#354697", "amb1": "#0C71C3", "amb2": "#1E2654", "amb3": "#26346F"}),
    # BP Migliora dentro il portale: palette Migliora, testata blu scuro con
    # logo bianco (chip semitrasparenti, leggibili sul fondo scuro)
    "migliora": dict(
        nome="Migliora", claim=CLAIM, logo="Logo_Migliora_marchio_bianco.png", parola="migliora",
        logo_h="40px", fonts="", font="", font_t="",
        v={**_NEWATT, "blu": "#28326F", "blu-scuro": "#1C2454", "teal": "#28326F",
           "teal-testo": "#00738A", "azzurro-tenue": "#E3F0FB", "top-bg": "#28326f",
           "top-ink": "#FFFFFF", "top-accento": "0 solid transparent",
           "top-contorno": "0 solid transparent",
           "chip-bg": "rgba(255,255,255,.10)", "chip-bd": "rgba(255,255,255,.30)",
           "amb0": "#28326F", "amb1": "#00738A", "amb2": "#5A6389", "amb3": "#1C2454"}),
    # Migliora come società del portale: design NeWatt, logo a colori, accento blu Migliora
    "migliora_kpi": dict(
        nome="Migliora", claim=CLAIM, logo="Logo_Migliora_marchio.png", parola="migliora",
        logo_h="40px", fonts="family=Poppins:wght@400;500;600;700", font=_POPPINS, font_t=_POPPINS,
        v={**_NEWATT, "blu": "#28326F", "blu-scuro": "#1C2454", "teal": "#28326F",
           "teal-testo": "#00738A", "azzurro-tenue": "#E3F0FB", "top-ink": "#28326F",
           "top-accento": "6px solid #009EBD",
           "amb0": "#28326F", "amb1": "#00738A", "amb2": "#5A6389", "amb3": "#1C2454"}),
}


LOGO_NEWATT_PATH = APP_DIR / "assets" / "Logo_NeWatt_bianco.png"   # dallo strumento CTE
BARRA_H = 58


def barra_portale(modulo: str = "Portale KPI") -> None:
    """Barra superiore del portale come nello strumento CTE: blu #0000FF a
    tutta larghezza, logo NeWatt bianco, separatore e nome del modulo. È
    l'intestazione di Streamlit ridisegnata (resta sopra la barra laterale)."""
    b64 = _b64(LOGO_NEWATT_PATH)
    logo = (f"url('data:image/png;base64,{b64}') no-repeat var(--mg-barra-x, 20px) center / auto 28px"
            if b64 else "none")
    st.markdown(f"""<style>
    [data-testid="stHeader"] {{ position:fixed; top:0; left:0; right:0; width:100%; height:{BARRA_H}px;
        z-index:999992; background:#0000FF; background:{logo}, #0000FF;
        box-shadow:0 1px 0 rgba(0,0,0,.08), 0 4px 18px rgba(0,0,255,.18); }}
    [data-testid="stHeader"]::before {{ content:"{modulo}"; position:absolute; top:50%;
        left:calc(var(--mg-barra-x, 20px) + 122px); transform:translateY(-50%); color:#fff;
        font:700 1.02rem/1 'Poppins','Segoe UI',system-ui,sans-serif; letter-spacing:.02em;
        padding:5px 0 5px 14px; border-left:1px solid rgba(255,255,255,.35); white-space:nowrap; }}
    [data-testid="stHeader"]:has([data-testid="stExpandSidebarButton"]) {{ --mg-barra-x: 64px; }}
    [data-testid="stHeader"] button, [data-testid="stHeader"] a, [data-testid="stHeader"] span,
    [data-testid="stHeader"] svg {{ color:#fff !important; fill:currentColor; }}
    [data-testid="stHeader"] [data-testid="stToolbar"] {{ top:50%; transform:translateY(-50%); }}
    [data-testid="stSidebar"] {{ top:{BARRA_H}px !important; height:calc(100vh - {BARRA_H}px) !important; }}
    [data-testid="stSidebar"] > div {{ height:calc(100vh - {BARRA_H}px) !important; }}
    .block-container {{ padding-top:calc({BARRA_H}px + .9rem) !important; }}
    </style>""", unsafe_allow_html=True)


def applica_tema(codice: str) -> None:
    """Ridefinisce le variabili del design system con il tema indicato."""
    tema = TEMI[codice]
    var = {"--mg-" + k: v for k, v in tema["v"].items() if not k.startswith("amb")}
    var.update({"--" + k: v for k, v in tema["v"].items() if k.startswith("amb")})
    if tema["font"]:
        var["--mg-font"], var["--mg-font-t"] = tema["font"], tema["font_t"]
    var["--mg-logo-h"] = tema["logo_h"]
    font = (f"@import url('https://fonts.googleapis.com/css2?{tema['fonts']}&display=swap');"
            if tema["fonts"] else "")
    corpo = "; ".join(f"{k}:{v}" for k, v in var.items())
    st.markdown(f"<style>{font} :root {{ {corpo} }}</style>", unsafe_allow_html=True)


def logo_tema_html(codice: str) -> str:
    """Logo del tema per la testata; senza file, il nome in testo nel font
    del marchio (sostituibile appena arriva il logo ufficiale)."""
    tema = TEMI[codice]
    b64 = _b64(APP_DIR / "assets" / tema["logo"]) if tema["logo"] else ""
    if b64:
        return (f"<img class='mg-top-logo' src='data:image/png;base64,{b64}' "
                f"alt='{escape(tema['nome'])}'/>")
    if not tema["parola"]:          # NeWatt: il logo sta già nella barra superiore
        return ""
    return f"<span class='mg-top-word'>{escape(tema['parola'])}</span>"


# Loghi delle società del gruppo a colori (riga sotto il titolo del login):
# file in assets/, altezza scelta a occhio perché pesino uguale (LifeGate è
# una scritta lunga e bassa, Gazel ha la mascotte e il claim).
LOGHI_SOCIETA = [("Logo_LifeGate.png", "LifeGate Energy", 20),
                 ("Logo_Gazel.png", "Gazel", 46),
                 ("Logo_Migliora_marchio.png", "Migliora", 28)]


def loghi_societa_html() -> str:
    pezzi = []
    for file, nome, altezza in LOGHI_SOCIETA:
        b64 = _b64(APP_DIR / "assets" / file)
        pezzi.append(f"<img src='data:image/png;base64,{b64}' alt='{escape(nome)}' title='{escape(nome)}' "
                     f"style='height:{altezza}px;width:auto;display:block'/>" if b64
                     else f"<span style='font-weight:600'>{escape(nome)}</span>")
    return ("<div style='display:flex;align-items:center;justify-content:center;gap:22px;"
            "flex-wrap:wrap;margin-top:12px'>" + "".join(pezzi) + "</div>")


def render_login_hero(tema: str = "newatt") -> None:
    """Pre-login: marchio del tema su una fascia del suo colore + titolo
    (il form lo rende auth)."""
    tm = TEMI[tema]
    b64 = _b64(LOGO_NEWATT_PATH)
    logo = (f"<img src='data:image/png;base64,{b64}' alt='NeWatt' style='height:44px;width:auto;"
            f"display:block;margin:0 auto'/>" if b64 else logo_tema_html(tema))
    st.markdown(
        "<div style='max-width:420px;margin:0 auto;border-radius:18px;overflow:hidden;"
        "border:1px solid var(--mg-line);box-shadow:var(--mg-sh, none)'>"
        "<div style='background:#0000FF;color:#fff;padding:24px 24px 20px;text-align:center'>"
        f"{logo}"
        f"<div style='font-size:13px;margin-top:8px;opacity:.92'>{escape(tm['claim'])}</div></div>"
        "<div style='background:#fff;padding:16px 24px 18px;text-align:center'>"
        "<div style='font-family:var(--mg-font-t);font-size:20px;line-height:26px;font-weight:600;"
        "color:var(--mg-blu)'>Portale KPI del gruppo</div>"
        f"{loghi_societa_html()}</div></div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# Componenti HTML
# =============================================================================

def testata(titolo: str, aggiornato: str, chips_html: str, tema: str = "migliora") -> str:
    """Testata dell'handoff: logo del tema, titolo e claim sotto il logo, a
    destra «Aggiornato al …» e lo stato dei dati."""
    agg = f"<span class='mg-top-agg'>{escape(aggiornato)}</span>" if aggiornato else ""
    chips = f"<span class='mg-chips'>{chips_html}</span>" if chips_html else ""
    return (f"<div class='mg-top'><div class='mg-top-l'>{logo_tema_html(tema)}"
            f"<div class='mg-top-txt'><span class='mg-top-tit'>{escape(titolo)}</span>"
            f"<span class='mg-top-claim'>{escape(TEMI[tema]['claim'])}</span></div></div>"
            f"<div class='mg-top-r'>{agg}{chips}</div></div>")


def slicer(etichetta: str, valore: str) -> str:
    """Slicer in sola lettura (valore che arriva dai filtri globali)."""
    return (f"<div class='mg-slicer'><span class='mg-slicer-l'>{escape(etichetta)}</span>"
            f"<span class='mg-slicer-v'>{escape(valore)}</span></div>")


def contatori(conteggi: dict, ordine: list | None = None) -> str:
    """Chip «{stato} · n» della barra filtri, nell'ordine dell'handoff (o in
    quello indicato: [(stato, etichetta), ...])."""
    # solo gli stati presenti: con cinque chip fissi la riga andava a capo
    pezzi = [f"<span class='c {s}'><i></i>{escape(label)} · {conteggi.get(s, 0)}</span>"
             for s, label in (ordine or ORDINE_CONTATORI) if conteggi.get(s, 0)]
    return f"<div class='mg-cnt'>{''.join(pezzi)}</div>"


# Icone degli ambiti: linea singola del brand book (griglia 24, tratto 2 px,
# terminali arrotondati), bianche sulla colonna colorata. Niente simboli che il
# brand book vieta (strette di mano, scudi, lampadine come cliché).
ICONE_AMBITO = {
    # moneta con l'euro: conto economico, costi, risultato
    "euro": "<circle cx='12' cy='12' r='9'/><path d='M15.2 8.6a4.3 4.3 0 1 0 0 6.8'/>"
            "<path d='M7.5 10.8h5.5M7.5 13.2h5.5'/>",
    # crescita: vendite, acquisizione, canali
    "crescita": "<path d='M3 17l6-6 4 4 8-8'/><path d='M15 7h6v6'/>",
    # casa: il Cliente e la sua casa al centro (brand book, «Vicinanza»)
    "casa": "<path d='M3.5 11L12 4l8.5 7'/><path d='M5.5 9.5V20h13V9.5'/><path d='M10 20v-5.5h4V20'/>",
    # persone: portafoglio clienti, struttura e FTE
    "persone": "<circle cx='9' cy='8' r='3.2'/><path d='M3 20c0-3.3 2.7-5.6 6-5.6s6 2.3 6 5.6'/>"
               "<path d='M16 4.9a3.2 3.2 0 0 1 0 6.2'/><path d='M21 20c0-2.6-1.6-4.6-4-5.3'/>",
    # spunta: qualità del servizio
    "qualita": "<circle cx='12' cy='12' r='9'/><path d='M8 12.3l2.7 2.7L16.2 9.5'/>",
    # più: servizi aggiuntivi (VAS)
    "servizi": "<rect x='3.5' y='3.5' width='17' height='17' rx='4'/><path d='M12 8v8M8 12h8'/>",
    # griglia: ripiego
    "griglia": "<rect x='4' y='4' width='6.5' height='6.5' rx='1.5'/><rect x='13.5' y='4' width='6.5' "
               "height='6.5' rx='1.5'/><rect x='4' y='13.5' width='6.5' height='6.5' rx='1.5'/>"
               "<rect x='13.5' y='13.5' width='6.5' height='6.5' rx='1.5'/>",
}
# Parola chiave nel nome dell'ambito -> icona (vince la prima che compare).
_PAROLE_ICONA = [("client", "casa"), ("qualit", "qualita"), ("struttura", "persone"),
                 ("portafoglio", "persone"), ("economi", "euro"), ("finanz", "euro"),
                 ("ricavi", "euro"), ("cost", "euro"), ("risultato", "euro"), ("vas", "servizi"),
                 ("commercial", "crescita"), ("acquisizione", "crescita"), ("canale", "crescita"),
                 ("vendit", "crescita")]


def icona_ambito(nome: str) -> str:
    chiave = next((v for k, v in _PAROLE_ICONA if k in nome.lower()), "griglia")
    return (f"<svg class='mg-amb-ico' viewBox='0 0 24 24' fill='none' stroke='#ffffff' "
            f"stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
            f"{ICONE_AMBITO[chiave]}</svg>")


def testata_ambito(nome: str, n_kpi: int) -> str:
    """Colonna sinistra della fascia: icona, titolo dell'ambito e numero di KPI."""
    return (f"{icona_ambito(nome)}<span class='mg-amb-title'>{escape(nome)}</span>"
            f"<span class='mg-amb-cnt'>{n_kpi} KPI</span>")


# Commodity: icone dell'handoff (griglia 24, tratto blu 2px arrotondato):
# lampadina gialla per l'energia elettrica, fiamma azzurra per il gas. Sempre
# con il nome accanto: il colore non porta da solo l'informazione.
ICONA_COMMODITY = {
    "Power": ("<svg class='mg-com-ico' viewBox='0 0 24 24' fill='none' stroke='#28326f' "
              "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
              "<path d='M9 18h6'/><path d='M10 22h4'/>"
              "<path d='M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z' "
              "fill='#f5c400'/></svg>"),
    "Gas": ("<svg class='mg-com-ico' viewBox='0 0 24 24' fill='none' stroke='#28326f' "
            "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
            "<path d='M12 22c4 0 7-2.8 7-6.8 0-3.6-2.4-6-4.3-8.4-.5 1.9-1.6 3.2-2.9 3.7"
            "C12.4 7 11 4.3 8.7 2 8.7 6 5 8.6 5 15.2 5 19.2 8 22 12 22z' fill='#97c7ec'/></svg>"),
}
NOME_COMMODITY = {"Power": "Energia elettrica", "Gas": "Gas naturale"}


def icona_commodity(commodity: str) -> str:
    return ICONA_COMMODITY.get(commodity, "")


def dettaglio_commodity(valori: dict) -> str:
    """Righe del dettaglio per commodity dentro il riquadro: icona + nome a
    sinistra, valore a destra (più piccolo del numero principale)."""
    righe = [f"<div class='mg-split-r'><span class='l'>{icona_commodity(c)}"
             f"<span>{escape(NOME_COMMODITY.get(c, c))}</span></span><b>{escape(v)}</b></div>"
             for c, v in valori.items()]
    return f"<div class='mg-split'>{''.join(righe)}</div>" if righe else ""


def riquadro_kpi(vm: dict) -> str:
    """Riquadro KPI dell'handoff da un modello già calcolato (ui._modello):
    nome + chip di stato, cifra con alone (o «In attesa dati»), sparkline,
    dettaglio per commodity, Rif., note, owner e codice."""
    st_ = vm["stato"]
    info = STATI_KPI[st_]
    label = vm.get("label_stato") or info["label"]
    corpo = [f"<div class='mg-k-head'><span class='mg-k-name'>{escape(vm['nome'])}</span>"
             f"<span class='mg-st {st_}'><i></i>{escape(label)}</span></div>"]
    if vm.get("valore") is not None:
        glow = (f"<span class='glow' aria-hidden='true' style='--glow:{info['glow']}'></span>"
                if info["glow"] else "")
        unita = f"<span class='u'>{escape(vm['unita'])}</span>" if vm.get("unita") else ""
        nd = " nd" if vm.get("nd") else ""
        cifra = (f"<div class='mg-k-val{nd}'>{glow}<span class='n'>{escape(vm['valore'])}</span>"
                 f"{unita}</div>")
        if vm.get("affianco"):      # seconda cifra a destra (es. churn progressivo nei punti attivi)
            etichetta, testo = vm["affianco"]
            cifra = ("<div style='display:flex;align-items:center;justify-content:space-between;"
                     "gap:12px;flex-wrap:wrap'>" + cifra +
                     "<div class='mg-k-side' style='text-align:right;padding:6px 0;margin-left:auto'>"
                     "<div style='font-size:10.5px;font-weight:700;letter-spacing:.06em;"
                     f"text-transform:uppercase;color:var(--mg-mut)'>{escape(etichetta)}</div>"
                     "<div style='font-size:20px;line-height:1.15;font-weight:800;white-space:nowrap;"
                     f"color:var(--mg-ink)'>{escape(testo)}</div></div></div>")
        corpo.append(cifra)
    else:
        corpo.append("<div class='mg-k-pend'>In attesa dati</div>")
    if vm.get("spark"):
        corpo.append(vm["spark"])
    corpo.append(dettaglio_commodity(vm.get("split") or {}))
    if vm.get("delta"):
        corpo.append(f"<div class='mg-k-note'><span class='mg-delta {vm['delta'][1]}'>"
                     f"{escape(vm['delta'][0])}</span></div>")
    if vm.get("pill"):
        corpo.append(f"<span class='mg-pill {vm['pill'][1]}'>{escape(vm['pill'][0])}</span>")
    corpo.append(f"<span class='mg-k-rif'>Rif. <b>{escape(vm.get('rif') or 'da definire')}</b></span>")
    for nota in vm.get("note") or []:
        corpo.append(f"<span class='mg-k-note'>{escape(nota)}</span>")
    corpo.append(f"<div class='mg-k-foot'><span class='mg-k-owner'>{escape(vm.get('owner') or '')}</span>"
                 f"<span class='mg-k-code'>{escape(vm.get('codice') or '—')}</span></div>")
    classe = "mg-k pend" if st_ == "pend" else "mg-k"
    return (f"<div class='{classe}' title='{escape(vm.get('definizione') or '', quote=True)}'>"
            f"{''.join(corpo)}</div>")


def stato_vuoto(titolo: str, testo: str) -> str:
    """Pagina senza dati: riquadro tratteggiato con icona, titolo e spiegazione."""
    return ("<div class='mg-vuoto'><svg viewBox='0 0 24 24' fill='none' stroke='currentColor' "
            "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
            "<path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><path d='M14 3v5h5'/>"
            "<path d='M12 17v-6M9.5 13.5 12 11l2.5 2.5'/></svg>"
            f"<div><div class='mg-vuoto-t'>{escape(titolo)}</div>"
            f"<div class='mg-vuoto-d'>{escape(testo)}</div></div></div>")


def legenda(items: list[tuple[str, str, str]]) -> str:
    """Legenda compatta: (stile, colore, testo) con stile solid|dash|box."""
    pezzi = []
    for stile, colore, testo in items:
        if stile == "box":
            marca = (f"<i style='display:inline-block;width:12px;height:10px;border-radius:2px;"
                     f"background:{colore};margin-right:6px;vertical-align:middle'></i>")
        else:
            tratto = "dashed" if stile == "dash" else "solid"
            marca = (f"<i style='display:inline-block;width:20px;border-top:3px {tratto} {colore};"
                     f"margin-right:6px;vertical-align:middle'></i>")
        pezzi.append(f"<span style='margin-right:14px'>{marca}{escape(testo)}</span>")
    return (f"<div style='font-size:12px;color:{INK_MUTED};margin:0 0 8px;display:flex;"
            f"flex-wrap:wrap;gap:2px 0'>{''.join(pezzi)}</div>")


def sparkline(serie_a: list, serie_b: list | None = None, altezza: int = 34) -> str:
    """Sparkline: area azzurra + linea blu + punto finale; la versione di
    confronto è teal tratteggiata."""
    serie_a = list(serie_a or [])
    while serie_a and serie_a[0] is None:        # niente spazio vuoto prima del primo dato
        serie_a.pop(0)
    valori = [v for v in serie_a + list(serie_b or []) if v is not None]
    if len([v for v in serie_a if v is not None]) < 2:
        return ""
    w, h, pad = 150.0, float(altezza) - 6, 3.0
    lo, hi = min(valori), max(valori)
    span = (hi - lo) or 1.0

    def punti(serie):
        n = len(serie)
        return [(i * w / (n - 1), pad + (1 - (v - lo) / span) * (h - pad))
                for i, v in enumerate(serie) if v is not None]

    pa = punti(serie_a)
    linea = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pa)
    area = f"{linea}L{pa[-1][0]:.1f} {h:.1f}L{pa[0][0]:.1f} {h:.1f}Z"
    fine = pa[-1]
    b = ""
    if serie_b and len([v for v in serie_b if v is not None]) >= 2:
        pb = punti(serie_b)
        b = (f"<path d='M{'L'.join(f'{x:.1f} {y:.1f}' for x, y in pb)}' fill='none' "
             f"stroke='{C_CONFRONTO}' stroke-width='2' stroke-dasharray='5 3'/>")
    return (f"<svg class='mg-hk-spark' viewBox='0 0 {w:.0f} {altezza}' preserveAspectRatio='none'>"
            f"<path d='{area}' fill='rgba(151,199,236,.35)'/>"
            f"<path d='{linea}' fill='none' stroke='{C_BP}' stroke-width='2.2' "
            f"stroke-linejoin='round' stroke-linecap='round'/>"
            f"<circle cx='{fine[0]:.1f}' cy='{fine[1]:.1f}' r='2.6' fill='{C_BP}'/>{b}</svg>")


# Colori del TESTO per tono (4,5:1 su bianco): il giallo e l'azzurro dei
# riempimenti sulle scritte sarebbero illeggibili — qui si usa l'inchiostro.
TONO_TESTO = {"buono": "#1f7a4d", "attenzione": "#8a6a00", "cattivo": C_CATTIVO,
              "neutro": INK_MUTED}


def barre(righe: list[dict], colore: str = C_BP) -> str:
    """Barre orizzontali con valore e delta (viste 30 secondi).
    Ogni riga: {nome, valore, quota 0-1, delta?, tono?, colore?}."""
    out = []
    for r in righe:
        quota = max(0.0, min(1.0, float(r.get("quota") or 0.0))) * 100
        delta = (f"<span class='mg-bar-delta' style='color:"
                 f"{TONO_TESTO.get(r.get('tono', 'neutro'), INK_MUTED)}'>"
                 f"{escape(str(r['delta']))}</span>") if r.get("delta") else ""
        out.append(
            f"<div><div class='mg-bar-top'><span class='mg-bar-name'>{escape(str(r['nome']))}</span>"
            f"<span class='mg-bar-right'><span class='mg-bar-val'>{escape(str(r['valore']))}</span>"
            f"{delta}</span></div>"
            f"<div class='mg-bar-track'><div class='mg-bar-fill' style='width:{quota:.1f}%;"
            f"--c:{r.get('colore', colore)}'></div></div></div>")
    return f"<div class='mg-bars'>{''.join(out)}</div>"


def pannello_in_arrivo(icona: str, titolo: str, descrizione: str,
                       funzioni: list[tuple[str, str]]) -> None:
    feats = "".join(
        f"<div style='background:#fff;border:1px solid {LINE};border-radius:12px;padding:12px 14px;"
        f"font-size:13px;color:{INK_MUTED};line-height:1.4'><b style='color:{INK};display:block;"
        f"margin-bottom:2px'>{escape(t)}</b>{escape(d)}</div>" for t, d in funzioni)
    st.markdown(
        f"<div style='display:flex;gap:18px;align-items:flex-start;padding:20px 22px;background:#fff;"
        f"border:1px dashed #b9c6e2;border-radius:12px'>"
        f"<div style='width:58px;height:58px;border-radius:12px;background:{AZZURRO_TENUE};display:flex;"
        f"align-items:center;justify-content:center;font-size:26px;flex:none'>{icona}</div><div>"
        f"<div style='font-family:var(--mg-font-t);font-size:17px;font-weight:600;color:{BLU};"
        f"margin-bottom:3px'>{escape(titolo)}</div>"
        f"<div style='font-size:14px;color:{INK_MUTED};line-height:1.5'>{escape(descrizione)}</div>"
        f"</div></div>"
        f"<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;"
        f"margin-top:12px'>{feats}</div>",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Compatibilità: la testata la disegna ui.testata()."""
    return None
