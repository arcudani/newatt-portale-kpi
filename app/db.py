"""
Helper di connessione PostgreSQL (Supabase) — psycopg 3.

Stesso helper di Bros_ERP / Gas_Monitor: pool condiviso per processo e
prepare_threshold=None, OBBLIGATORIO per il Transaction pooler di Supabase
(pgbouncer).

Due database (`base`):
  * "newatt" — progetto Supabase `cte-newatt`: portale KPI del gruppo
    (kpi_utenti, kpi_caricamenti, kpi_valori). Env `NEWATT_DB_URL`.
  * "bp"     — progetto `bros-consulenza`: Controllo BP Migliora (bp_*).
    Env `SUPABASE_DB_URL`. È il default, così il codice BP non cambia.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row, tuple_row

try:
    from psycopg_pool import ConnectionPool
except ImportError:  # senza psycopg-pool si apre una connessione per query
    ConnectionPool = None  # type: ignore[assignment,misc]

import config


class DBConfigError(RuntimeError):
    pass


_ENV = {"bp": "SUPABASE_DB_URL", "newatt": "NEWATT_DB_URL"}


def conn_str(base: str = "bp") -> str:
    s = config.newatt_db_url() if base == "newatt" else config.supabase_db_url()
    if not s:
        raise DBConfigError(
            f"{_ENV[base]} non impostata. Inseriscila nel file .env "
            "(Supabase > Connect > Transaction pooler > URI)."
        )
    return s


_POOLS: dict = {}


def _pool(base: str = "bp"):
    if base not in _POOLS:
        _POOLS[base] = ConnectionPool(
            conn_str(base),
            min_size=1,
            max_size=2,
            max_idle=300,
            check=ConnectionPool.check_connection,
            kwargs=dict(row_factory=dict_row, prepare_threshold=None,
                        connect_timeout=15),
            open=True,
        )
    return _POOLS[base]


@contextmanager
def connect(autocommit: bool = False, base: str = "bp"):
    """Presta una connessione dal pool (row_factory=dict_row)."""
    if ConnectionPool is None:
        with psycopg.connect(
            conn_str(base), row_factory=dict_row, connect_timeout=15,
            prepare_threshold=None, autocommit=autocommit,
        ) as conn:
            yield conn
        return
    with _pool(base).connection() as conn:
        conn.autocommit = autocommit
        yield conn


def query(sql: str, params=None, base: str = "bp") -> list[tuple]:
    """SELECT -> righe come TUPLE posizionali. Autocommit + retry con backoff
    sui problemi transitori (drop del pooler, blip DNS/rete)."""
    last_err = None
    for tentativo in range(3):
        try:
            with connect(autocommit=True, base=base) as conn:
                cur = conn.cursor(row_factory=tuple_row)
                cur.execute(sql, params or ())
                return cur.fetchall()
        except psycopg.OperationalError as e:
            last_err = e
            time.sleep(0.6 * (tentativo + 1))
    raise last_err


def query_dict(sql: str, params=None, base: str = "bp") -> list[dict]:
    """Come query() ma con righe dict (colonna -> valore)."""
    last_err = None
    for tentativo in range(3):
        try:
            with connect(autocommit=True, base=base) as conn:
                cur = conn.cursor(row_factory=dict_row)
                cur.execute(sql, params or ())
                return cur.fetchall()
        except psycopg.OperationalError as e:
            last_err = e
            time.sleep(0.6 * (tentativo + 1))
    raise last_err
