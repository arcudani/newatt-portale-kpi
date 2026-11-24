"""
Dati FITTIZI per i test (nessun numero reale di Migliora nel repo).

* workbook_bp(): un BP Excel inventato con la STESSA struttura del BP v5
  (fogli, etichette, sezioni, colonne dei mesi con i totali annui
  intercalati, IRES/IRAP solo annuali, righe VAS gas etichettate "Power"),
  con numeri coerenti così che la quadratura con il Riepilogo torni;
* catalogo_seed(): il catalogo KPI letto dal seme SQL della migrazione
  bp002 (così i test verificano anche la coerenza catalogo <-> calcoli).
"""
from __future__ import annotations

import datetime as dt
import io
import re
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

ANNI = [2026, 2027, 2028, 2029, 2030]
INIZIO = (2026, 10)
Fn = Callable[[int, int], float]


def k(a: int, m: int) -> int:
    """Mesi di attività: 0 nel 2026 (avviamento), 1..48 dal 2027."""
    return 0 if a < 2027 else (a - 2027) * 12 + m


def _att(v: float) -> Fn:
    return lambda a, m: v if k(a, m) > 0 else 0.0


def _somma(*fs: Fn) -> Fn:
    return lambda a, m: sum(f(a, m) for f in fs)


def _cum(f: Fn) -> Fn:
    """Stock = somma cumulata dei flussi fino al mese (a, m) compreso."""
    def g(a, m):
        return sum(f(aa, mm) for aa in ANNI for mm in range(1, 13) if (aa, mm) <= (a, m))
    return g


def _annuo(f: Fn, a: int) -> float:
    return sum(f(a, m) for m in range(1, 13))


# ---------------------------------------------------------------- CE --------
RP = {"mat": lambda a, m: 100.0 * k(a, m), "qf": lambda a, m: 40.0 * k(a, m)}
RG = {"mat": lambda a, m: 50.0 * k(a, m), "qf": lambda a, m: 20.0 * k(a, m)}
CP = {"mat": lambda a, m: -60.0 * k(a, m), "qf": lambda a, m: -2.0 * k(a, m)}
CG = {"mat": lambda a, m: -30.0 * k(a, m), "qf": lambda a, m: -1.0 * k(a, m)}
ZERO: Fn = lambda a, m: 0.0  # noqa: E731
RIC_P, RIC_G = _somma(*RP.values()), _somma(*RG.values())
COS_P, COS_G = _somma(*CP.values()), _somma(*CG.values())
RICAVI, COSTI = _somma(RIC_P, RIC_G), _somma(COS_P, COS_G)
PM = _somma(RICAVI, COSTI)
PROVV = lambda a, m: -10.0 * k(a, m)  # noqa: E731
POINT = _att(-1.0)
PMN = _somma(PM, PROVV, POINT)
MKT = _att(-2.0)
NEWATT, IT = _att(-5.0), _att(-3.0)
SRV = _somma(NEWATT, IT)
SOFT = _att(-1.0)
VA = _somma(PMN, MKT, SRV, SOFT)
SAL, ONE, TFR = _att(-4.0), _att(-1.0), _att(-0.5)
PERS = _somma(SAL, ONE, TFR)
EBITDA = _somma(VA, PERS)
PERDITE = lambda a, m: -2.0 if a >= 2027 and m == 1 else 0.0  # noqa: E731
EBIT = _somma(EBITDA, PERDITE)


def ires(a: int) -> float:
    return -0.24 * _annuo(EBIT, a)


def irap(a: int) -> float:
    return -0.039 * _annuo(EBIT, a)


# ------------------------------------------------------------- DRIVER -------
GRUPPI = {("Retail", "Power"): 70.0, ("Retail", "Gas"): 30.0,
          ("Business", "Power"): 7.0, ("Business", "Gas"): 3.0}
PROD = {g: _att(v) for g, v in GRUPPI.items()}
SO = {g: (lambda a, m, v=v: -(v / 70.0) * 0.5 * k(a, m)) for g, v in GRUPPI.items()}
STOCK = {g: _cum(_somma(PROD[g], SO[g])) for g in GRUPPI}
PDP_TOT = _somma(*STOCK.values())
MWH = {g: (lambda a, m, g=g: 0.2 * STOCK[g](a, m)) for g in GRUPPI}
VAS_PROD = {"Power": _att(20.0), "Gas": _att(10.0)}
VAS_SO = {"Power": lambda a, m: -0.1 * k(a, m), "Gas": lambda a, m: -0.05 * k(a, m)}
VAS_STOCK = {c: _cum(_somma(VAS_PROD[c], VAS_SO[c])) for c in ("Power", "Gas")}
QUOTE = {"Assicurazione": 20 / 45, "Manutenzione": 15 / 45, "Telecomunicazioni": 10 / 45}
VAS_PRODOTTO = {(c, p): (lambda a, m, c=c, q=q: VAS_STOCK[c](a, m) * q)
                for c in ("Power", "Gas") for p, q in QUOTE.items()}
VAS_TOT = _somma(*VAS_PRODOTTO.values())
BASE_FTE = _somma(PDP_TOT, VAS_TOT)


def _mesi_da(inizio):
    return [(a, m) for a in ANNI for m in range(1, 13) if (a, m) >= inizio]


def _scrivi(ws, righe, col0: int = 3, inizio=(2026, 1), totali: bool = True) -> None:
    """Intestazione in riga 2 (date dei mesi + anno intero dopo ogni dicembre,
    come il BP), righe da riga 4. Ogni riga: (celle etichetta, funzione, annuo)."""
    mappa, col = [], col0
    for a in ANNI:
        for m in range(1, 13):
            if (a, m) < inizio:
                continue
            ws.cell(row=2, column=col + 1, value=dt.datetime(a, m, 1))
            mappa.append((col, (a, m)))
            col += 1
        if totali:
            ws.cell(row=2, column=col + 1, value=a)
            mappa.append((col, a))
            col += 1
    for r, (etichette, f, annuo) in enumerate(righe, start=4):
        for j, t in enumerate(etichette):
            if t is not None:
                ws.cell(row=r, column=j + 1, value=t)
        if f is None:
            continue
        for c, chiave in mappa:
            if isinstance(chiave, tuple):
                v = f(*chiave)
            else:   # totale annuo: solo le celle numeriche (come SOMMA in Excel)
                v = annuo(chiave) if annuo else sum(
                    x for x in (f(chiave, mm) for mm in range(1, 13) if (chiave, mm) >= inizio)
                    if isinstance(x, (int, float)))
            if v is not None:
                ws.cell(row=r, column=c + 1, value=v)


def _ce(escludi: set) -> list:
    R = []

    def riga(et, f=None, annuo=None, b=None):
        if et not in escludi:
            R.append(((et, b), f, annuo))

    riga("Power - Pass-Through")
    riga("N° POD fatturati", ZERO, b="N.")
    riga("Power")
    riga("Ricavi Materia Prima", RP["mat"], b="EUR")
    riga("Ricavi Quota Fissa", RP["qf"], b="EUR")
    for et in ("Ricavi Pratiche", "Ricavi Oneri Passanti", "Ricavi Sopravvenienze Attive"):
        riga(et, ZERO, b="EUR")
    riga("Totale Ricavi Power", RIC_P, b="EUR")
    riga("Costi Materia Prima", CP["mat"], b="EUR")
    riga("Costi Quota Fissa", CP["qf"], b="EUR")
    riga("Costi Oneri Passanti", ZERO, b="EUR")
    riga("Costi Sopravvenienze Passive", ZERO, b="EUR")
    riga("Totale Costi Power", COS_P, b="EUR")
    riga("Primo Margine Variabile", ZERO, b="EUR")
    riga("Gas")
    riga("Ricavi Materia Prima", RG["mat"], b="EUR")
    riga("Ricavi Quota Fissa", RG["qf"], b="EUR")
    for et in ("Ricavi Pratiche", "Ricavi Oneri Passanti", "Ricavi Sopravvenienze Attive"):
        riga(et, ZERO, b="EUR")
    riga("Totale Ricavi Gas", RIC_G, b="EUR")
    riga("Costi Materia Prima", CG["mat"], b="EUR")
    riga("Costi Quota Fissa", CG["qf"], b="EUR")
    riga("Costi Oneri Passanti", ZERO, b="EUR")
    riga("Costi Sopravvenienze Passive", ZERO, b="EUR")
    riga("Totale Costi Gas", COS_G, b="EUR")
    riga("ALTRE VENDITE", ZERO)
    riga("TOTALI PRIMO MARGINE")
    riga("Totale Ricavi", RICAVI, b="EUR")
    riga("Totale Costi", COSTI, b="EUR")
    riga("Primo Margine Lordo ", PM, b="EUR")
    riga("Provvigioni", PROVV, b="EUR")
    riga("Spese Point", POINT, b="EUR")
    riga("Primo Margine Netto Totale", PMN, b="EUR")
    riga("PM Lordo su Totale Ricavi", lambda a, m: "#DIV/0!" if k(a, m) == 0 else 0.5)
    riga("Costi Marketing e Commerciali (non variabili) ", MKT)
    riga("Viaggi e rimborsi spese", ZERO)
    riga("Contratti di Servizio Specifici", lambda a, m: None, lambda a: None)
    riga("Altri costi Marketing e commerciali", MKT)
    riga("Costi Servizi Generali", SRV)
    riga("Contratto di Servizio Newatt", NEWATT)
    for et in ("Assicurazioni e Fidejussioni", "Spese Legali e Amministrative",
               "Studio Paghe, Revisore, Commercialista", "Spese Amministrative Straordinarie"):
        riga(et, ZERO)
    riga("Spese Gestione IT", IT)
    for et in ("Pasti, Soggiorni, Buoni Pasto", "Note Spese Amministratori", "Costo CDA",
               "Spese di Sede", "Altri costi per servizi", "Oneri bancari / SDD",
               "Oneri bancari altri costi"):
        riga(et, ZERO)
    riga("Costi God. Beni di Terzi", SOFT)
    for et in ("Affitto", "Auto/veicoli", "Altri Noleggi"):
        riga(et, ZERO)
    riga("Lic. Software", SOFT)
    riga("VALORE AGGIUNTO", VA)
    riga("Costo Personale", PERS)
    riga("Salari e Stipendi", SAL)
    riga("Oneri Sociali", ONE)
    riga("TFR", TFR)
    riga("EBITDA", EBITDA)
    riga("Ammortamenti Immateriali", ZERO)
    riga("Ammortamenti Materiali", ZERO)
    riga("Perdite su Crediti", PERDITE)
    riga("Accantonamento Rischi su Crediti", ZERO)
    riga("Accantonamento Altri Rischi", ZERO)
    riga("Oneri div. di gestione (incluse sopravv. Passive)", ZERO)
    riga("EBIT", EBIT)
    riga("Proventi Finanziari", ZERO)
    riga("Interessi Attivi su Depositi Bancari", ZERO)
    riga("Interessi Attivi di Mora", ZERO)
    riga("Oneri Finanziari", ZERO)
    for et in ("Interessi Passivi Bancari", "Interessi Passivi su Mutui",
               "Interessi Passivi su Finanziamenti", "Interessi Passivi su c/Anticipi",
               "Interessi Passivi verso Fornitori"):
        riga(et, ZERO)
    riga("EBT", EBIT)
    riga("IRES 24%", lambda a, m: None, ires)
    riga("IRAP 3,9%", lambda a, m: None, irap)
    riga("Risultato Netto", EBIT, lambda a: _annuo(EBIT, a) + ires(a) + irap(a))
    return R


def _sviluppo_agenti() -> list:
    R = [(("Sportelli", "Apertura Sportelli"), lambda a, m: 1.0 if (a, m) >= INIZIO else 0.0, None),
         (("Produzione", "Produzione Totale"), _somma(*PROD.values()), None)]
    R += [((None, f"Prod. {c} {s}"), PROD[(s, c)], None) for s, c in GRUPPI]
    R.append((("Switch-out", "Switch-out Totale"), _somma(*SO.values()), None))
    R += [((None, f"Switch-out {c} {s}"), SO[(s, c)], None) for s, c in GRUPPI]
    R.append((("PdP", "PdP Totali"), PDP_TOT, None))
    nomi = {("Retail", "Power"): "POD Retail", ("Retail", "Gas"): "PDR Retail",
            ("Business", "Power"): "POD Business", ("Business", "Gas"): "PDR Business"}
    R += [((None, nomi[g]), STOCK[g], None) for g in GRUPPI]
    R += [((None, f"MWh {c} {s}"), MWH[(s, c)], None) for s, c in GRUPPI]
    return R


def _sviluppo_vas() -> list:
    R = [(("Produzione", "Produzione Totale"), _somma(*VAS_PROD.values()), None)]
    R += [((None, f"Prod. {c} Retail"), VAS_PROD[c], None) for c in ("Power", "Gas")]
    R.append((("Switch-out", "Switch-out Totale"), _somma(*VAS_SO.values()), None))
    R += [((None, f"Switch-out {c} Retail"), VAS_SO[c], None) for c in ("Power", "Gas")]
    R += [((None, f"{pref} Retail {p}"), VAS_PRODOTTO[(c, p)], None)
          for pref, c in (("POD", "Power"), ("PDR", "Gas")) for p in QUOTE]
    return R


def _pm_vas() -> list:
    R = []
    for c in ("Power", "Gas"):
        R.append(((None, f"Margine Totale {c} Retail"), ZERO, None))
        # righe gas etichettate "Power" come nel BP v5
        R += [((None, f"Margine Fisso Power {p}"),
               (lambda a, m, c=c, p=p: 10.0 * VAS_PRODOTTO[(c, p)](a, m)), None) for p in QUOTE]
    return R


def _pm_agenti() -> list:
    R = [((None, f"Margine Totale {c} {s}"), (lambda a, m, g=(s, c): 5.0 * STOCK[g](a, m)), None)
         for s, c in GRUPPI]
    R.append((("Provvigioni", "Provvigioni Totali"), ZERO, None))
    R += [((None, f"Provvigioni {c} {s}"), (lambda a, m, g=(s, c): -95.0 * PROD[g](a, m)), None)
          for s, c in GRUPPI]
    R.append((("Rinnovi", "Provvigioni Totali"), ZERO, None))
    # Power Retail: rinnovi positivi ad agosto e dicembre, tanto da rendere
    # positivo il totale del canale (il rilievo aperto del BP v5)
    def _rinnovo(a, m, pos):
        if pos:
            return (2.0 if m in (8, 12) else -0.5) * k(a, m)
        return -0.1 * k(a, m)
    R += [((None, f"Provvigioni {c} {s}"),
           (lambda a, m, pos=(s, c) == ("Retail", "Power"): _rinnovo(a, m, pos)), None)
          for s, c in GRUPPI]
    return R


def _fte_cc() -> list:
    return [((None, "PdP attivi totali"), BASE_FTE, None),
            ((None, "Chiamate gestite da operatore"), lambda a, m: 0.1 * BASE_FTE(a, m), None),
            ((None, "Contatti scritti gestiti da operatore"), lambda a, m: 0.07 * BASE_FTE(a, m), None),
            ((None, "Reclami gestiti da operatore"), lambda a, m: 0.005 * BASE_FTE(a, m), None),
            ((None, "FTE necessari"), lambda a, m: BASE_FTE(a, m) / 1000, None)]


def _fte_op() -> list:
    return [((None, "Fatture emesse"), BASE_FTE, None),
            ((None, "Pratiche switch-in"), _somma(*PROD.values()), None),
            ((None, "Pratiche di cessazione"), lambda a, m: -_somma(*SO.values())(a, m), None),
            ((None, "Volture/subentri gestiti"), lambda a, m: 0.004 * BASE_FTE(a, m), None),
            ((None, "Pratiche incasso gestite"), lambda a, m: 0.02 * BASE_FTE(a, m), None),
            ((None, "FTE necessari"), lambda a, m: BASE_FTE(a, m) / 5000, None)]


def _personale() -> list:
    ruoli = [("Servizio clienti", lambda a, m: (2.0 if a >= 2029 else 1.0) if k(a, m) else 0.0),
             ("Operation", _att(1.0)), ("Operation VAS", _att(1.0)), ("Fatturazione", _att(1.0)),
             ("Credito", _att(1.0)), ("Commerciale", ZERO)]
    R = [((et,), f, None) for et, f in ruoli]
    R.append((("Riepilogo Livelli",), None, None))
    R += [((et,), f, None) for et, f in (("Liv. Alto", ZERO), ("Liv. Medio", _att(5.0)),
                                         ("Apprendistato", ZERO), ("Tirocinio", ZERO))]
    R.append((("Salari e Stipendi", "RAL"), None, None))
    R += [((et,), f, None) for et, f in (("Alto", ZERO), ("Medio", SAL),
                                         ("Apprendistato", ZERO), ("Tirocinio", ZERO))]
    return R


def _riepilogo(variazioni: dict) -> list:
    dic = lambda f: (lambda a: f(a, 12))  # noqa: E731
    righe = [
        ("Fatturato Totale", lambda a: _annuo(RICAVI, a)),
        ("Costi per Approvvigionamento", lambda a: _annuo(COSTI, a)),
        ("Primo Margine Lordo", lambda a: _annuo(PM, a)),
        ("Provvigioni", lambda a: _annuo(PROVV, a)),
        ("Costi Marketing & Comunicazione", lambda a: _annuo(MKT, a)),
        ("Costi Servizi Generali", lambda a: _annuo(SRV, a)),
        ("Costi per God. Beni di Terzi", lambda a: _annuo(SOFT, a)),
        ("Costo per il Personale Operativo", lambda a: _annuo(PERS, a)),
        ("EBITDA", lambda a: _annuo(EBITDA, a)),
        ("Perdite su Crediti e Fondo Rischi", lambda a: _annuo(PERDITE, a)),
        ("EBIT", lambda a: _annuo(EBIT, a)),
        ("IRES", ires), ("IRAP", irap),
        ("Risultato Netto", lambda a: _annuo(EBIT, a) + ires(a) + irap(a)),
        ("N° PdP", dic(PDP_TOT)),
        ("MWH Power Venduti", lambda a: sum(_annuo(MWH[g], a) for g in GRUPPI if g[1] == "Power")),
        ("MWH Gas Venduti", lambda a: sum(_annuo(MWH[g], a) for g in GRUPPI if g[1] == "Gas")),
        ("di cui n° POD VAS", dic(VAS_STOCK["Power"])),
        ("di cui n° PDR VAS", dic(VAS_STOCK["Gas"])),
    ]
    out = [["Business Plan", None, None, *ANNI]]
    for et, f in righe:
        out.append([et, None, None,
                    *[f(a) * variazioni.get((et, a), 1.0) for a in ANNI]])
    return out


def workbook_bp(variazioni: Optional[dict] = None, escludi: Optional[set] = None) -> bytes:
    """BP Excel fittizio (bytes). variazioni: {(etichetta Riepilogo, anno): fattore}
    per simulare una quadratura KO; escludi: etichette del CE da togliere."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Riepilogo Business Plan")
    for riga in _riepilogo(variazioni or {}):
        ws.append(riga)
    _scrivi(wb.create_sheet("Risultato Mensile"), _ce(escludi or set()))
    _scrivi(wb.create_sheet("CdV - Sviluppo Agenti"), _sviluppo_agenti())
    _scrivi(wb.create_sheet("CdV - Sviluppo VAS"), _sviluppo_vas())
    _scrivi(wb.create_sheet("CdV - Calcolo PM VAS"), _pm_vas())
    _scrivi(wb.create_sheet("CdV - Calcolo PM Agenti"), _pm_agenti())
    _scrivi(wb.create_sheet("IPO - FTE Customer Care"), _fte_cc(), inizio=INIZIO, totali=False)
    _scrivi(wb.create_sheet("IPO - FTE Operation"), _fte_op(), inizio=INIZIO, totali=False)
    _scrivi(wb.create_sheet("IPO - Personale"), _personale(), col0=4)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------ CATALOGO ------

def _campi_sql(tupla: str) -> list:
    """Divide i campi di una tupla SQL (stringhe con '' come escape)."""
    campi, cur, in_str, i = [], "", False, 0
    while i < len(tupla):
        ch = tupla[i]
        if in_str:
            if ch == "'" and i + 1 < len(tupla) and tupla[i + 1] == "'":
                cur += "'"
                i += 1
            elif ch == "'":
                in_str = False
            else:
                cur += ch
        elif ch == "'":
            in_str, cur = True, cur + "\x00"   # marcatore: è una stringa
        elif ch == ",":
            campi.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    campi.append(cur.strip())
    out = []
    for c in campi:
        c = c.split("::")[0].strip() if not c.startswith("\x00") else c   # null::numeric
        if c.startswith("\x00"):
            out.append(c[1:])
        elif c.lower() == "null":
            out.append(None)
        else:
            out.append(float(c) if "." in c else int(c))
    return out


def _tuple_sql(corpo: str) -> list:
    """Tuple di una clausola VALUES (stringhe con '' come escape)."""
    tuple_, livello, cur, in_str, i = [], 0, "", False, 0
    while i < len(corpo):
        ch = corpo[i]
        if in_str:
            cur += ch
            if ch == "'":
                if corpo[i + 1:i + 2] == "'":      # apice raddoppiato = escape
                    cur += "'"
                    i += 1
                else:
                    in_str = False
        elif ch == "'":
            in_str = True
            cur += ch
        elif ch == "(":
            livello += 1
            if livello > 1:
                cur += ch
            else:
                cur = ""
        elif ch == ")":
            livello -= 1
            if livello > 0:
                cur += ch
            else:
                tuple_.append(cur)
        elif livello >= 1:
            cur += ch
        i += 1
    return tuple_


def _sql(nome: str) -> str:
    testo = (Path(__file__).resolve().parent / "migrations" / nome).read_text(encoding="utf-8")
    return "\n".join(r for r in testo.splitlines() if not r.lstrip().startswith("--"))


def _insert_sql(testo: str) -> pd.DataFrame:
    """Righe di un INSERT ... VALUES ... ON CONFLICT (colonne dal suo elenco)."""
    colonne = [c.strip() for c in testo.split("(", 1)[1].split(")", 1)[0].split(",")]
    basso = testo.lower()
    corpo = testo[basso.index("values") + len("values"):basso.rindex("on conflict")]
    return pd.DataFrame([dict(zip(colonne, _campi_sql(t))) for t in _tuple_sql(corpo)])


def _update_values_sql(testo: str) -> dict:
    """{codice: tupla} dalla clausola UPDATE ... FROM (VALUES ...) AS v(...)."""
    basso = testo.lower()
    corpo = testo[basso.index("from (values") + len("from (values"):basso.index(") as v(")]
    return {r[0]: r for r in (_campi_sql(t) for t in _tuple_sql(corpo))}


def _applica_righe_sql(df: pd.DataFrame, testo: str) -> pd.DataFrame:
    """Migrazione di soli dati nel formato di bp004: INSERT (nuove righe,
    facoltativo), UPDATE ... SET definizione = '...' WHERE codice = '...'
    (facoltativo), UPDATE ... FROM (VALUES (codice, livello, vista, ambito,
    ordine, drill)), DELETE ... WHERE codice IN (...)."""
    testa = testo.split("update public.", 1)[0]
    if "insert into" in testa.lower():
        nuove = _insert_sql(testa)
        nuove = nuove[~nuove["codice"].isin(df["codice"])].assign(frequenza="mensile", ambito="")
        df = pd.concat([df, nuove], ignore_index=True)
    for definizione, codice in re.findall(
            r"update public\.bp_kpi_catalogo set definizione = '((?:[^']|'')*)' "
            r"where codice = '([^']+)'", testo):
        df.loc[df["codice"] == codice, "definizione"] = definizione.replace("''", "'")
    for codice, (_, livello, vista, ambito, ordine, drill) in _update_values_sql(testo).items():
        df.loc[df["codice"] == codice, ["livello", "vista", "ambito", "ordine", "drill"]] = (
            livello, vista, ambito, ordine, drill)
    via = re.search(r"delete from public\.bp_kpi_catalogo where codice in \(([^)]*)\)", testo)
    return df[~df["codice"].isin(re.findall(r"'([^']+)'", via.group(1)))]


def catalogo_seed() -> pd.DataFrame:
    """Catalogo KPI dal seme SQL, applicando le migrazioni in ordine: bp002
    (righe), bp003 (ambiti, ordine, benchmark), poi bp004-bp007 (KPI
    di primo livello del Cruscotto: nuove righe, spostamenti, cancellazioni).
    Così i test vedono lo stesso catalogo del DB."""
    df = _insert_sql(_sql("bp002_catalogo_kpi.sql"))
    df["frequenza"] = "mensile"

    agg = _update_values_sql(_sql("bp003_ambiti_benchmark.sql"))
    df["ambito"] = df["codice"].map(lambda c: agg.get(c, [None, ""])[1] or "")
    df["ordine"] = [agg[c][2] if c in agg else o for c, o in zip(df["codice"], df["ordine"])]
    for i, nome in ((3, "bench_min"), (4, "bench_max")):
        df[nome] = df["codice"].map(lambda c, i=i: agg.get(c, [None] * 5)[i])

    for nome in ("bp004_cruscotto_kpi_l1.sql", "bp005_clt_unico.sql", "bp006_churn_unico.sql",
                 "bp007_sales_plan_unico.sql"):
        df = _applica_righe_sql(df, _sql(nome))

    for c in ("soglia_gialla", "soglia_rossa", "bench_min", "bench_max"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(["livello", "vista", "ordine"], ignore_index=True)


def versioni_prova(stato_b: str = "bozza", quadratura: Optional[list] = None) -> pd.DataFrame:
    """Due versioni fittizie: 1 approvata, 2 (scenario) nello stato indicato."""
    q = quadratura if quadratura is not None else [
        {"grandezza": "Ricavi", "anno": 2027, "excel": 1.0, "motore": 1.0, "delta": 0.0,
         "delta_pct": 0.0, "ok": True}]
    ora = pd.Timestamp("2026-09-10 10:00", tz="UTC")
    return pd.DataFrame([
        {"id": 1, "nome": "BP prova", "descrizione": "fittizio", "stato": "approvata",
         "origine": "prova.xlsx", "quadratura_ok": True, "quadratura": q, "creata_da": "test",
         "created_at": ora, "stato_da": "test", "stato_il": ora},
        {"id": 2, "nome": "Scenario prova", "descrizione": "fittizio", "stato": stato_b,
         "origine": "prova.xlsx", "quadratura_ok": True, "quadratura": q, "creata_da": "test",
         "created_at": ora, "stato_da": "", "stato_il": None},
    ])


# ------------------------------------------------------- DASHBOARD KPI -----

def valori_kpi_prova(fattore: float = 1.0) -> dict:
    """Valori FITTIZI (ordini di grandezza plausibili, nessun dato reale)
    per ogni misura del foglio DASHBOARD."""
    import kpi_catalogo as kc
    base = {"€": 250_000.0, "%": 0.05, "N.": 4_000.0, "MWh": 9_000.0, "mesi": 12.0,
            "€/cliente": 80.0}
    return {m.codice: round(base[m.unita] * (1 + i / 50) * fattore, 6)
            for i, m in enumerate(kc.MISURE)}


def workbook_kpi(titolo: str = "KPI MONITORING GAZEL OTTOBRE 2026",
                 valori: Optional[dict] = None, togli: tuple = (), errori: Optional[dict] = None,
                 vuoti: tuple = (), foglio: str = "DASHBOARD", altri_fogli: tuple = ("CRM FORNITURE",)) -> bytes:
    """Excel «Dashboard KPI» fittizio con la stessa grammatica del foglio
    vero: titolo in A1, tre colonne (A, D, G), etichetta e valore sotto,
    qualche riga di descrizione in mezzo. togli = misure senza etichetta,
    errori = {codice: "#DIV/0!"}, vuoti = etichetta senza valore."""
    import openpyxl
    import kpi_catalogo as kc

    valori = valori if valori is not None else valori_kpi_prova()
    errori = errori or {}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = foglio
    ws["A1"] = titolo
    colonne = {"Finanziario": 1, "Vendite": 4, "Cliente": 7}
    riga = {c: 6 for c in colonne.values()}
    per_misura = {}
    for t in kc.TESSERE:
        for c in (*t.misure, *t.commodity.values(), *(x for _, x in t.dettaglio), *t.quota.values()):
            per_misura.setdefault(c, colonne[t.ambito])
    for m in kc.MISURE:
        if m.codice in togli:
            continue
        col = per_misura[m.codice]
        r = riga[col]
        etichetta = m.etichetta + (" (febbraio 2026)" if m.codice == "CHURN_MAX" else
                                   " (gennaio 2026)" if m.codice == "CHURN_MIN" else "")
        ws.cell(r, col, etichetta)
        if m.codice in ("SALES_BP", "CHURN", "LTV"):          # riga di descrizione come nel vero
            r += 1
            ws.cell(r, col, "Totale energia elettrica e gas naturale")
        if m.codice in errori:
            ws.cell(r + 1, col, errori[m.codice])
        elif m.codice not in vuoti:
            ws.cell(r + 1, col, valori[m.codice])
        riga[col] = r + 3
    for nome in altri_fogli:
        wb.create_sheet(nome)["A1"] = "dati di clienti (non letti)"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def valori_kpi_df(societa: str = "gazel", mesi=((2026, 9, 0.9), (2026, 10, 1.0))) -> pd.DataFrame:
    """Come kpi_dati.carica_valori: valori correnti di più report fittizi."""
    import kpi_import as ki
    righe = []
    for cid, (anno, mese, fattore) in enumerate(mesi, start=1):
        imp = ki.leggi_dashboard(workbook_kpi(valori=valori_kpi_prova(fattore)), "prova.xlsx")
        for r in ki.righe_da_salvare(imp, anno, mese):
            righe.append({"societa": societa, "anno": anno, "mese": mese, "caricamento_id": cid,
                          "caricato_il": pd.Timestamp("2026-11-24 09:00", tz="UTC"),
                          "caricato_da": "test", **r})
    return pd.DataFrame(righe)


def caricamenti_prova(societa: str = "gazel") -> pd.DataFrame:
    return pd.DataFrame([{"id": i, "societa": societa, "anno": 2026, "mese": m, "titolo_excel": "",
                          "file_nome": "prova.xlsx", "n_valori": 37, "caricato_da": "test",
                          "caricato_il": pd.Timestamp("2026-11-24", tz="UTC"), "annullato": False,
                          "note": ""} for i, m in ((1, 9), (2, 10))])
