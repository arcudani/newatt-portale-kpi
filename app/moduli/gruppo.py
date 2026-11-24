"""Panoramica del gruppo NeWatt: per ogni società del perimetro
dell'utente i KPI principali dell'ultimo report, con il link al cruscotto."""
import streamlit as st

import ui_kpi

ui_kpi.panoramica(st.session_state.get("perimetro") or [])
