"""
Accesso ai dati bp_* su Supabase (IO). Le funzioni pure stanno in bp_import
(lettura Excel) e bp_calcoli (KPI): qui solo lettura/scrittura sul DB.

Le letture sono in cache 5 minuti (st.cache_data funziona anche fuori da
Streamlit, per gli script); dopo ogni scrittura chiamare svuota_cache().
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

import bp_import as bi
import db

COLONNE_VERSIONI = ["id", "nome", "descrizione", "stato", "origine",
                    "quadratura_ok", "quadratura", "creata_da", "created_at",
                    "stato_da", "stato_il"]
COLONNE_CATALOGO = ["codice", "nome", "livello", "vista", "ordine", "definizione",
                    "unita", "direzione", "owner", "frequenza", "fonte", "stato",
                    "fonte_prevista", "rif_ded", "benchmark", "soglia_gialla",
                    "soglia_rossa", "visibilita", "drill", "ambito", "bench_min",
                    "bench_max"]


# =============================================================================
# Letture (cache 5 min)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def carica_versioni() -> pd.DataFrame:
    rows = db.query_dict(
        f"SELECT {', '.join(COLONNE_VERSIONI)} FROM public.bp_versioni "
        "ORDER BY created_at DESC"
    )
    return pd.DataFrame(rows, columns=COLONNE_VERSIONI)


@st.cache_data(ttl=300, show_spinner=False)
def carica_ce(versione_id: int) -> pd.DataFrame:
    rows = db.query(
        "SELECT voce, anno, mese, importo::float8 FROM public.bp_ce_mensile "
        "WHERE versione_id = %s",
        (int(versione_id),),
    )
    return pd.DataFrame(rows, columns=["voce", "anno", "mese", "importo"])


@st.cache_data(ttl=300, show_spinner=False)
def carica_driver(versione_id: int) -> pd.DataFrame:
    cols = ["driver", *bi.DIMENSIONI, "anno", "mese", "valore"]
    rows = db.query(
        f"SELECT driver, {', '.join(bi.DIMENSIONI)}, anno, mese, valore::float8 "
        "FROM public.bp_driver_mensile WHERE versione_id = %s",
        (int(versione_id),),
    )
    return pd.DataFrame(rows, columns=cols)


@st.cache_data(ttl=300, show_spinner=False)
def carica_catalogo() -> pd.DataFrame:
    rows = db.query_dict(
        f"SELECT {', '.join(COLONNE_CATALOGO)} FROM public.bp_kpi_catalogo "
        "ORDER BY livello, vista, ordine"
    )
    df = pd.DataFrame(rows, columns=COLONNE_CATALOGO)
    for c in ("soglia_gialla", "soglia_rossa", "bench_min", "bench_max"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def svuota_cache() -> None:
    for f in (carica_versioni, carica_ce, carica_driver, carica_catalogo):
        f.clear()


# =============================================================================
# Scritture
# =============================================================================

def _sincronizza_voci(conn) -> None:
    """Upsert del piano voci (bp_import.VOCI è la fonte: il parser ne dipende).
    L'ordine della lista mette sempre il padre prima dei figli (FK)."""
    for ordine, v in enumerate(bi.VOCI, start=1):
        conn.execute(
            "INSERT INTO public.bp_voci (codice, etichetta, padre, livello, ordine, "
            "natura, commodity, famiglia_cts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (codice) DO UPDATE SET etichetta = excluded.etichetta, "
            "padre = excluded.padre, livello = excluded.livello, "
            "ordine = excluded.ordine, natura = excluded.natura, "
            "commodity = excluded.commodity, famiglia_cts = excluded.famiglia_cts",
            (v.codice, v.etichetta, v.padre, v.livello, ordine, v.natura,
             v.commodity, v.famiglia),
        )


def salva_versione(nome: str, descrizione: str, origine: str,
                   bp: bi.BPImportato, creata_da: str) -> int:
    """Crea una versione in BOZZA con CE e driver, in un'unica transazione.
    Ritorna l'id della nuova versione."""
    with db.connect() as conn:
        with conn.transaction():
            _sincronizza_voci(conn)
            vid = conn.execute(
                "INSERT INTO public.bp_versioni (nome, descrizione, origine, "
                "quadratura_ok, quadratura, creata_da) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s) RETURNING id",
                (nome, descrizione, origine, bp.quadratura_ok,
                 json.dumps(bp.quadratura), creata_da),
            ).fetchone()["id"]
            with conn.cursor() as cur:
                with cur.copy("COPY public.bp_ce_mensile "
                              "(versione_id, voce, anno, mese, importo) "
                              "FROM STDIN") as cp:
                    for r in bp.ce.itertuples(index=False):
                        cp.write_row((vid, r.voce, int(r.anno), int(r.mese),
                                      float(r.importo)))
                cols = ["driver", *bi.DIMENSIONI, "anno", "mese", "valore"]
                with cur.copy(f"COPY public.bp_driver_mensile "
                              f"(versione_id, {', '.join(cols)}) FROM STDIN") as cp:
                    for r in bp.driver[cols].itertuples(index=False):
                        cp.write_row((vid, *r[:-3], int(r[-3]), int(r[-2]),
                                      float(r[-1])))
    svuota_cache()
    return int(vid)


class TransizioneNonAmmessa(ValueError):
    pass


def aggiorna_stato(versione_id: int, stato: str, utente: str) -> None:
    """Cambia lo stato di una versione. Una versione fuori quadratura NON può
    essere approvata (blueprint §8): il vincolo è nella WHERE."""
    if stato not in ("bozza", "approvata", "archiviata"):
        raise TransizioneNonAmmessa(f"stato '{stato}' non valido")
    with db.connect() as conn:
        with conn.transaction():
            n = conn.execute(
                "UPDATE public.bp_versioni SET stato = %s, stato_da = %s, "
                "stato_il = now() WHERE id = %s "
                "AND (%s <> 'approvata' OR quadratura_ok IS TRUE)",
                (stato, utente, int(versione_id), stato),
            ).rowcount
    if n == 0:
        raise TransizioneNonAmmessa(
            "Versione non approvabile: la quadratura con l'Excel non è OK.")
    svuota_cache()


def elimina_bozza(versione_id: int) -> None:
    """Elimina una versione SOLO se è ancora in bozza (CE e driver a cascata)."""
    with db.connect() as conn:
        with conn.transaction():
            n = conn.execute(
                "DELETE FROM public.bp_versioni WHERE id = %s AND stato = 'bozza'",
                (int(versione_id),),
            ).rowcount
    if n == 0:
        raise TransizioneNonAmmessa("Si possono eliminare solo le bozze.")
    svuota_cache()
