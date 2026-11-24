"""
Catalogo KPI — la tabella bp_kpi_catalogo in lettura (blueprint §6-§7).

Un KPI, una definizione, un owner, una fonte: le tessere delle viste si
generano da qui. Owner, soglie, ambito e intervallo di benchmark si cambiano
sul DB senza toccare il codice. Il viewer NeWatt non vede i KPI con
visibilità «bros».

Vista di riferimento: niente tessere KPI (un numero dominante non ha senso su
un elenco). La gerarchia è pillole di conteggio → chiave di lettura → filtri →
composizione della selezione a barre (per livello e per ambito) → tabella, con
i campi nuovi del catalogo: **ambito** e **intervallo benchmark**
(bench_min / bench_max) accanto al testo del benchmark. La colonna Vista
porta anche il titolo della pagina che ospita la tessera (dal registro).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import formato as fmt
import registro_moduli
import ui

ctx = ui.carica_contesto()
ui.testata("CAT", "Che cosa misura ogni KPI, chi ne risponde, da dove arriva il dato?", None,
           livello="Riferimento")

SENZA_AMBITO = "senza ambito"
DIREZIONE = {1: "↑ più alto è meglio", -1: "↓ più basso è meglio", 0: "= neutro"}


def _vista(codice) -> str:
    """«V4 · VAS»: il codice del blueprint più il titolo della pagina che
    ospita la tessera (dal registro dei moduli, unica fonte dei titoli)."""
    m = registro_moduli.PER_CODICE.get(str(codice))
    return f"{codice} · {m.titolo}" if m else str(codice or "")


cat = ctx.catalogo.copy()
cat["ambito"] = cat["ambito"].fillna("").astype(str).str.strip()
cat["liv"] = cat["livello"].map(lambda x: f"L{x}")
cat["amb"] = cat["ambito"].where(cat["ambito"] != "", SENZA_AMBITO)
cat["vista_txt"] = cat["vista"].map(_vista)
cat["ha_intervallo"] = cat["bench_min"].notna() | cat["bench_max"].notna()

n_tot = len(cat)
n_att = int((cat["stato"] == "attivo").sum())
n_seg = int((cat["stato"] == "segnaposto").sum())
n_amb = int(cat.loc[cat["ambito"] != "", "ambito"].nunique())
n_int = int(cat["ha_intervallo"].sum())


def _pillola(numero: int, testo: str, tono: str = "neutro") -> str:
    return f"<span class='mg-pill {tono}'><b>{fmt.numero(numero)}</b>&nbsp;{testo}</span>"


st.markdown(
    "<div class='mg-hk-badges' style='margin:4px 0 12px'>"
    + _pillola(n_tot, "KPI a catalogo")
    + _pillola(n_att, "attivi in v1", "buono")
    + _pillola(n_seg, "segnaposto DeD", "attenzione")
    + _pillola(n_amb, "ambiti")
    + _pillola(n_int, "con intervallo benchmark")
    + "</div>",
    unsafe_allow_html=True,
)
ui.nota(
    "<b>Come si legge.</b> L'<b>ambito</b> raggruppa i riquadri di una vista in una fascia, "
    "con il titolo nella colonna colorata a sinistra. Il chip di stato del riquadro si "
    "accende solo contro un riferimento reale: con una <b>versione di confronto</b> lo "
    "decidono le <b>soglie gialla / rossa</b> sullo scostamento; senza, l'<b>intervallo "
    "benchmark</b> (dentro = In target, fuori nel verso sbagliato = Da attenzionare o "
    "Critico). Un valore del BP senza riferimento resta «Valore BP»."
)

# --- Filtri locali -----------------------------------------------------------
f1, f2, f3, f4 = st.columns([1.35, 1.1, 1.6, 1.9])
livelli = f1.segmented_control("Livello", ["L3", "L30", "L300"], selection_mode="multi",
                               default=["L3", "L30", "L300"], key="cat_livello") or []
stati = f2.segmented_control("Stato", ["attivo", "segnaposto"], selection_mode="multi",
                             default=["attivo", "segnaposto"], key="cat_stato") or []
ambiti_scelti = f3.multiselect("Ambito", sorted(cat["amb"].unique()), default=[],
                               placeholder="tutti gli ambiti", key="cat_ambito")
cerca = f4.text_input("Cerca", placeholder="nome, definizione, owner, ambito, vista, codice…",
                      key="cat_cerca")

cat = cat[cat["liv"].isin(livelli) & cat["stato"].isin(stati)]
if ambiti_scelti:
    cat = cat[cat["amb"].isin(ambiti_scelti)]
if cerca and not cat.empty:
    campi = ["nome", "definizione", "owner", "amb", "vista_txt", "rif_ded", "codice"]
    testo = cat[campi].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    cat = cat[testo.str.contains(cerca.lower(), regex=False)]

st.caption(f"{fmt.numero(len(cat))} KPI su {fmt.numero(n_tot)} con i filtri impostati.")

if cat.empty:
    st.info("Nessun KPI corrisponde ai filtri impostati: allarga la selezione.")
    st.stop()


# --- Composizione della selezione (quote, non serie: barre, non grafici) -----
def _righe_quota(coppie: list[tuple[str, pd.DataFrame]]) -> list[dict]:
    """(etichetta, righe) -> barre con conteggio, quota sul totale e attivi."""
    totale = len(cat)
    righe = []
    for etichetta, blocco in coppie:
        n = len(blocco)
        if not n:
            continue
        quota = n / totale
        righe.append({"nome": etichetta, "quota": quota,
                      "valore": f"{fmt.numero(n)} KPI · {fmt.pct(quota, 0)}",
                      "delta": f"{fmt.numero(int((blocco['stato'] == 'attivo').sum()))} attivi",
                      "tono": "neutro"})
    return righe


with ui.pannello("🧭 Composizione della selezione", "cat_composizione"):
    ambiti_ordinati = cat["amb"].value_counts().index.tolist()
    meta = (len(ambiti_ordinati) + 1) // 2          # due colonne di ambiti: pannello basso
    c1, c2, c3 = st.columns([1, 1.15, 1.15], gap="medium")
    with c1:
        st.caption("Per livello di lettura")
        ui.barre(_righe_quota([(ui.ETICHETTA_LIVELLO.get(liv.lstrip("L"), liv),
                                cat[cat["liv"] == liv]) for liv in ("L3", "L30", "L300")]))
    for colonna, titolo, blocco in ((c2, "Per ambito", ambiti_ordinati[:meta]),
                                    (c3, "Per ambito · segue", ambiti_ordinati[meta:])):
        if not blocco:      # pochi ambiti: niente colonna con la sola intestazione
            continue
        with colonna:
            st.caption(titolo)
            ui.barre(_righe_quota([(a, cat[cat["amb"] == a]) for a in blocco]))
    st.caption("Quote sul totale dei KPI selezionati; a destra del valore, quanti sono già "
               "calcolati nella v1 (il resto sono segnaposto DeD).")


# --- Tabella -----------------------------------------------------------------
def _soglie(r) -> str:
    """«5% / 10%», sulle percentuali in punti: «3 pp / 6 pp». Se il catalogo
    indica una sola soglia l'altra resta un trattino, mai «n.d.%»."""
    gialla, rossa = r["soglia_gialla"], r["soglia_rossa"]
    if fmt.manca(gialla) and fmt.manca(rossa):
        return ""
    u = " pp" if r["unita"] == "%" else "%"
    return " / ".join("—" if fmt.manca(s) else f"{fmt.numero(s)}{u}" for s in (gialla, rossa))


def _limite(x: float, unita: str) -> str:
    return fmt.pct(x, 0) if unita == "%" else fmt.numero(x)


def _intervallo(r) -> str:
    """bench_min / bench_max con l'unità scritta una volta sola: «75–85%»,
    «10–15 €», «≥ 45%». Vuoto (non 'n.d.') quando il catalogo non lo indica."""
    lo, hi = r["bench_min"], r["bench_max"]
    manca_lo, manca_hi = fmt.manca(lo), fmt.manca(hi)
    if manca_lo and manca_hi:
        return ""
    unita = str(r["unita"] or "")
    coda = " €" if unita.startswith("€") else ""
    if manca_hi:
        return f"≥ {_limite(lo, unita)}{coda}"
    if manca_lo:
        return f"≤ {_limite(hi, unita)}{coda}"
    primo = fmt.numero(lo * 100) if unita == "%" else fmt.numero(lo)
    return f"{primo}–{_limite(hi, unita)}{coda}"


show = pd.DataFrame({
    "Codice": cat["codice"], "KPI": cat["nome"], "Liv.": cat["liv"], "Vista": cat["vista_txt"],
    "Ambito": cat["amb"], "Definizione": cat["definizione"], "Unità": cat["unita"],
    "Direzione": cat["direzione"].map(lambda d: DIREZIONE.get(int(d), "") if not fmt.manca(d) else ""),
    "Benchmark": cat["benchmark"], "Intervallo": cat.apply(_intervallo, axis=1),
    "Soglie G / R": cat.apply(_soglie, axis=1), "Owner": cat["owner"], "Fonte v1": cat["fonte"],
    "Stato": cat["stato"], "Fonte prevista": cat["fonte_prevista"], "Rif. DeD": cat["rif_ded"],
    "Visibilità": cat["visibilita"],
})

T = st.column_config.TextColumn
COLONNE = {
    "Codice": T(width="small", pinned=True,
                help="Chiave tecnica: la usano il motore di calcolo e le tessere."),
    "KPI": T(width="medium", pinned=True),
    "Liv.": T(width="small", help="Livello di lettura: 3, 30 o 300 secondi."),
    "Vista": T(width="medium", help="Pagina che ospita la tessera del KPI."),
    "Ambito": T(width="medium",
                help="Gruppo della tessera dentro la vista: colonna in L3, fascia in L30."),
    "Definizione": T(width="large"),
    "Unità": T(width="small"),
    "Direzione": T(width="medium", help="Verso buono del KPI."),
    "Benchmark": T(width="medium", help="Riferimento di mercato a parole (fonte DeD)."),
    "Intervallo": T(width="small",
                    help="Fascia sana bench_min–bench_max: dentro insight, fuori avviso."),
    "Soglie G / R": T(width="small",
                      help="Scostamento dalla versione di confronto che accende l'anello."),
    "Owner": T(width="medium", help="Chi risponde del KPI."),
    "Fonte v1": T(width="small", help="Da dove arriva il dato oggi."),
    "Stato": T(width="small", help="attivo = calcolato; segnaposto = tessera DeD in attesa."),
    "Fonte prevista": T(width="medium", help="Sorgente attesa per i segnaposto."),
    "Rif. DeD": T(width="small", help="Codice della tessera nella dashboard DeD."),
    "Visibilità": T(width="small", help="«tutti» oppure «bros» (perimetro riservato)."),
}

with ui.pannello("📚 Catalogo KPI 3-30-300", "cat_tabella"):
    st.dataframe(show, hide_index=True, width="stretch", row_height=34,
                 height=min(46 + 34 * len(show), 720), column_config=COLONNE)
    st.caption("Fonte: tabella `bp_kpi_catalogo` su Supabase. Ambito, intervallo benchmark e "
               "ordine arrivano dalla migrazione bp003; owner nominativi e soglie definitive "
               "restano punti aperti del blueprint (§12, punti 5-6).")
    ui.scarica(show, "catalogo_kpi")
