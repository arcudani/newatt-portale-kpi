"""
Carica KPI — caricamento dell'Excel mensile «Dashboard KPI» (admin e
caricatori: Daniele, Virginia).

Flusso: scegli il file → l'app legge SOLO il foglio DASHBOARD (il resto
dell'Excel contiene dati di clienti e non si salva) → controlla società e
mese ricavati dal titolo → anteprima con avvisi → «Conferma e salva». Ogni
caricamento è una nuova versione: lo stesso mese caricato due volte non
sovrascrive nulla, vale l'ultima e lo storico le conserva tutte.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import branding
import kpi_catalogo as kc
import kpi_dati
import kpi_import as ki
import registro_moduli
import ui_kpi

utente = st.session_state.get("utente_autenticato", "")
ruolo = st.session_state.get("ruolo", "")
perimetro = st.session_state.get("perimetro") or []

st.markdown(branding.testata("Carica KPI", "Excel mensile «Dashboard KPI»", "", tema="newatt"),
            unsafe_allow_html=True)
st.markdown(
    "<div class='mg-dom'>Carica la «Dashboard KPI» del mese di una società. L'app legge solo il "
    "foglio <b>DASHBOARD</b> (gli altri fogli, con i dati dei clienti, non vengono salvati); "
    "società e mese si ricavano dal titolo in alto, «KPI MONITORING GAZEL OTTOBRE 2026», e puoi "
    "correggerli prima di salvare. Ricaricare un mese già presente crea una nuova versione: "
    "nulla viene sovrascritto.</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=4)
def _leggi(contenuto: bytes, nome: str):
    return ki.leggi_dashboard(contenuto, nome)


with st.container(key="panel_file"):
    st.markdown("<div class='mg-panel-title'>Nuovo caricamento</div>", unsafe_allow_html=True)
    file = st.file_uploader("Excel «Dashboard KPI» (.xlsx)", key="kpi_file",
                            help="Il file che contiene il foglio DASHBOARD, es. «17.11.2026.Dashboard KPI.xlsx».")

if file is not None:
    contenuto = file.getvalue()
    try:
        with st.spinner("Leggo il foglio DASHBOARD…"):
            imp = _leggi(contenuto, file.name)
    except ki.ImportKPIError as e:
        st.error(f"**Il file non può essere caricato.** {e}")
        imp = None
    except Exception as e:  # noqa: BLE001 — qualunque altro guasto: messaggio, non crash
        st.error("**Errore imprevisto nella lettura del file.** Riprova; se si ripete, manda il "
                 f"file a Daniele. Dettaglio tecnico: {type(e).__name__}: {e}")
        imp = None

    if imp is not None:
        with st.container(key="panel_carica"):
            st.markdown("<div class='mg-panel-title'>Controlla prima di salvare</div>",
                        unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            societa_ok = [s for s in kc.ORDINE_SOCIETA if s in perimetro]
            if not societa_ok:
                st.error("Il tuo utente non ha società assegnate: non puoi caricare dati.")
                st.stop()
            i_soc = societa_ok.index(imp.societa) if imp.societa in societa_ok else 0
            societa = c1.selectbox("Società", societa_ok, index=i_soc, format_func=kc.SOCIETA.get,
                                   key="kpi_up_societa")
            mese = c2.selectbox("Mese del report", list(range(1, 13)),
                                index=(imp.mese or 1) - 1,
                                format_func=lambda m: ui_kpi.MESI_IT[m - 1], key="kpi_up_mese")
            anno = c3.number_input("Anno", 2024, 2100, value=imp.anno or pd.Timestamp.now().year,
                                   step=1, key="kpi_up_anno")

            if imp.societa and imp.societa not in societa_ok:
                st.error(f"Il titolo dice «{kc.SOCIETA[imp.societa]}», che non è nel tuo perimetro: "
                         "puoi caricare solo " + ", ".join(kc.SOCIETA[s] for s in societa_ok) + ".")
                st.stop()
            if imp.societa and societa != imp.societa:
                st.warning(f"Il titolo del foglio dice «{kc.SOCIETA[imp.societa]}» ma hai scelto "
                           f"«{kc.SOCIETA[societa]}»: controlla di non aver preso il file sbagliato.")
            if imp.mese and (anno, mese) != (imp.anno, imp.mese):
                st.warning(f"Il titolo dice «{ui_kpi.mese_lungo(imp.anno, imp.mese)}» ma hai scelto "
                           f"«{ui_kpi.mese_lungo(int(anno), mese)}».")
            for avviso in imp.avvisi:
                st.warning(avviso)
            try:
                gia = kpi_dati.versioni_esistenti(societa, int(anno), mese)
            except Exception as e:  # noqa: BLE001
                st.error(f"📡 Impossibile controllare i caricamenti esistenti: {e}")
                st.stop()
            if gia:
                st.info(f"Per {kc.SOCIETA[societa]} · {ui_kpi.mese_lungo(int(anno), mese)} ci sono già "
                        f"{gia} caricamenti: salvando crei la versione {gia + 1}, le precedenti restano "
                        "nello storico.")

            righe = []
            for r in ki.righe_da_salvare(imp, int(anno), mese):
                m = kc.PER_CODICE[r["codice"]]
                testo = ui_kpi._testo_valore(r["valore"], m.unita)
                if r["testo"]:
                    testo += f" · {r['testo']}"
                righe.append({"Livello": ui_kpi.ROMANI[kc.livello_misura(m.codice)], "Indicatore": m.etichetta,
                              "Valore": testo,
                              "Competenza": ui_kpi.mese_lungo(r["anno_comp"], r["mese_comp"]),
                              "Rif.": m.rif})
            st.caption(f"{imp.n_valori} indicatori su {len(kc.MISURE)} con un valore · titolo letto: "
                       f"«{imp.titolo or '—'}»")
            st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch", height=420)
            note = st.text_input("Nota (facoltativa)", key="kpi_up_note",
                                 placeholder="es. riemissione dopo correzione del churn")
            if st.button("Conferma e salva", type="primary", key="kpi_up_salva"):
                try:
                    cid = kpi_dati.salva_caricamento(imp, societa, int(anno), mese, file.name,
                                                     utente, note)
                except Exception as e:  # noqa: BLE001
                    st.error(f"**Salvataggio non riuscito**, nessun dato è stato scritto: {e}")
                else:
                    st.success(f"Salvato: {kc.SOCIETA[societa]} · {ui_kpi.mese_lungo(int(anno), mese)} "
                               f"(caricamento n. {cid}).")
                    st.page_link(registro_moduli.PER_SOCIETA[societa].file,
                                 label=f"Apri il cruscotto di {kc.SOCIETA[societa]}",
                                 icon=":material/arrow_forward:")

# ------------------------------------------------------------------ storico --
with st.container(key="panel_storico_caricamenti"):
    st.markdown("<div class='mg-panel-title'>Caricamenti</div>", unsafe_allow_html=True)
    try:
        reg = kpi_dati.carica_caricamenti()
    except Exception as e:  # noqa: BLE001
        st.error(f"📡 Impossibile leggere lo storico dei caricamenti: {e}")
        st.stop()
    reg = reg[reg["societa"].isin(perimetro)]
    if reg.empty:
        st.caption("Ancora nessun caricamento.")
    else:
        vista = pd.DataFrame({
            "N.": reg["id"], "Società": reg["societa"].map(kc.SOCIETA),
            "Report": [ui_kpi.mese_lungo(int(a), int(m)) for a, m in zip(reg["anno"], reg["mese"])],
            "File": reg["file_nome"], "Indicatori": reg["n_valori"],
            "Caricato da": reg["caricato_da"],
            "Caricato il": pd.to_datetime(reg["caricato_il"], utc=True).dt.tz_convert("Europe/Rome")
                    .dt.strftime("%d/%m/%Y %H:%M"),
            "Stato": reg["annullato"].map({True: "annullato", False: "valido"}),
            "Note": reg["note"]})
        st.dataframe(vista, hide_index=True, width="stretch")
        if ruolo == "admin":
            validi = reg[~reg["annullato"]]
            if not validi.empty:
                c1, c2, c3 = st.columns([2, 1.2, 1], vertical_alignment="bottom")
                scelto = c1.selectbox(
                    "Annulla un caricamento (resta nello storico, non conta più)",
                    list(validi["id"]), key="kpi_annulla_id",
                    format_func=lambda i: (f"n. {i} · {kc.SOCIETA[validi.set_index('id').loc[i, 'societa']]} · "
                                           + ui_kpi.mese_lungo(int(validi.set_index('id').loc[i, 'anno']),
                                                               int(validi.set_index('id').loc[i, 'mese']))))
                conferma = c2.checkbox("Confermo l'annullamento", key="kpi_annulla_ok")
                if c3.button("Annulla", key="kpi_annulla_btn", disabled=not conferma):
                    kpi_dati.annulla_caricamento(int(scelto), utente)
                    st.success(f"Caricamento n. {scelto} annullato.")
                    st.rerun()
