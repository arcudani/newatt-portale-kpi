"""
Filtri GLOBALI (blueprint §4.1): versione BP, scenario di confronto, anno,
periodo. Stanno in sidebar, li disegna la shell a ogni run e persistono in
sessione (stesse chiavi su tutte le viste), così il drill da una tessera
del Cruscotto apre la vista L30 con i filtri già impostati.

Il viewer vede solo le versioni APPROVATE; admin/editor anche le bozze. Le
archiviate restano consultabili solo nella vista Versioni.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

import bp_calcoli as bc
import bp_dati
import formato as fmt

K_VERSIONE, K_CONFRONTO = "f_versione", "f_confronto"
K_ANNO, K_MESE = "f_anno", "f_mese_a"
NESSUNO = 0


def versioni_visibili(ruolo: str) -> pd.DataFrame:
    v = bp_dati.carica_versioni()
    if v.empty:
        return v
    if ruolo in ("admin", "editor"):
        return v[v["stato"] != "archiviata"]
    return v[v["stato"] == "approvata"]


def _etichetta(v: pd.DataFrame, vid: int) -> str:
    if vid == NESSUNO:
        return "Nessun confronto"
    r = v[v["id"] == vid]
    if r.empty:
        return "?"
    r = r.iloc[0]
    return r["nome"] + ("" if r["stato"] == "approvata" else f" · {r['stato']}")


def selettori(ruolo: str) -> None:
    """Disegna i filtri globali (va chiamata dentro `with st.sidebar`)."""
    try:
        v = versioni_visibili(ruolo)
    except Exception as e:  # DB giù: le viste mostreranno l'errore
        st.caption(f"Filtri non disponibili: {e}")
        return
    st.markdown("<div class='mg-side-label'>Filtri globali</div>", unsafe_allow_html=True)
    if v.empty:
        st.caption("Nessuna versione del BP disponibile.")
        return
    ids = [int(i) for i in v["id"]]
    approvate = [int(i) for i in v[v["stato"] == "approvata"]["id"]]
    if st.session_state.get(K_VERSIONE) not in ids:
        st.session_state[K_VERSIONE] = approvate[0] if approvate else ids[0]
    st.selectbox("Versione BP (riferimento)", ids, key=K_VERSIONE,
                 format_func=lambda i: _etichetta(v, i))

    altre = [NESSUNO] + [i for i in ids if i != st.session_state[K_VERSIONE]]
    if st.session_state.get(K_CONFRONTO) not in altre:
        st.session_state[K_CONFRONTO] = NESSUNO
    st.selectbox("Confronta con", altre, key=K_CONFRONTO,
                 format_func=lambda i: _etichetta(v, i),
                 help="Scenario 'BP vs Versione B'. I confronti con il consuntivo "
                      "arrivano con la fase 3.")

    d = bc.Dati(bp_dati.carica_ce(st.session_state[K_VERSIONE]), bc.dati_vuoti().drv)
    anni = d.anni or [dt.date.today().year]
    if st.session_state.get(K_ANNO) not in anni:
        st.session_state[K_ANNO] = bc.anno_default(d, dt.date.today().year)
    st.selectbox("Anno", anni, key=K_ANNO)
    if K_MESE not in st.session_state:
        st.session_state[K_MESE] = 12
    st.select_slider("Periodo: da gennaio a…", options=list(range(1, 13)), key=K_MESE,
                     format_func=lambda m: fmt.MESI_LUNGHI[m - 1])


@dataclass
class Contesto:
    utente: str
    ruolo: str
    versione: Optional[dict]
    confronto: Optional[dict]
    a: bc.Dati
    b: Optional[bc.Dati]
    periodo: bc.Periodo
    catalogo: pd.DataFrame

    @property
    def nome_a(self) -> str:
        return self.versione["nome"] if self.versione else "BP"

    @property
    def nome_b(self) -> str:
        return self.confronto["nome"] if self.confronto else ""

    @property
    def bros(self) -> bool:
        return self.ruolo in ("admin", "editor")


def contesto() -> Contesto:
    """Tutto quello che serve a una vista: utente, filtri, dati A/B, catalogo
    (già filtrato sul perimetro visibile al ruolo)."""
    ruolo = st.session_state.get("ruolo", "viewer")
    utente = st.session_state.get("utente_autenticato", "")
    v = versioni_visibili(ruolo)
    vid = st.session_state.get(K_VERSIONE)
    riga_a = v[v["id"] == vid] if not v.empty and vid is not None else pd.DataFrame()
    if riga_a.empty and not v.empty:
        riga_a = v.iloc[[0]]
    versione = riga_a.iloc[0].to_dict() if not riga_a.empty else None

    cid = st.session_state.get(K_CONFRONTO, NESSUNO)
    riga_b = v[v["id"] == cid] if (not v.empty and cid and versione
                                   and cid != versione["id"]) else pd.DataFrame()
    confronto = riga_b.iloc[0].to_dict() if not riga_b.empty else None

    a = (bc.Dati(bp_dati.carica_ce(versione["id"]), bp_dati.carica_driver(versione["id"]))
         if versione else bc.dati_vuoti())
    b = (bc.Dati(bp_dati.carica_ce(confronto["id"]), bp_dati.carica_driver(confronto["id"]))
         if confronto else None)
    anno = st.session_state.get(K_ANNO) or bc.anno_default(a, dt.date.today().year)
    periodo = bc.Periodo(int(anno), int(st.session_state.get(K_MESE, 12)))

    cat = bp_dati.carica_catalogo()
    if ruolo not in ("admin", "editor"):
        cat = cat[cat["visibilita"] == "tutti"]
    return Contesto(utente, ruolo, versione, confronto, a, b, periodo, cat)
