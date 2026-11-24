"""Crea un utente del Portale KPI NeWatt e/o ne imposta la password.

Password chiesta UNA volta (non si vede mentre scrivi), mostrato solo il
numero di caratteri, conferma s/n. Si salva solo l'hash bcrypt nella tabella
public.kpi_utenti del progetto cte-newatt: la password non passa mai in chiaro.

Uso (da C:\\Code\\Migliora_BP\\app):
    .\\.venv\\Scripts\\python.exe imposta_pwd.py                      # elenca gli utenti
    .\\.venv\\Scripts\\python.exe imposta_pwd.py Daniele              # imposta la password
    .\\.venv\\Scripts\\python.exe imposta_pwd.py MarioRossi --ruolo lettore --societa gazel
    .\\.venv\\Scripts\\python.exe imposta_pwd.py Virginia --ruolo caricatore

--societa: una o più tra lifegate, gazel, migliora (separate da virgola);
omessa = tutto il gruppo. Su un utente esistente ruolo e società si cambiano
solo se li indichi.
"""
from __future__ import annotations

import argparse
import getpass
import sys

import bcrypt

import config  # noqa: F401  (carica il .env)
import db
import kpi_catalogo as kc

BASE = "newatt"


def elenca() -> None:
    rows = db.query("SELECT username, nome, ruolo, societa, attivo, password_hash IS NOT NULL "
                    "FROM public.kpi_utenti ORDER BY username", base=BASE)
    if not rows:
        print("Nessun utente. Creane uno: python imposta_pwd.py <Nome> --ruolo admin")
        return
    for u, nome, ruolo, societa, attivo, ha_pwd in rows:
        perim = ", ".join(societa) if societa else "tutto il gruppo"
        print(f"  {u:<14} {nome:<20} ruolo={ruolo:<10} società={perim:<28} attivo={attivo} "
              f"password={'impostata' if ha_pwd else 'MANCANTE'}")


def imposta(username: str, ruolo: str | None, societa: list[str] | None, nome: str | None) -> int:
    pwd = getpass.getpass(f"Nuova password per {username}: ")
    print(f"Ricevuti {len(pwd)} caratteri.")
    if len(pwd) < 8:
        print("ERRORE: minimo 8 caratteri.")
        return 1
    if input("Confermi? [s/n] ").strip().lower() != "s":
        print("Annullato.")
        return 1
    h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            esiste = conn.execute("SELECT 1 FROM public.kpi_utenti WHERE username = %s",
                                  (username,)).fetchone()
            if esiste:
                conn.execute(
                    "UPDATE public.kpi_utenti SET password_hash = %s, "
                    "ruolo = coalesce(%s, ruolo), societa = coalesce(%s, societa), "
                    "nome = coalesce(%s, nome) WHERE username = %s",
                    (h, ruolo, societa, nome, username))
            else:
                conn.execute(
                    "INSERT INTO public.kpi_utenti (username, nome, password_hash, ruolo, societa) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (username, nome or username, h, ruolo or "lettore", societa or []))
    print(f"OK: password di {username} impostata.")
    elenca()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("username", nargs="?", help="utente da creare/aggiornare")
    ap.add_argument("--ruolo", choices=["admin", "caricatore", "lettore"])
    ap.add_argument("--societa", help="lifegate,gazel,migliora (omessa = tutto il gruppo)")
    ap.add_argument("--nome", help="nome e cognome da mostrare")
    args = ap.parse_args()
    if not args.username:
        elenca()
        sys.exit(0)
    scelte = None
    if args.societa:
        scelte = [s.strip().lower() for s in args.societa.split(",") if s.strip()]
        ignote = [s for s in scelte if s not in kc.SOCIETA]
        if ignote:
            print(f"ERRORE: società sconosciute {ignote}. Valide: {', '.join(kc.SOCIETA)}")
            sys.exit(1)
    sys.exit(imposta(args.username, args.ruolo, scelte, args.nome))
