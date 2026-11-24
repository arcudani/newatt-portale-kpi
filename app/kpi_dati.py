"""
IO del portale KPI NeWatt sul database `cte-newatt` (db base "newatt").

Storicizzazione: ogni Excel caricato è un record in kpi_caricamenti con i suoi
valori in kpi_valori; nulla si sovrascrive. La vista kpi_valori_correnti dà,
per società e mese del report, l'ultimo caricamento non annullato.
Le letture hanno cache di 5 minuti; ogni scrittura la svuota.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import db
import kpi_import as ki

BASE = "newatt"
COLONNE_VALORI = ["societa", "anno", "mese", "caricamento_id", "caricato_il", "caricato_da",
                  "codice", "anno_comp", "mese_comp", "valore", "testo"]
COLONNE_CARICAMENTI = ["id", "societa", "anno", "mese", "titolo_excel", "file_nome",
                       "n_valori", "caricato_da", "caricato_il", "annullato", "note"]


@st.cache_data(ttl=300, show_spinner=False)
def carica_valori(societa: str) -> pd.DataFrame:
    """Valori correnti (ultima versione di ogni mese) di una società."""
    righe = db.query(
        f"SELECT {', '.join(COLONNE_VALORI)} FROM public.kpi_valori_correnti "
        "WHERE societa = %s ORDER BY anno, mese, codice", (societa,), base=BASE)
    df = pd.DataFrame(righe, columns=COLONNE_VALORI)
    if not df.empty:
        df["valore"] = pd.to_numeric(df["valore"], errors="coerce")
        for c in ("anno", "mese", "anno_comp", "mese_comp"):
            df[c] = df[c].astype(int)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def carica_caricamenti(societa: str | None = None) -> pd.DataFrame:
    """Registro dei caricamenti (tutte le versioni, anche annullate)."""
    filtro, params = ("WHERE societa = %s", (societa,)) if societa else ("", ())
    righe = db.query(
        f"SELECT {', '.join(COLONNE_CARICAMENTI)} FROM public.kpi_caricamenti {filtro} "
        "ORDER BY id DESC", params, base=BASE)
    return pd.DataFrame(righe, columns=COLONNE_CARICAMENTI)


COLONNE_OBIETTIVI = ["societa", "anno", "codice", "direzione", "obiettivo", "soglia",
                     "aggiornato_da", "aggiornato_il"]


@st.cache_data(ttl=300, show_spinner=False)
def carica_obiettivi(societa: str) -> pd.DataFrame:
    """Obiettivi (soglie del semaforo) di una società, tutti gli anni."""
    righe = db.query(
        f"SELECT {', '.join(COLONNE_OBIETTIVI)} FROM public.kpi_obiettivi WHERE societa = %s "
        "ORDER BY anno, codice", (societa,), base=BASE)
    df = pd.DataFrame(righe, columns=COLONNE_OBIETTIVI)
    for c in ("obiettivo", "soglia"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def obiettivi_anno(societa: str, anno: int) -> dict:
    """{codice tessera: (direzione, obiettivo, soglia)} per un anno; {} se
    la tabella non è leggibile (il semaforo resta spento, niente errore)."""
    try:
        df = carica_obiettivi(societa)
    except Exception:  # noqa: BLE001
        return {}
    df = df[df["anno"] == anno]
    return {r.codice: (int(r.direzione), float(r.obiettivo),
                       None if pd.isna(r.soglia) else float(r.soglia))
            for r in df.itertuples()}


def salva_obiettivi(societa: str, anno: int, scrivere: list, cancellare: list, utente: str) -> None:
    """Upsert delle righe cambiate e cancellazione di quelle svuotate, in
    UNA transazione (kpi_obiettivi.calcola_modifiche)."""
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            cur = conn.cursor()
            if scrivere:
                cur.executemany(
                    "INSERT INTO public.kpi_obiettivi (societa, anno, codice, direzione, obiettivo, "
                    "soglia, aggiornato_da) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (societa, anno, codice) DO UPDATE SET direzione = excluded.direzione, "
                    "obiettivo = excluded.obiettivo, soglia = excluded.soglia, "
                    "aggiornato_da = excluded.aggiornato_da, aggiornato_il = now()",
                    [(societa, anno, c, d, ob, so, utente) for c, d, ob, so in scrivere])
            if cancellare:
                cur.execute("DELETE FROM public.kpi_obiettivi WHERE societa = %s AND anno = %s "
                            "AND codice = ANY(%s)", (societa, anno, list(cancellare)))
    carica_obiettivi.clear()


def svuota_cache() -> None:
    for f in (carica_valori, carica_caricamenti, carica_obiettivi):
        f.clear()


def versioni_esistenti(societa: str, anno: int, mese: int) -> int:
    righe = db.query(
        "SELECT count(*) FROM public.kpi_caricamenti WHERE societa = %s AND anno = %s "
        "AND mese = %s AND NOT annullato", (societa, anno, mese), base=BASE)
    return int(righe[0][0]) if righe else 0


def salva_caricamento(imp: ki.KPIImportato, societa: str, anno: int, mese: int,
                      file_nome: str, utente: str, note: str = "") -> int:
    """Nuovo caricamento + valori in UNA transazione. Ritorna l'id."""
    righe = ki.righe_da_salvare(imp, anno, mese)
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO public.kpi_caricamenti (societa, anno, mese, titolo_excel, file_nome, "
                "file_sha256, n_valori, caricato_da, note) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id",
                (societa, anno, mese, imp.titolo, file_nome, imp.sha256, imp.n_valori, utente, note))
            cid = cur.fetchone()["id"]
            cur.executemany(
                "INSERT INTO public.kpi_valori (caricamento_id, codice, anno_comp, mese_comp, valore, testo) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(cid, r["codice"], r["anno_comp"], r["mese_comp"], r["valore"], r["testo"])
                 for r in righe])
    svuota_cache()
    return int(cid)


def annulla_caricamento(caricamento_id: int, utente: str) -> None:
    """Annulla una versione (resta nello storico, non conta più)."""
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            conn.execute(
                "UPDATE public.kpi_caricamenti SET annullato = true, "
                "note = trim(note || ' · annullato da ' || %s || ' il ' || to_char(now(), 'DD/MM/YYYY')) "
                "WHERE id = %s", (utente, caricamento_id))
    svuota_cache()
