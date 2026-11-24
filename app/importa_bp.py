"""Importa un BP Excel di Migliora come nuova versione in BOZZA su Supabase.

Legge i valori calcolati del file (bp_import.leggi_bp), stampa quadratura e
avvisi, e salva CE + driver in un'unica transazione. La versione nasce in
bozza: l'approvazione si fa dalla vista Versioni (solo admin, e solo se la
quadratura con il Riepilogo è OK). Lo stesso import è disponibile in-app.

Uso (da C:\\Code\\Migliora_BP\\app):
    .\\.venv\\Scripts\\python.exe importa_bp.py "<file.xlsx>" --nome "BP v5" --prova
    .\\.venv\\Scripts\\python.exe importa_bp.py "<file.xlsx>" --nome "BP v5" \\
        --descrizione "Bozza 2026.08, FTE"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config  # noqa: F401  (carica il .env)
import bp_dati
import bp_import as bi


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="percorso del BP Excel (.xlsx)")
    ap.add_argument("--nome", required=True, help="nome univoco della versione")
    ap.add_argument("--descrizione", default="")
    ap.add_argument("--prova", action="store_true",
                    help="solo lettura e quadratura, nessuna scrittura sul DB")
    args = ap.parse_args()

    path = Path(args.file)
    bp = bi.leggi_bp(path.read_bytes())
    ko = [q for q in bp.quadratura if not q["ok"]]
    print(f"Letto {path.name}: {len(bp.ce)} righe CE, {len(bp.driver)} righe driver.")
    print(f"Quadratura con il Riepilogo: {len(bp.quadratura) - len(ko)}/"
          f"{len(bp.quadratura)} controlli OK (tolleranza ±0,1%).")
    for q in ko:
        print(f"  KO {q['grandezza']} {q['anno']}: Excel {q['excel']:,.0f} · "
              f"import {q['motore']:,.0f} · Δ {q['delta']:,.0f}")
    for a in bp.avvisi:
        print(f"  AVVISO {a}")
    if args.prova:
        print("Prova: nessuna scrittura.")
        return 0
    vid = bp_dati.salva_versione(args.nome, args.descrizione, path.name, bp,
                                 creata_da="import CLI")
    print(f"OK: versione '{args.nome}' creata in bozza (id {vid}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
