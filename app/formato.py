"""Formati numerici e di data in italiano (funzioni pure).

Regola "niente errori silenziosi" (blueprint §3): un valore mancante (None o
NaN) non diventa mai 0 né #DIV/0!, ma "n.d." — il motivo lo porta chi chiama.
"""
from __future__ import annotations

import math
from typing import Optional

MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott",
        "nov", "dic"]
MESI_LUNGHI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
               "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
ND = "n.d."


def manca(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _it(x: float, dec: int = 0) -> str:
    """1234567.891 -> '1.234.567,89' (dec=2). Mai '-0'."""
    if round(x, dec) == 0:
        x = 0.0
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero(v: Optional[float], dec: int = 0) -> str:
    return ND if manca(v) else _it(v, dec)


def eur(v: Optional[float], dec: int = 0) -> str:
    """Importo pieno: '€ 1.234.567'."""
    return ND if manca(v) else f"€ {_it(v, dec)}"


def eur_compatto(v: Optional[float]) -> str:
    """Importo per le tessere: 147 M€ · 20,9 M€ · 4,06 M€ · 591 k€ · 850 €."""
    if manca(v):
        return ND
    if abs(v) < 0.5:
        v = 0.0
    a = abs(v)
    if a >= 1e8:
        return f"{_it(v / 1e6, 0)} M€"
    if a >= 1e7:
        return f"{_it(v / 1e6, 1)} M€"
    if a >= 1e6:
        return f"{_it(v / 1e6, 2)} M€"
    if a >= 1e4:
        return f"{_it(v / 1e3, 0)} k€"
    return f"{_it(v, 0)} €"


def pct(v: Optional[float], dec: int = 1) -> str:
    """Frazione -> percentuale: 0.194 -> '19,4%'."""
    return ND if manca(v) else f"{_it(v * 100, dec)}%"


def segno(v: Optional[float], testo: str) -> str:
    """Prefisso + per i valori positivi non nulli (il - lo mette il numero).
    Niente '+' se il testo formattato è comunque uno zero (es. '0,0%')."""
    if manca(v) or testo == ND:
        return testo
    nudo = testo.replace("€", "").replace("%", "").replace(" ", "").replace(" ", "")
    zero = (not nudo) or all(ch in "0,." for ch in nudo)
    return f"+{testo}" if v > 0 and not zero else testo


def pct_segno(v: Optional[float], dec: int = 1) -> str:
    return segno(v, pct(v, dec))


def formatta(v: Optional[float], unita: str) -> tuple[str, str]:
    """Valore principale di una tessera -> (numero, unità piccola)."""
    if manca(v):
        return ND, ""
    if unita == "€":
        return eur_compatto(v), ""
    if unita == "%":
        return pct(v), ""
    if unita == "N.":
        return numero(v), ""
    if unita in ("€/PdP", "€/punto"):
        return numero(v), unita
    if unita == "€/FTE":
        return f"{_it(v / 1e3, 1)} k€", "per FTE"
    if unita == "FTE":
        return numero(v, 1), "FTE"
    return numero(v, 1), unita


def formatta_hero(v: Optional[float], unita: str) -> tuple[str, str]:
    """Numero grande della tessera separato dall'unità piccola (stile DeD):
    (20,9 · M€) · (38,6 · %) · (42 · € / PdP) · (25.612 · '')."""
    if manca(v):
        return ND, ""
    if unita == "€":
        a = abs(v)
        if a < 0.5:
            return "0", "€"
        if a >= 1e8:
            return _it(v / 1e6, 0), "M€"
        if a >= 1e7:
            return _it(v / 1e6, 1), "M€"
        if a >= 1e6:
            return _it(v / 1e6, 2), "M€"
        if a >= 1e4:
            return _it(v / 1e3, 0), "k€"
        return _it(v, 0), "€"
    if unita == "%":
        return _it(v * 100, 1), "%"
    if unita == "N.":
        return _it(v, 0), ""
    if unita in ("€/PdP", "€/punto"):
        return _it(v, 0), unita.replace("/", " / ")
    if unita == "€/FTE":
        return _it(v / 1e3, 1), "k€ / FTE"
    if unita == "FTE":
        return _it(v, 1), "FTE"
    return _it(v, 1), unita


def formatta_delta(assoluto: Optional[float], relativo: Optional[float],
                   unita: str) -> str:
    """Scostamento leggibile: '+1,2 M€ · +5,8%' oppure '-2,1 pp'."""
    if manca(assoluto):
        return ND
    if unita == "%":
        return f"{segno(assoluto, _it(assoluto * 100, 1))} pp"
    if unita == "€":
        base = segno(assoluto, eur_compatto(assoluto))
    elif unita == "FTE":
        base = segno(assoluto, _it(assoluto, 1)) + " FTE"
    else:
        base = segno(assoluto, _it(assoluto, 0))
    if manca(relativo):
        return base
    return f"{base} · {segno(relativo, _it(relativo * 100, 1))}%"


def mese_label(anno: int, mese: int) -> str:
    """(2027, 3) -> 'mar 27'."""
    return f"{MESI[mese - 1]} {str(anno)[-2:]}"


def periodo_label(anno: int, mese_da: int, mese_a: int) -> str:
    if mese_da == 1 and mese_a == 12:
        return f"anno {anno}"
    if mese_da == mese_a:
        return f"{MESI_LUNGHI[mese_a - 1]} {anno}"
    return f"{MESI[mese_da - 1]}–{MESI[mese_a - 1]} {anno}"
