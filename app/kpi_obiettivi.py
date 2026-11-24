"""
Obiettivi dei KPI (soglie del semaforo) del Portale NeWatt — logica pura,
testata offline. L'IO sta in kpi_dati (tabella kpi_obiettivi su cte-newatt).

Una soglia è per società × anno × riquadro KPI (codice della Tessera):
  * direzione +1 (più alto è meglio) o -1 (più basso è meglio);
  * obiettivo: raggiunto = «In target»;
  * soglia di attenzione (facoltativa): tra soglia e obiettivo =
    «Da attenzionare», oltre la soglia = «Critico». Senza soglia, il
    mancato obiettivo è «Critico».
I valori si salvano nell'unità dei dati (euro, frazione per le %); la pagina
li mostra e li fa inserire in k€ e in punti percentuali (UNITA_INSERIMENTO).
Per i flussi da inizio anno l'obiettivo è annuo e si confronta in
proporzione ai mesi di competenza (obiettivo_al_mese).
"""
from __future__ import annotations

import math
from typing import Optional

import kpi_catalogo as kc

# unità del catalogo -> (unità mostrata nella tabella, fattore dato -> tabella)
UNITA_INSERIMENTO = {"%": ("%", 100.0), "€": ("k€", 0.001)}
VERSI = {1: "↑ più alto è meglio", -1: "↓ più basso è meglio"}
PER_VERSO = {v: k for k, v in VERSI.items()}


def unita_inserimento(unita: str) -> tuple[str, float]:
    return UNITA_INSERIMENTO.get(unita, (unita, 1.0))


def _vuoto(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def obiettivo_al_mese(obiettivo: float, natura: str, mese_comp: int) -> float:
    """Obiettivo da confrontare con il valore del report: per i flussi YTD
    la quota dei mesi trascorsi (ottobre = 10/12), per stock e rapporti
    l'obiettivo così com'è."""
    return obiettivo * mese_comp / 12 if natura == "flusso" else obiettivo


def stato(valore: float, direzione: int, obiettivo: float, soglia: Optional[float]) -> str:
    """ok / warn / crit del semaforo (direzione +1 o -1)."""
    if valore * direzione >= obiettivo * direzione:
        return "ok"
    if not _vuoto(soglia) and valore * direzione >= soglia * direzione:
        return "warn"
    return "crit"


def direzione_default(t: kc.Tessera) -> int:
    """Verso proposto: quello del catalogo; i KPI neutri partono da +1."""
    return t.direzione if t.direzione in (1, -1) else 1


def valida(righe: list[dict]) -> list[str]:
    """righe = [{codice, nome, direzione, obiettivo, soglia}] in unità della
    tabella. Ritorna i messaggi d'errore (vuoto = si può salvare)."""
    errori = []
    for r in righe:
        ob, so, d = r.get("obiettivo"), r.get("soglia"), r.get("direzione")
        if _vuoto(ob) and not _vuoto(so):
            errori.append(f"«{r['nome']}»: c'è la soglia di attenzione ma manca l'obiettivo.")
            continue
        if _vuoto(ob):
            continue
        if d not in (1, -1):
            errori.append(f"«{r['nome']}»: scegli se è meglio più alto o più basso.")
            continue
        if not _vuoto(so) and so * d > ob * d:
            verso = "sotto" if d == 1 else "sopra"
            errori.append(f"«{r['nome']}»: la soglia di attenzione deve stare {verso} l'obiettivo "
                          f"(se più {'alto' if d == 1 else 'basso'} è meglio).")
    return errori


def calcola_modifiche(esistenti: dict, nuovi: dict) -> tuple[list[tuple], list[str]]:
    """esistenti/nuovi = {codice: (direzione, obiettivo, soglia)} in unità dei
    dati. Ritorna (da_scrivere [(codice, direzione, obiettivo, soglia)],
    da_cancellare [codice]): si toccano solo le righe cambiate."""
    def uguale(a, b):
        if _vuoto(a) and _vuoto(b):
            return True
        if _vuoto(a) or _vuoto(b):
            return False
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)

    scrivere, cancellare = [], []
    for codice, (d, ob, so) in nuovi.items():
        if _vuoto(ob):
            if codice in esistenti:
                cancellare.append(codice)
            continue
        prima = esistenti.get(codice)
        if prima is None or prima[0] != d or not uguale(prima[1], ob) or not uguale(prima[2], so):
            scrivere.append((codice, d, float(ob), None if _vuoto(so) else float(so)))
    return scrivere, cancellare
