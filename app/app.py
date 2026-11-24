"""
Portale KPI del gruppo NeWatt — shell modulare.

Avvio locale (da dentro app\\):  python -m streamlit run app.py --server.port 8540

La shell fa, una volta sola e nell'ordine: bridge dei segreti,
set_page_config, CSS di base + tema NeWatt, registrazione pagine
(st.navigation) filtrate per ruolo e perimetro di società, filtri globali del
Business Plan Migliora (solo sulle sue pagine), gate di login, run della
vista corrente. Le viste sono script-pagina in moduli\\ e NON chiamano
set_page_config / login; le dashboard di società applicano il proprio tema.

⚠️ La danza navigation/login è load-bearing (stessa di Bros_ERP e
Gas_Monitor): st.navigation va chiamata SEMPRE, SUBITO e UNA SOLA volta per
run, così un URL profondo sopravvive al giro di login; dopo l'autenticazione
in-run un singolo st.rerun() ricostruisce la sidebar visibile. Lo username
va risolto PRIMA di costruire la nav (riautenticazione da cookie in una
sessione nuova: authentication_status è True ma utente/ruolo non ancora).
"""
from __future__ import annotations

import streamlit as st

import config
config.bridge_streamlit_secrets()  # st.secrets -> os.environ (PRIMA di db/auth)
import auth
import branding
import registro_moduli

st.set_page_config(
    page_title="Portale KPI — Gruppo NeWatt",
    page_icon="⚡",
    layout="wide",
)

branding.apply_base(logo=False)
branding.applica_tema("newatt")
branding.barra_portale()
st.markdown(registro_moduli.css_wip(), unsafe_allow_html=True)
branding.enable_altair_theme()

if st.query_params.get("invito"):
    # Link personale dell'email di invito: pagina pubblica per scegliere la
    # password, prima (e al posto) del login. La nav resta chiamata una volta.
    import accesso  # noqa: E402
    st.navigation(registro_moduli.build_navigation("admin"), position="hidden")
    accesso.pagina_invito(st.query_params["invito"])
    st.stop()

_gia_autenticato = bool(st.session_state.get("authentication_status"))
if _gia_autenticato:
    _utente = st.session_state.get("utente_autenticato", "")
    if not _utente:
        _raw = (st.session_state.get("username") or st.session_state.get("name") or "").strip()
        _utente = auth._canonical_username(_raw) or _raw
    _ruolo = st.session_state.get("ruolo") or auth.ruolo(_utente) or "lettore"
    _perimetro = st.session_state.get("perimetro")
    if _perimetro is None:
        _perimetro = auth.perimetro(_utente)
    st.session_state["ruolo"], st.session_state["perimetro"] = _ruolo, _perimetro
    pg = st.navigation(registro_moduli.build_navigation(_ruolo, _perimetro), expanded=True)
    if pg.url_path in registro_moduli.URL_BP:
        # Filtri globali del BP Migliora PRIMA del gate: in sidebar stanno sopra "Esci".
        import filtri  # noqa: E402  (dopo il bridge dei segreti)
        with st.sidebar, st.container(key="mg_filtri"):
            filtri.selettori(_ruolo)
else:
    # nav nascosta con TUTTE le pagine: un link profondo sopravvive al login
    pg = st.navigation(registro_moduli.build_navigation("admin"), position="hidden")
    branding.render_login_hero(tema="newatt")

# Gate di login: blocca qui (st.stop) finché non autenticato.
utente_autenticato = auth.require_login()
st.session_state["utente_autenticato"] = utente_autenticato
st.session_state["ruolo"] = auth.ruolo(utente_autenticato) or "lettore"
st.session_state["perimetro"] = auth.perimetro(utente_autenticato)

if not _gia_autenticato:
    st.rerun()

pg.run()
