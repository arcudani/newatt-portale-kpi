"""
Obiettivi KPI — tabella di configurazione delle soglie del semaforo, per
ogni riquadro KPI e per ogni società (admin e caricatori: Daniele, Virginia).

Una riga per riquadro (le 20 tessere del Livello I e II). Si scelgono
società e anno, si scrivono obiettivo e soglia di attenzione nelle unità
mostrate (k€, %, n., MWh, mesi, €/cliente) e si salva: si scrivono solo le
righe cambiate; svuotare l'obiettivo toglie la soglia (semaforo spento).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import branding
import kpi_catalogo as kc
import kpi_dati
import kpi_obiettivi as ko
import ui_kpi

utente = st.session_state.get("utente_autenticato", "")
perimetro = st.session_state.get("perimetro") or []

st.markdown(branding.testata("Obiettivi KPI", "Soglie del semaforo per società e anno", "",
                             tema="newatt"), unsafe_allow_html=True)
st.markdown(
    "<div class='mg-dom'>Per ogni KPI scrivi l'<b>obiettivo</b> e, se vuoi, la <b>soglia di "
    "attenzione</b>. Nei cruscotti il riquadro diventa <b>In target</b> se l'obiettivo è "
    "raggiunto, <b>Da attenzionare</b> tra soglia e obiettivo, <b>Critico</b> oltre la soglia "
    "(senza soglia: mancato obiettivo = Critico). Per i KPI <b>da inizio anno</b> (EBITDA, "
    "fatturato, margine, utile, MWh) scrivi l'obiettivo <b>annuo</b>: l'app lo confronta in "
    "proporzione ai mesi trascorsi. Svuota l'obiettivo per spegnere il semaforo di quel KPI."
    "</div>", unsafe_allow_html=True)

societa_ok = [s for s in kc.ORDINE_SOCIETA if s in perimetro]
if not societa_ok:
    st.error("Il tuo utente non ha società assegnate.")
    st.stop()

with st.container(key="mg_slicer"):
    c1, c2, _ = st.columns([1.4, 1, 3], vertical_alignment="bottom")
    societa = c1.selectbox("Società", societa_ok, format_func=kc.SOCIETA.get, key="ob_societa")
    anno = int(c2.number_input("Anno", 2024, 2100, value=pd.Timestamp.now().year, step=1,
                               key="ob_anno"))

try:
    tutti = kpi_dati.carica_obiettivi(societa)
except Exception as e:  # noqa: BLE001
    st.error(f"📡 Impossibile leggere gli obiettivi dal database: {e}")
    if st.button("🔄 Riprova"):
        kpi_dati.svuota_cache()
        st.rerun()
    st.stop()

esistenti = kpi_dati.obiettivi_anno(societa, anno)
info = tutti[tutti["anno"] == anno].set_index("codice") if not tutti.empty else pd.DataFrame()

righe = []
for t in kc.TESSERE:
    unita, fattore = ko.unita_inserimento(t.misura.unita)
    d, ob, so = esistenti.get(t.codice, (ko.direzione_default(t), None, None))
    ultima = ""
    if t.codice in info.index:
        quando = pd.Timestamp(info.loc[t.codice, "aggiornato_il"])
        quando = quando.tz_convert("Europe/Rome") if quando.tzinfo else quando
        ultima = f"{quando:%d/%m/%Y} · {info.loc[t.codice, 'aggiornato_da']}"
    righe.append({
        "codice": t.codice,
        "Livello": ui_kpi.ROMANI[t.livello], "Ambito": t.ambito, "KPI": t.nome,
        "Unità": unita + (" annuo" if t.misura.natura == "flusso" else ""),
        "Verso": ko.VERSI[d],
        "Obiettivo": None if ob is None else round(ob * fattore, 6),
        "Soglia di attenzione": None if so is None else round(so * fattore, 6),
        "Ultima modifica": ultima,
    })
tabella = pd.DataFrame(righe).set_index("codice")
for _c in ("Obiettivo", "Soglia di attenzione"):     # float: le celle vuote restano vuote
    tabella[_c] = pd.to_numeric(tabella[_c], errors="coerce").astype(float)

with st.container(key="panel_obiettivi"):
    st.markdown(f"<div class='mg-panel-title'>{kc.SOCIETA[societa]} · obiettivi {anno}</div>",
                unsafe_allow_html=True)
    modificata = st.data_editor(
        tabella, key=f"ob_editor_{societa}_{anno}", num_rows="fixed", hide_index=True,
        width="stretch", height=740, placeholder="—",
        disabled=["Livello", "Ambito", "KPI", "Unità", "Ultima modifica"],
        column_config={
            "Livello": st.column_config.TextColumn("Livello", width=55),
            "Ambito": st.column_config.TextColumn("Ambito", width=88),
            "Unità": st.column_config.TextColumn("Unità", width=85),
            "KPI": st.column_config.TextColumn("KPI", width=170),
            "Ultima modifica": st.column_config.TextColumn("Ultima modifica", width=118),
            "Verso": st.column_config.SelectboxColumn(
                "Verso", options=list(ko.VERSI.values()), required=True, width=148,
                help="Se per questo KPI è meglio un valore più alto o più basso."),
            "Obiettivo": st.column_config.NumberColumn(
                "Obiettivo", format="localized", width=92,
                help="Nell'unità della colonna Unità (k€, %, …); per i KPI «annuo» il valore "
                     "di fine anno."),
            "Soglia di attenzione": st.column_config.NumberColumn(
                "Soglia di attenzione", format="localized", width=152,
                help="Facoltativa. Oltre questa soglia il KPI è Critico; tra soglia e obiettivo "
                     "è Da attenzionare."),
        })

    nuovi_tabella = []
    for codice, r in modificata.iterrows():
        nuovi_tabella.append({"codice": codice, "nome": r["KPI"],
                              "direzione": ko.PER_VERSO.get(r["Verso"]),
                              "obiettivo": None if pd.isna(r["Obiettivo"]) else float(r["Obiettivo"]),
                              "soglia": (None if pd.isna(r["Soglia di attenzione"])
                                         else float(r["Soglia di attenzione"]))})
    errori = ko.valida(nuovi_tabella)
    for err in errori:
        st.error(err)

    nuovi = {}
    for r in nuovi_tabella:
        _, fattore = ko.unita_inserimento(kc.PER_TESSERA[r["codice"]].misura.unita)
        nuovi[r["codice"]] = (r["direzione"],
                              None if r["obiettivo"] is None else r["obiettivo"] / fattore,
                              None if r["soglia"] is None else r["soglia"] / fattore)
    scrivere, cancellare = ko.calcola_modifiche(esistenti, nuovi)
    n = len(scrivere) + len(cancellare)
    c_info, c_btn = st.columns([3, 1], vertical_alignment="center")
    c_info.caption(f"{len(esistenti)} KPI con obiettivo per {anno} · "
                   + (f"{n} modifiche da salvare" if n else "nessuna modifica"))
    if c_btn.button("Salva obiettivi", type="primary", key="ob_salva",
                    disabled=bool(errori) or n == 0, width="stretch"):
        try:
            kpi_dati.salva_obiettivi(societa, anno, scrivere, cancellare, utente)
        except Exception as e:  # noqa: BLE001
            st.error(f"**Salvataggio non riuscito**, nessuna soglia è stata modificata: {e}")
        else:
            st.session_state["ob_esito"] = (f"Salvato: {len(scrivere)} obiettivi aggiornati, "
                                            f"{len(cancellare)} tolti ({kc.SOCIETA[societa]} · {anno}).")
            st.session_state.pop(f"ob_editor_{societa}_{anno}", None)
            st.rerun()
    if "ob_esito" in st.session_state:
        st.success(st.session_state.pop("ob_esito"))
