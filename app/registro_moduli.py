"""
Registro delle viste del Portale KPI NeWatt — aggiungere una vista = 1 file
in moduli\\ + 1 riga qui (stesso pattern di Bros_ERP e Gas_Monitor).

Sezioni della sidebar:
  * Gruppo NeWatt      — panoramica delle tre società (pagina di atterraggio);
  * LifeGate Energy / Gazel / Migliora — una sezione per società con due
                         voci, «Livello I» e «Livello II» del foglio
                         DASHBOARD, con colori e logo della società;
                         visibili solo alle società del perimetro dell'utente;
  * Dati               — caricamento dell'Excel mensile e obiettivi dei KPI
                         (admin, caricatore: Daniele e Virginia);
  * Business Plan Migliora · 3″ / 30″ / 300″ — il Controllo BP Migliora
                         (viste V1-V11 + Catalogo), riservato agli admin.

Ogni vista è uno script-pagina Streamlit: codice top-level, NIENTE
st.set_page_config / login / CSS di base (li fa la shell app.py). Utente,
ruolo e perimetro si leggono da st.session_state["utente_autenticato"] /
["ruolo"] / ["perimetro"].
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

TUTTI = ("admin", "caricatore", "lettore")
CARICANO = ("admin", "caricatore")
SOLO_ADMIN = ("admin",)

SEZ_GRUPPO = "Gruppo NeWatt"
SEZ_DATI = "Dati"
SEZ_L3 = "BP Migliora · 3 secondi"
SEZ_L30 = "BP Migliora · 30 secondi"
SEZ_L300 = "BP Migliora · 300 secondi"
SEZIONI_BP = (SEZ_L3, SEZ_L30, SEZ_L300)


@dataclass(frozen=True)
class Modulo:
    file: str                 # percorso dello script-pagina, relativo ad app/
    titolo: str
    icona: str
    codice: str               # G0, LG/GZ/MG, UP; V1..V11 e CAT per il BP Migliora
    descrizione: str = ""
    url_path: Optional[str] = None
    sezione: str = SEZ_L300
    default: bool = False
    attivo: bool = True       # False = segnaposto "in arrivo" (fase 2-3)
    ruoli: tuple = TUTTI
    wip: bool = True          # Work in Progress: etichetta «WIP» accanto alla voce del menu
    societa: Optional[str] = None   # dashboard di una società: visibile solo nel perimetro
    livello: Optional[int] = None   # 1 o 2: livello del foglio DASHBOARD mostrato

    @property
    def bp(self) -> bool:
        return self.sezione in SEZIONI_BP


MODULI: list[Modulo] = [
    # ---------------- Portale KPI del gruppo ----------------
    Modulo("moduli/gruppo.py", "Panoramica gruppo", ":material/hub:", "G0",
           "Le società del gruppo NeWatt in un colpo d'occhio",
           sezione=SEZ_GRUPPO, default=True, wip=False),
    # una sezione per società, due voci: Livello I (url storico, es. /gazel) e Livello II
    Modulo("moduli/kpi_lifegate.py", "Livello I", ":material/looks_one:", "LG",
           "KPI di Livello I di LifeGate Energy", url_path="lifegate",
           sezione="LifeGate Energy", wip=False, societa="lifegate", livello=1),
    Modulo("moduli/kpi_lifegate_l2.py", "Livello II", ":material/looks_two:", "LG2",
           "KPI di Livello II di LifeGate Energy", url_path="lifegate-livello-2",
           sezione="LifeGate Energy", wip=False, societa="lifegate", livello=2),
    Modulo("moduli/kpi_gazel.py", "Livello I", ":material/looks_one:", "GZ",
           "KPI di Livello I di Gazel", url_path="gazel",
           sezione="Gazel", wip=False, societa="gazel", livello=1),
    Modulo("moduli/kpi_gazel_l2.py", "Livello II", ":material/looks_two:", "GZ2",
           "KPI di Livello II di Gazel", url_path="gazel-livello-2",
           sezione="Gazel", wip=False, societa="gazel", livello=2),
    Modulo("moduli/kpi_migliora.py", "Livello I", ":material/looks_one:", "MG",
           "KPI di Livello I di Migliora", url_path="migliora",
           sezione="Migliora", wip=False, societa="migliora", livello=1),
    Modulo("moduli/kpi_migliora_l2.py", "Livello II", ":material/looks_two:", "MG2",
           "KPI di Livello II di Migliora", url_path="migliora-livello-2",
           sezione="Migliora", wip=False, societa="migliora", livello=2),
    Modulo("moduli/carica_kpi.py", "Carica KPI", ":material/upload_file:", "UP",
           "Caricamento dell'Excel mensile «Dashboard KPI» e storico dei caricamenti",
           url_path="carica", sezione=SEZ_DATI, ruoli=CARICANO, wip=False),
    Modulo("moduli/obiettivi_kpi.py", "Obiettivi KPI", ":material/flag:", "OB",
           "Soglie obiettivo del semaforo per ogni KPI e società",
           url_path="obiettivi", sezione=SEZ_DATI, ruoli=CARICANO, wip=False),
    # ---------------- Business Plan Migliora (solo admin) ----------------
    Modulo("moduli/cruscotto.py", "Cruscotto Direzione", ":material/speed:", "V1",
           "Il piano sta tenendo? I KPI di primo livello di Migliora",
           url_path="bp-cruscotto", sezione=SEZ_L3, ruoli=SOLO_ADMIN),
    Modulo("moduli/economico.py", "Economico", ":material/euro:", "V2",
           "Dove si scosta il conto economico e perché",
           url_path="economico", sezione=SEZ_L30, ruoli=SOLO_ADMIN),
    Modulo("moduli/commerciale.py", "Commerciale Agenti", ":material/handshake:", "V3",
           "Produzione, cessazioni, portafoglio e provvigioni",
           url_path="commerciale", sezione=SEZ_L30, ruoli=SOLO_ADMIN),
    Modulo("moduli/vas.py", "VAS", ":material/extension:", "V4",
           "Punti con VAS, penetrazione ed extra-profitto per prodotto",
           url_path="vas", sezione=SEZ_L30, ruoli=SOLO_ADMIN),
    Modulo("moduli/operations.py", "Operations & Servizio", ":material/settings:", "V5",
           "Cost-to-Serve, FTE, perdite su crediti e qualità del servizio",
           url_path="operations", sezione=SEZ_L30, ruoli=SOLO_ADMIN),
    Modulo("moduli/scostamenti.py", "Scostamenti voce × mese", ":material/table_chart:", "V6",
           "Heatmap del CE per voce e mese con dettaglio ed export",
           url_path="scostamenti", ruoli=SOLO_ADMIN),
    Modulo("moduli/cdv_agenti.py", "Modulo CdV Agenti", ":material/edit:", "V7",
           "Parametri editabili del canale agenti (fase 2)",
           url_path="cdv-agenti", attivo=False, ruoli=SOLO_ADMIN),
    Modulo("moduli/modulo_vas.py", "Modulo VAS", ":material/edit:", "V8",
           "Parametri editabili del VAS (fase 2)",
           url_path="modulo-vas", attivo=False, ruoli=SOLO_ADMIN),
    Modulo("moduli/fte.py", "FTE e Personale", ":material/groups:", "V9",
           "Driver di carico, FTE da driver vs pianificati, costo del personale",
           url_path="fte", ruoli=SOLO_ADMIN),
    Modulo("moduli/consuntivo.py", "Consuntivo", ":material/input:", "V10",
           "Import del CE mensile, mapping conti, quadratura (fase 3)",
           url_path="consuntivo", attivo=False, ruoli=SOLO_ADMIN),
    Modulo("moduli/versioni.py", "Versioni", ":material/inventory_2:", "V11",
           "Versioni del BP, quadratura con l'Excel, confronto KPI",
           url_path="versioni", ruoli=SOLO_ADMIN),
    Modulo("moduli/catalogo.py", "Catalogo KPI", ":material/menu_book:", "CAT",
           "Definizione, owner, fonte e soglie di ogni KPI",
           url_path="catalogo", ruoli=SOLO_ADMIN),
]
PER_CODICE = {m.codice: m for m in MODULI}
PER_SOCIETA = {m.societa: m for m in MODULI if m.societa and m.livello == 1}   # atterraggio
PER_SOCIETA_LIVELLO = {(m.societa, m.livello): m for m in MODULI if m.societa}
URL_BP = {m.url_path for m in MODULI if m.bp}


def url_di(m: Modulo) -> str:
    if m.default:
        return "/"
    return "/" + (m.url_path or Path(m.file).stem)


def moduli_visibili(ruolo: str, perimetro: Optional[list] = None) -> list[Modulo]:
    """Viste del ruolo; le dashboard di società solo se nel perimetro
    (perimetro None = nessun filtro, usato prima del login)."""
    return [m for m in MODULI if ruolo in m.ruoli
            and (m.societa is None or perimetro is None or m.societa in perimetro)]


def css_wip() -> str:
    """Pillola «WIP» in fondo alle voci del menu delle viste ancora in
    lavorazione (Modulo.wip). Via CSS sull'href della voce, così il titolo
    della pagina resta pulito."""
    selettori = ", ".join(f'[data-testid="stSidebarNav"] a[href$="{url_di(m)}"]::after'
                          for m in MODULI if m.wip and m.attivo and not m.default)
    if not selettori:
        return ""
    return ("<style>" + selettori + " { content:'WIP'; margin-left:auto; padding:1px 7px; "
            "border-radius:999px; background:var(--mg-azzurro-tenue, #e3f0fb); "
            "color:var(--mg-blu, #28326f); font-size:10px; line-height:16px; font-weight:700; "
            "letter-spacing:.06em; flex:none; }</style>")


def build_navigation(ruolo: str, perimetro: Optional[list] = None) -> dict[str, list]:
    """Argomento di st.navigation: {sezione: [st.Page, ...]}.
    Ruolo vuoto (prima del login) = vista del lettore, senza filtro di
    perimetro: la nav nascosta deve conoscere tutte le pagine perché un URL
    profondo sopravviva al login."""
    sezioni: dict[str, list] = {}
    for m in moduli_visibili(ruolo or "lettore", perimetro):
        titolo = m.titolo if m.attivo else f"{m.titolo} · in arrivo"
        kwargs = dict(title=titolo, icon=m.icona, default=m.default)
        if m.url_path:
            kwargs["url_path"] = m.url_path
        sezioni.setdefault(m.sezione, []).append(st.Page(m.file, **kwargs))
    return sezioni
