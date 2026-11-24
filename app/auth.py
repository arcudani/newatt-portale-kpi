"""
Autenticazione del Portale KPI NeWatt — streamlit-authenticator + bcrypt.

Le credenziali stanno nella tabella dedicata public.kpi_utenti del progetto
Supabase `cte-newatt` (db base "newatt"), lette con l'utente di database
`kpi_portale` che vede solo le tabelle kpi_*.

Ruoli (kpi_utenti.ruolo):
  admin      — tutto: tutte le società del perimetro, caricamenti, annullo
               versioni, sezione Business Plan Migliora;
  caricatore — carica l'Excel mensile (es. Daniele, Virginia) e legge;
  lettore    — solo lettura delle dashboard.
Perimetro (kpi_utenti.societa): elenco di società visibili; vuoto = tutto il
gruppo (lifegate, gazel, migliora).

Cookie proprio (newatt_kpi_auth). Password: imposta_pwd.py in questo repo.
"""
from __future__ import annotations

from typing import Optional

import streamlit as st
import streamlit_authenticator as stauth

import config
import db
import kpi_catalogo as kc

COOKIE_NAME = "newatt_kpi_auth"
COOKIE_EXPIRY_DAYS = 7
RUOLI = ("admin", "caricatore", "lettore")
ETICHETTA_RUOLO = {"admin": "amministratore", "caricatore": "carica dati", "lettore": "lettura"}
BASE = "newatt"


def _cookie_key() -> str:
    key = config.auth_cookie_key()
    if not key:
        # Fallback solo sviluppo locale: sessione non persistente, NON sicura.
        return "dev-only-cookie-key-cambiami"
    return key


@st.cache_data(ttl=300, show_spinner=False)
def load_credentials() -> dict:
    """Dict credenziali per streamlit-authenticator da kpi_utenti.
    Solo utenti attivi con password impostata. Cache 5 min."""
    rows = db.query(
        "SELECT username, nome, password_hash, ruolo FROM public.kpi_utenti "
        "WHERE attivo = true AND password_hash IS NOT NULL", base=BASE)
    usernames = {}
    for username, nome, pwd_hash, ruolo_ in rows:
        usernames[username] = {
            "name": nome or username,
            "password": pwd_hash,            # già hashato (bcrypt)
            "email": "",
            "roles": [ruolo_],
        }
    return {"usernames": usernames}


def get_authenticator() -> Optional[stauth.Authenticate]:
    creds = load_credentials()
    if not creds["usernames"]:
        return None
    return stauth.Authenticate(
        creds,
        COOKIE_NAME,
        _cookie_key(),
        COOKIE_EXPIRY_DAYS,
        auto_hash=False,   # gli hash sono già in DB
    )


def require_login() -> str:
    """Mostra il login e blocca l'app (st.stop) finché non autenticato.
    Ritorna lo username canonico autenticato."""
    try:
        authenticator = get_authenticator()
    except db.DBConfigError as e:
        st.error(f"⚙️ {e}")
        st.stop()
    except Exception as e:
        if "kpi_utenti" in str(e):
            st.error("⚠️ Tabella `kpi_utenti` non trovata: applicare la migrazione "
                     "`app/migrations/kpi001_portale_newatt.sql` sul progetto cte-newatt.")
            st.stop()
        raise
    if authenticator is None:
        st.error("⚠️ Nessun utente con password impostata. Impostala con: "
                 "python imposta_pwd.py Daniele")
        st.stop()

    if not st.session_state.get("authentication_status"):
        authenticator.login(location="main")

    status = st.session_state.get("authentication_status")
    if status is False:
        st.error("❌ Username o password errati.")
        st.stop()
    if status is None:
        st.info("🔐 Inserisci le credenziali per accedere.")
        st.stop()

    # Nome canonico dal DB (streamlit-authenticator abbassa a minuscolo).
    raw = (st.session_state.get("username") or st.session_state.get("name") or "").strip()
    utente = _canonical_username(raw) or raw
    with st.sidebar, st.container(key="mg_logout"):
        st.caption(f"👤 **{st.session_state.get('name', utente)}** · "
                   f"{ETICHETTA_RUOLO.get(ruolo(utente), 'lettura')}")
        authenticator.logout("Esci", location="main")
    return utente


@st.cache_data(ttl=300, show_spinner=False)
def _canonical_username(name: str) -> Optional[str]:
    name = (name or "").strip()
    if not name:
        return None
    rows = db.query("SELECT username FROM public.kpi_utenti "
                    "WHERE lower(username) = lower(%s) LIMIT 1", (name,), base=BASE)
    return rows[0][0] if rows else None


@st.cache_data(ttl=300, show_spinner=False)
def _profilo(username: str) -> tuple[str, tuple]:
    if not username:
        return "", ()
    rows = db.query("SELECT ruolo, societa FROM public.kpi_utenti "
                    "WHERE lower(username) = lower(%s) AND attivo LIMIT 1", (username,), base=BASE)
    if not rows:
        return "", ()
    return rows[0][0], tuple(rows[0][1] or ())


def ruolo(username: str) -> str:
    """'admin' | 'caricatore' | 'lettore' ('' se l'utente non esiste)."""
    return _profilo(username)[0]


def perimetro(username: str) -> list[str]:
    """Società visibili all'utente, nell'ordine del portale (vuoto in DB =
    tutto il gruppo)."""
    if not ruolo(username):
        return []
    scelte = _profilo(username)[1]
    return [s for s in kc.ORDINE_SOCIETA if not scelte or s in scelte]
