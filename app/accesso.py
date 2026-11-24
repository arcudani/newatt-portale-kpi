"""
Pagina pubblica del link di invito (…/?invito=<token>): l'utente sceglie la
password. La chiama app.py PRIMA del gate di login, quando nell'URL c'è
«invito»; non richiede di essere autenticati e non mostra nient'altro del
portale.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import auth
import branding
import utenti


def pagina_invito(token: str) -> None:
    branding.render_login_hero(tema="newatt")
    # stessa colonna stretta del login
    st.markdown("<style>.st-key-invito_box { max-width:420px; margin:12px auto 0; }</style>",
                unsafe_allow_html=True)
    with st.container(key="invito_box"):
        _contenuto(token)


def _contenuto(token: str) -> None:
    try:
        invito = utenti.invito_valido(token)
    except Exception:  # noqa: BLE001 — DB irraggiungibile
        st.error("📡 Il portale non riesce a verificare il link in questo momento: riprova tra poco.")
        return

    fatto = st.session_state.get("invito_fatto")
    if fatto:
        st.success(f"Password impostata. Ora accedi con lo username **{fatto}** e la tua password.")
        if st.button("Vai all'accesso", type="primary", key="invito_vai"):
            st.session_state.pop("invito_fatto", None)
            st.query_params.clear()
            st.rerun()
        return
    if invito is None:
        st.markdown(branding.stato_vuoto(
            "Link non più valido",
            "Il link è già stato usato, è scaduto o è stato sostituito da uno più recente. "
            "Chiedi all'amministratore del portale di inviartene uno nuovo."), unsafe_allow_html=True)
        if st.button("Vai all'accesso", key="invito_vai_ko"):
            st.query_params.clear()
            st.rerun()
        return

    nome = (invito["nome"] or invito["username"]).split()[0]
    with st.form("invito_pwd"):
        st.markdown(f"<div class='mg-panel-title'>Ciao {escape(nome)}, scegli la tua password</div>"
                    f"<div class='mg-dom' style='margin:0 0 10px'>Username: <b>{escape(invito['username'])}</b>. "
                    f"Almeno {utenti.PWD_MIN} caratteri, con lettere e numeri.</div>",
                    unsafe_allow_html=True)
        pwd = st.text_input("Nuova password", type="password", key="invito_p1")
        conferma = st.text_input("Ripeti la password", type="password", key="invito_p2")
        invia = st.form_submit_button("Imposta la password")
    if invia:
        errori = utenti.valida_password(pwd, conferma, invito["username"])
        for e in errori:
            st.error(e)
        if not errori:
            try:
                username = utenti.usa_invito(token, pwd)
            except Exception:  # noqa: BLE001
                st.error("Salvataggio non riuscito: riprova tra poco.")
                return
            if username is None:
                st.error("Il link non è più valido: chiedine uno nuovo all'amministratore.")
                return
            auth.load_credentials.clear()          # il nuovo utente può entrare subito
            st.session_state["invito_fatto"] = username
            st.rerun()
