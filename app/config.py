"""
Configurazione Controllo BP Migliora — UNICA fonte dei segreti (getter da env).

In locale i valori vengono da app\\.env (python-dotenv, caricato all'import).
Su Streamlit Community Cloud arrivano da st.secrets: bridge_streamlit_secrets()
li riversa in os.environ e va chiamata in cima ad app.py, PRIMA dell'import
di db/auth (stesso pattern di Bros_ERP e Gas_Monitor).

Regola: niente os.getenv sparsi nel codice — aggiungere getter qui.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def bridge_streamlit_secrets() -> None:
    """Copia st.secrets in os.environ (Streamlit Community Cloud).
    No-op in locale o se st.secrets non è disponibile."""
    try:
        import streamlit as st
        for chiave, valore in st.secrets.items():
            if isinstance(valore, str) and chiave not in os.environ:
                os.environ[chiave] = valore
    except Exception:
        pass


def supabase_db_url() -> str:
    """Connection string Postgres (Transaction pooler Supabase, porta 6543)."""
    return os.getenv("SUPABASE_DB_URL", "").strip()


def newatt_db_url() -> str:
    """Connection string del progetto Supabase `cte-newatt` (portale KPI del
    gruppo NeWatt e suoi utenti). Transaction pooler, porta 6543."""
    return os.getenv("NEWATT_DB_URL", "").strip()


def auth_cookie_key() -> str:
    """Chiave di firma del cookie di sessione (PROPRIA di questa app:
    le sessioni di ERP, Offerte, Gas Monitor e Migliora sono indipendenti)."""
    return os.getenv("AUTH_COOKIE_KEY", "").strip()
