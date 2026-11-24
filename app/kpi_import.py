"""
Lettura del foglio DASHBOARD dell'Excel «Dashboard KPI» — funzioni PURE
(bytes in, dati out), testate offline su un workbook fittizio.

Il foglio si legge per CONTENUTO, non per coordinate: ogni misura del
catalogo si cerca per etichetta (normalizzata: maiuscole, senza spazi,
apostrofi e trattini) e il valore è il primo numero nelle 3 celle sotto,
saltando le righe di descrizione e fermandosi se si incontra un'altra
etichetta (così una cella vuota non «ruba» il valore della misura dopo).

Dal titolo in A1 («KPI MONITORING GAZEL OTTOBRE 2026») si ricavano società
e mese del report; chi carica può correggerli prima di salvare.

Gli errori sono pensati per chi carica il file, non per uno sviluppatore:
ImportKPIError porta un messaggio leggibile e cosa fare.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import kpi_catalogo as kc

FOGLIO = "DASHBOARD"
MESI = ["GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO", "GIUGNO", "LUGLIO", "AGOSTO",
        "SETTEMBRE", "OTTOBRE", "NOVEMBRE", "DICEMBRE"]
ALIAS_SOCIETA = {"GAZEL": "gazel", "LIFEGATE": "lifegate", "LIFEGATEENERGY": "lifegate",
                 "ENERGYLIFEGATE": "lifegate", "MIGLIORA": "migliora", "MIGLIORAENERGIA": "migliora"}
MAX_RIGHE_SOTTO = 3
SOGLIA_MANCANTI = 0.5      # oltre metà misure mancanti: non è il foglio giusto


class ImportKPIError(Exception):
    """Errore bloccante, con un messaggio da mostrare a chi carica il file."""


@dataclass
class KPIImportato:
    societa: Optional[str]                # dal titolo (None se non riconosciuta)
    anno: Optional[int]
    mese: Optional[int]
    titolo: str
    valori: dict                          # codice -> float | None
    testi: dict = field(default_factory=dict)      # codice -> testo (es. mese del churn max)
    mancanti: list = field(default_factory=list)   # codici senza etichetta nel foglio
    non_numerici: list = field(default_factory=list)  # (codice, contenuto della cella)
    avvisi: list = field(default_factory=list)
    sha256: str = ""

    @property
    def n_valori(self) -> int:
        return sum(1 for v in self.valori.values() if v is not None)


def normalizza(testo) -> str:
    s = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9%/]", "", s.upper())


def _apri(contenuto: bytes, nome_file: str = ""):
    """Workbook in sola lettura dei valori, con errori comprensibili."""
    import openpyxl

    nome = (nome_file or "").lower()
    if nome.endswith((".xls", ".xlsb")):
        raise ImportKPIError(
            f"Il file «{nome_file}» è in un formato Excel che non riesco a leggere "
            f"({nome.rsplit('.', 1)[-1]}). Aprilo in Excel e salvalo come «Cartella di lavoro "
            "di Excel (*.xlsx)», poi caricalo di nuovo.")
    if nome.endswith((".csv", ".pdf", ".ods")):
        raise ImportKPIError(
            f"Il file «{nome_file}» non è un Excel. Carica la «Dashboard KPI» in formato .xlsx.")
    if not contenuto:
        raise ImportKPIError("Il file è vuoto. Controlla di aver scelto quello giusto.")
    if contenuto[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ImportKPIError(
            "Il file è protetto da password o è nel vecchio formato .xls. Togli la password "
            "(File > Informazioni > Proteggi cartella di lavoro) o salvalo come .xlsx, poi "
            "caricalo di nuovo.")
    if not zipfile.is_zipfile(io.BytesIO(contenuto)):
        raise ImportKPIError(
            "Non riesco ad aprire il file: non è un Excel .xlsx valido oppure è danneggiato. "
            "Prova ad aprirlo in Excel e a salvarlo di nuovo come .xlsx.")
    try:
        return openpyxl.load_workbook(io.BytesIO(contenuto), data_only=True, read_only=False)
    except Exception as e:  # noqa: BLE001 — openpyxl solleva tipi diversi
        raise ImportKPIError(
            f"Non riesco ad aprire il file Excel ({type(e).__name__}). Prova a salvarlo di "
            "nuovo come .xlsx da Excel e a ricaricarlo.") from e


def leggi_titolo(titolo: str) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """«KPI MONITORING GAZEL OTTOBRE 2026» -> ("gazel", 2026, 10)."""
    t = " ".join(str(titolo or "").upper().split())
    m = re.search(r"KPI\s+MONITORING\s+(.+?)\s+(" + "|".join(MESI) + r")\s+(\d{4})", t)
    if not m:
        return None, None, None
    societa = ALIAS_SOCIETA.get(normalizza(m.group(1)))
    return societa, int(m.group(3)), MESI.index(m.group(2)) + 1


def _numero(v) -> Optional[float]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def leggi_dashboard(contenuto: bytes, nome_file: str = "") -> KPIImportato:
    """Legge il foglio DASHBOARD. Solleva ImportKPIError se il file non è
    leggibile o non sembra la Dashboard KPI; il resto sono avvisi."""
    wb = _apri(contenuto, nome_file)
    fogli = {normalizza(n): n for n in wb.sheetnames}
    if normalizza(FOGLIO) not in fogli:
        elenco = ", ".join(wb.sheetnames[:8]) + (" …" if len(wb.sheetnames) > 8 else "")
        raise ImportKPIError(
            f"Nel file non c'è il foglio «{FOGLIO}». Fogli trovati: {elenco}. "
            "Controlla di caricare la «Dashboard KPI» del mese.")
    ws = wb[fogli[normalizza(FOGLIO)]]

    celle = {}
    for riga in ws.iter_rows():
        for c in riga:
            if c.value is not None and str(c.value).strip() != "":
                celle[(c.row, c.column)] = c.value

    titolo = next((str(v) for (r, c), v in sorted(celle.items())
                   if "KPI" in str(v).upper() and "MONITORING" in str(v).upper()), "")
    societa, anno, mese = leggi_titolo(titolo)

    etichette = {normalizza(m.etichetta): m for m in kc.MISURE}
    prefissi = [(normalizza(m.etichetta), m) for m in kc.MISURE if m.prefisso]

    def misura_di(valore) -> Optional[kc.Misura]:
        if not isinstance(valore, str):
            return None
        n = normalizza(valore)
        if n in etichette:
            return etichette[n]
        return next((m for p, m in prefissi if n.startswith(p)), None)

    trovate: dict[str, tuple] = {}
    for (r, c), v in sorted(celle.items()):
        m = misura_di(v)
        if m is not None and m.codice not in trovate:
            trovate[m.codice] = (r, c, str(v))

    valori, testi, non_numerici = {}, {}, []
    for codice, (r, c, testo_etichetta) in trovate.items():
        valore = None
        for dr in range(1, MAX_RIGHE_SOTTO + 1):
            cella = celle.get((r + dr, c))
            if cella is None:
                continue
            if misura_di(cella) is not None:          # è già l'etichetta successiva
                break
            numero = _numero(cella)
            if numero is not None:
                valore = numero
                break
            if isinstance(cella, str) and cella.strip().startswith("#"):
                non_numerici.append((codice, cella.strip()))   # #DIV/0!, #N/D, #RIF!
                break
        valori[codice] = valore
        tra_parentesi = re.search(r"\(([^)]*)\)", testo_etichetta)
        if kc.PER_CODICE[codice].prefisso and tra_parentesi:
            testi[codice] = tra_parentesi.group(1).strip()
    mancanti = [m.codice for m in kc.MISURE if m.codice not in trovate]
    for codice in mancanti:
        valori[codice] = None

    if len(mancanti) > SOGLIA_MANCANTI * len(kc.MISURE):
        raise ImportKPIError(
            f"Il foglio «{ws.title}» non sembra la Dashboard KPI: riconosco solo "
            f"{len(kc.MISURE) - len(mancanti)} indicatori su {len(kc.MISURE)} "
            "(per esempio «EBITDA M -1», «SALES/BP TOTALE M», «CHURN PDP M»). "
            "Controlla di aver caricato il file giusto e che le etichette non siano state rinominate.")

    avvisi = []
    if not titolo:
        avvisi.append("Non trovo il titolo «KPI MONITORING <SOCIETÀ> <MESE> <ANNO>»: "
                      "scegli tu società e mese prima di salvare.")
    elif societa is None or anno is None:
        avvisi.append(f"Non riconosco società o mese dal titolo «{titolo}»: "
                      "scegli tu società e mese prima di salvare.")
    if mancanti:
        nomi = ", ".join(kc.PER_CODICE[c].etichetta for c in mancanti)
        avvisi.append(f"Indicatori non trovati nel foglio ({len(mancanti)}): {nomi}. "
                      "Si salvano come «dato mancante».")
    vuoti = [c for c, (r, cc, _) in trovate.items() if valori[c] is None
             and c not in {x for x, _ in non_numerici}]
    if vuoti:
        avvisi.append("Etichetta presente ma senza valore numerico sotto: "
                      + ", ".join(kc.PER_CODICE[c].etichetta for c in vuoti) + ".")
    if non_numerici:
        avvisi.append("Celle con errore di formula: " + ", ".join(
            f"{kc.PER_CODICE[c].etichetta} = {t}" for c, t in non_numerici)
            + ". Si salvano come «dato mancante»: correggi l'Excel e ricaricalo se servono.")

    return KPIImportato(societa=societa, anno=anno, mese=mese, titolo=titolo, valori=valori,
                        testi=testi, mancanti=mancanti, non_numerici=non_numerici,
                        avvisi=avvisi, sha256=hashlib.sha256(contenuto).hexdigest())


def righe_da_salvare(imp: KPIImportato, anno: int, mese: int) -> list[dict]:
    """Una riga per misura, con il mese di competenza (M o M-1)."""
    out = []
    for m in kc.MISURE:
        ac, mc = kc.competenza(anno, mese, m.rif)
        out.append({"codice": m.codice, "anno_comp": ac, "mese_comp": mc,
                    "valore": imp.valori.get(m.codice), "testo": imp.testi.get(m.codice, "")})
    return out
