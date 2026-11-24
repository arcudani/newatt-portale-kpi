"""
Motore dei KPI e delle aggregazioni del Controllo BP Migliora — funzioni
PURE su DataFrame (nessun DB, nessuno Streamlit), testate offline.

Ogni KPI del catalogo (bp_kpi_catalogo.codice) ha qui una funzione
registrata con @kpi: riceve i dati della versione, il periodo e i dati della
versione di riferimento (A) e restituisce una Misura. Un codice del catalogo
senza funzione viene mostrato come "calcolo non ancora implementato".

Convenzioni:
  * i costi nel CE hanno segno negativo (come nel BP); nelle tessere i costi
    si mostrano in valore assoluto con direzione "più basso è meglio";
  * rapporti e unitari: n.d. con motivo se il denominatore è zero e sempre
    nel periodo di avviamento (ott-dic 2026, blueprint §8);
  * "PdP" = POD + PDR del canale Agenti (nel BP v5 i PdP del canale VAS
    sono un "di cui": vedi Nota ricostruzione VAS);
  * unitari annualizzati: valore del periodo × 12 / mesi del periodo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

import bp_import as bi
import formato as fmt

ANNO_AVVIAMENTO = 2026
MOTIVO_AVVIAMENTO = "avviamento (ott-dic 2026)"

# Voci che compongono i costi operativi del Cost-to-Serve (definizione BP:
# costi generali + personale operativo; esclusi provvigioni e spese point).
VOCI_CTS = ("costi_marketing", "costi_servizi", "costi_god_beni", "personale")
VOCI_COSTI_GENERALI = ("costi_marketing", "costi_servizi", "costi_god_beni")
# Fra primo margine lordo ed EBITDA: Cost-to-Serve + costi commerciali.
VOCI_COSTO_CLIENTE = (*VOCI_CTS, "provvigioni", "spese_point")
RUOLI_OPERATION = ("Operation", "Operation VAS", "Fatturazione", "Credito")


@dataclass(frozen=True)
class Periodo:
    anno: int
    mese_a: int = 12
    mese_da: int = 1

    @property
    def mesi(self) -> list[int]:
        return list(range(self.mese_da, self.mese_a + 1))

    @property
    def n_mesi(self) -> int:
        return self.mese_a - self.mese_da + 1

    def anno_intero(self) -> "Periodo":
        return Periodo(self.anno, 12, 1)

    @property
    def avviamento(self) -> bool:
        return self.anno <= ANNO_AVVIAMENTO


@dataclass
class Badge:
    """Etichetta sotto il numero della tessera (stile DeD): tendenza, avviso
    o insight. Tono: buono | attenzione | cattivo | neutro."""
    testo: str
    tono: str = "neutro"


@dataclass
class Misura:
    valore: Optional[float]
    motivo: str = ""                      # perché n.d.
    sub: str = ""                         # una riga di contesto
    serie: Optional[list] = None          # 12 valori mensili (sparkline)
    nota: str = ""                        # es. valore secondo la riga BP
    avvisi: list = field(default_factory=list)   # Badge specifici del KPI
    # dettaglio per commodity dentro il riquadro: {"Power": "26,5%", "Gas": "26,3%"}
    commodity: dict = field(default_factory=dict)
    # stessi valori in numero (unità del KPI), per lo slicer Commodity
    commodity_valori: dict = field(default_factory=dict)
    rif: str = ""                         # riferimento del riquadro («Rif. …»)


# =============================================================================
# Accesso ai dati di una versione
# =============================================================================

class Dati:
    """CE e driver di UNA versione, indicizzati per lookup rapidi."""

    def __init__(self, ce: pd.DataFrame, drv: pd.DataFrame):
        self.ce = ce
        self.drv = drv
        self._ce = ({(v, int(a), int(m)): float(i) for v, a, m, i in
                     ce[["voce", "anno", "mese", "importo"]].itertuples(index=False)}
                    if not ce.empty else {})
        self.anni = sorted({int(a) for a in ce["anno"].unique()}) if not ce.empty else []

    @property
    def vuota(self) -> bool:
        return not self._ce

    # ---- CE ----
    def voce(self, codice: str, p: Periodo) -> float:
        return sum(self._ce.get((codice, p.anno, m), 0.0) for m in p.mesi)

    def voci(self, codici, p: Periodo) -> float:
        return sum(self.voce(c, p) for c in codici)

    def voce_mensile(self, codice: str, anno: int) -> list[float]:
        return [self._ce.get((codice, anno, m), 0.0) for m in range(1, 13)]

    # ---- Driver ----
    def _filtro(self, driver: str, **dims) -> pd.DataFrame:
        d = self.drv[self.drv["driver"] == driver]
        for k, v in dims.items():
            d = d[d[k].isin(v)] if isinstance(v, (list, tuple, set)) else d[d[k] == v]
        return d

    def mensile(self, driver: str, anno: int, **dims) -> list[float]:
        d = self._filtro(driver, **dims)
        d = d[d["anno"] == anno].groupby("mese")["valore"].sum()
        return [float(d.get(m, 0.0)) for m in range(1, 13)]

    def flusso(self, driver: str, p: Periodo, **dims) -> float:
        serie = self.mensile(driver, p.anno, **dims)
        return sum(serie[m - 1] for m in p.mesi)

    def stock(self, driver: str, anno: int, mese: int, **dims) -> float:
        if mese == 0:
            anno, mese = anno - 1, 12
        return self.mensile(driver, anno, **dims)[mese - 1]

    def stock_medio(self, driver: str, p: Periodo, **dims) -> float:
        serie = self.mensile(driver, p.anno, **dims)
        vals = [serie[m - 1] for m in p.mesi]
        return sum(vals) / len(vals) if vals else 0.0

    def ha_driver(self, driver: str) -> bool:
        return bool((self.drv["driver"] == driver).any()) if not self.drv.empty else False


def dati_vuoti() -> Dati:
    return Dati(pd.DataFrame(columns=["voce", "anno", "mese", "importo"]),
                pd.DataFrame(columns=["driver", *bi.DIMENSIONI, "anno", "mese", "valore"]))


def anno_default(d: Dati, oggi_anno: int) -> int:
    """Anno corrente se ha ricavi, altrimenti il primo anno con ricavi."""
    if d.vuota:
        return oggi_anno
    con_ricavi = [a for a in d.anni if d.voce("ricavi", Periodo(a)) > 0]
    if oggi_anno in con_ricavi:
        return oggi_anno
    return con_ricavi[0] if con_ricavi else d.anni[0]


# =============================================================================
# Helper di calcolo
# =============================================================================

def rapporto(num: float, den: float, p: Periodo, motivo_zero: str) -> Misura:
    if p.avviamento:
        return Misura(None, MOTIVO_AVVIAMENTO)
    if den is None or abs(den) < 1e-9:
        return Misura(None, motivo_zero)
    return Misura(num / den)


def _annualizza(p: Periodo) -> float:
    return 12 / p.n_mesi


def _pdp(d: Dati, anno: int, mese: int, **dims) -> float:
    return d.stock("pdp_attivi", anno, mese, canale="Agenti", **dims)


def _pdp_medi(d: Dati, p: Periodo) -> float:
    return d.stock_medio("pdp_attivi", p, canale="Agenti")


def _serie_pdp(d: Dati, anno: int) -> list[float]:
    return d.mensile("pdp_attivi", anno, canale="Agenti")


CALCOLI: dict[str, Callable[[Dati, Periodo, Dati], Misura]] = {}


def kpi(*codici: str):
    def reg(f):
        for c in codici:
            CALCOLI[c] = f
        return f
    return reg


def calcola(codice: str, d: Dati, p: Periodo, rif: Optional[Dati] = None) -> Optional[Misura]:
    """Misura del KPI; None se il codice non ha (ancora) un calcolo."""
    f = CALCOLI.get(codice)
    if f is None:
        return None
    if d.vuota:
        return Misura(None, "nessun dato per la versione")
    return f(d, p, rif or d)


# =============================================================================
# KPI economici
# =============================================================================

@kpi("L3_RICAVI", "V2_FATTURATO")
def _ricavi(d, p, rif):
    return Misura(d.voce("ricavi", p), serie=d.voce_mensile("ricavi", p.anno))


def _sub_pct_ricavi(d, p, voce, testo) -> str:
    r = rapporto(d.voce(voce, p), d.voce("ricavi", p), p, "ricavi = 0")
    if r.valore is None:
        return f"% sui ricavi n.d. — {r.motivo}"
    return f"{fmt.pct(r.valore)} {testo}"


@kpi("L3_EBITDA", "V2_EBITDA")
def _ebitda(d, p, rif):
    return Misura(d.voce("ebitda", p), sub=_sub_pct_ricavi(d, p, "ebitda", "dei ricavi"),
                  serie=d.voce_mensile("ebitda", p.anno))


@kpi("L3_UTILE")
def _utile(d, p, rif):
    sub = _sub_pct_ricavi(d, p, "risultato_netto", "dei ricavi")
    if p.mese_a < 12:
        sub += " · imposte dell'anno imputate a dicembre"
    return Misura(d.voce("risultato_netto", p), sub=sub,
                  serie=d.voce_mensile("risultato_netto", p.anno))


@kpi("L3_FORECAST")
def _forecast(d, p, rif):
    fy = p.anno_intero()
    return Misura(d.voce("ebitda", fy),
                  sub="= BP dell'anno: nessun consuntivo caricato (fase 3)",
                  serie=d.voce_mensile("ebitda", p.anno))


@kpi("V2_COSTO_APPR")
def _costo_appr(d, p, rif):
    power = -d.voce("appr_power", p)
    gas = -d.voce("appr_gas", p)
    return Misura(-d.voce("costi_appr", p),
                  sub=f"Power {fmt.eur_compatto(power)} · Gas {fmt.eur_compatto(gas)}",
                  serie=[-v for v in d.voce_mensile("costi_appr", p.anno)])


@kpi("V2_PM_PCT")
def _pm_pct(d, p, rif):
    m = rapporto(d.voce("pm_lordo", p), d.voce("ricavi", p), p, "ricavi = 0")
    m.sub = f"PM lordo {fmt.eur_compatto(d.voce('pm_lordo', p))}"
    return m


@kpi("V2_PROVV_PM")
def _provv_pm(d, p, rif):
    m = rapporto(-d.voce("provvigioni", p), d.voce("pm_lordo", p), p, "PM lordo = 0")
    m.sub = f"provvigioni {fmt.eur_compatto(-d.voce('provvigioni', p))}"
    return m


@kpi("V2_COSTI_GEN")
def _costi_gen(d, p, rif):
    # Nel sottotitolo niente contratto NeWatt: è fuori dal perimetro del
    # viewer (blueprint §9) e il sottotitolo non conosce il ruolo.
    return Misura(-d.voci(VOCI_COSTI_GENERALI, p),
                  sub=f"servizi generali {fmt.eur_compatto(-d.voce('costi_servizi', p))}"
                      f" · marketing {fmt.eur_compatto(-d.voce('costi_marketing', p))}",
                  serie=[-sum(v) for v in zip(*(d.voce_mensile(c, p.anno)
                                                 for c in VOCI_COSTI_GENERALI))])


@kpi("V5_PERDITE")
def _perdite(d, p, rif):
    m = rapporto(-d.voce("perdite_crediti", p), d.voce("ricavi", p), p, "ricavi = 0")
    m.sub = f"{fmt.eur_compatto(-d.voce('perdite_crediti', p))} nel periodo"
    return m


# =============================================================================
# KPI di portafoglio e unitari
# =============================================================================

@kpi("L3_PDP", "V3_PDP")
def _pdp_attivi(d, p, rif):
    fine = _pdp(d, p.anno, p.mese_a)
    inizio = _pdp(d, p.anno, p.mese_da - 1)
    net = fine - inizio
    return Misura(fine, sub=f"net adds del periodo: {fmt.segno(net, fmt.numero(net))}",
                  serie=_serie_pdp(d, p.anno))


@kpi("L3_MIX")
def _mix(d, p, rif):
    retail = _pdp(d, p.anno, p.mese_a, segmento="Retail")
    tot = _pdp(d, p.anno, p.mese_a)
    if tot < 1e-9:
        return Misura(None, "nessun PdP attivo a fine periodo")
    quota = retail / tot
    return Misura(quota, sub=f"Business {fmt.pct(1 - quota)} · target DeD 80/20")


def _cts(d: Dati, p: Periodo, voci) -> Misura:
    costi = -d.voci(voci, p)
    m = rapporto(costi * _annualizza(p), _pdp_medi(d, p), p, "nessun PdP attivo")
    # Riga "Cost to Serve" del BP: costi dell'anno / PdP a FINE anno.
    fy = p.anno_intero()
    fine = _pdp(d, p.anno, 12)
    if not p.avviamento and fine > 0:
        m.nota = f"riga BP (PdP a fine anno): {fmt.numero(-d.voci(voci, fy) / fine)} €"
    return m


@kpi("L3_CTS", "V5_CTS")
def _cost_to_serve(d, p, rif):
    m = _cts(d, p, VOCI_CTS)
    m.sub = "su PdP attivi medi, annualizzato"
    return m


@kpi("L3_COSTO_CLIENTE")
def _costo_cliente(d, p, rif):
    """Tutto ciò che separa il primo margine lordo dall'EBITDA, per cliente:
    il Cost-to-Serve più i costi commerciali (provvigioni, spese point)."""
    m = _cts(d, p, VOCI_COSTO_CLIENTE)
    m.nota = ""            # la «riga BP» di _cts è quella del Cost-to-Serve
    cts = _cts(d, p, VOCI_CTS).valore
    if not fmt.manca(m.valore) and not fmt.manca(cts):
        m.sub = (f"di cui Cost-to-Serve {fmt.numero(cts)} € e costi commerciali "
                 f"{fmt.numero(m.valore - cts)} € · su PdP medi, annualizzato")
    return m


@kpi("L3_MARGINE_UNIT")
def _margine_unitario(d, p, rif):
    m = rapporto(d.voce("ebitda", p) * _annualizza(p), _pdp_medi(d, p), p,
                 "nessun PdP attivo")
    m.sub = "EBITDA su PdP attivi medi, annualizzato"
    fine = _pdp(d, p.anno, 12)
    if not p.avviamento and fine > 0:
        m.nota = (f"su PdP a fine anno: "
                  f"{fmt.numero(d.voce('ebitda', p.anno_intero()) / fine)} €")
    return m


def _finestra_ltm(anno: int, mese: int) -> list[tuple[int, int]]:
    out = []
    a, m = anno, mese
    for _ in range(12):
        out.append((a, m))
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    return out


def _churn_ltm(d: Dati, p: Periodo, **dims) -> Misura:
    """Cessati degli ultimi 12 mesi / base attiva media degli stessi mesi
    (dims: commodity="Power"/"Gas" per il churn di una sola commodity)."""
    finestra = _finestra_ltm(p.anno, p.mese_a)
    cessati = sum(d.stock("switch_out", a, m, canale="Agenti", **dims) for a, m in finestra)
    basi = [_pdp(d, a, m, **dims) for a, m in finestra]
    basi = [b for b in basi if b > 0]
    if not basi or p.avviamento:
        return Misura(None, MOTIVO_AVVIAMENTO if p.avviamento else "nessun PdP attivo")
    ltm = cessati / (sum(basi) / len(basi))
    mesi_dati = len(basi)
    sub = f"≈ {fmt.pct(ltm / 12)} al mese · ipotesi del BP"
    if mesi_dati < 12:
        sub += f" · su {mesi_dati} mesi"
    return Misura(ltm, sub=sub)


# Regola del Cruscotto (Migliora, 15/10/2026): nessuna tessera per singola
# commodity; la divisione EE / gas sta dentro la tessera (Misura.commodity).
COMMODITY = ("Power", "Gas")


@kpi("L3_CHURN")
def _churn(d, p, rif):
    """Churn di tutti i clienti; il dettaglio sotto il numero lo divide per
    commodity (stessa definizione LTM sulla sola commodity)."""
    m = _churn_ltm(d, p)
    if not fmt.manca(m.valore):
        m.commodity_valori = {c: _churn_ltm(d, p, commodity=c).valore for c in COMMODITY}
        m.commodity = {c: fmt.pct(v) for c, v in m.commodity_valori.items()}
    return m


@kpi("L3_CLT")
def _clt(d, p, rif):
    """CLT: un solo KPI (tutti i clienti) con il dettaglio per commodity sotto
    il numero. Il BP non lo contiene (servono le date di attivazione dal CRM,
    fase 4): la tessera resta «in attesa dati» ma mostra già il dettaglio."""
    return Misura(None, commodity={c: "— gg" for c in COMMODITY},
                  commodity_valori={c: None for c in COMMODITY})


# =============================================================================
# KPI commerciali (canale Agenti)
# =============================================================================

def _produzione(d: Dati, p: Periodo, **dims) -> float:
    return d.flusso("produzione", p, canale="Agenti", **dims)


@kpi("V3_PRODUZIONE")
def _prod(d, p, rif):
    r = _produzione(d, p, segmento="Retail")
    b = _produzione(d, p, segmento="Business")
    return Misura(r + b, sub=f"Retail {fmt.numero(r)} · Business {fmt.numero(b)}",
                  serie=d.mensile("produzione", p.anno, canale="Agenti"))


@kpi("V3_SWITCH_OUT")
def _switch_out(d, p, rif):
    so = d.flusso("switch_out", p, canale="Agenti")
    base = sum(_pdp(d, p.anno, m - 1) for m in p.mesi)
    sub = (f"{fmt.pct(so / base)} al mese sulla base di inizio mese"
           if base > 0 else "base attiva nulla")
    return Misura(so, sub=sub, serie=d.mensile("switch_out", p.anno, canale="Agenti"))


@kpi("V3_NET_ADDS")
def _net_adds(d, p, rif):
    net = _produzione(d, p) - d.flusso("switch_out", p, canale="Agenti")
    prod = d.mensile("produzione", p.anno, canale="Agenti")
    so = d.mensile("switch_out", p.anno, canale="Agenti")
    return Misura(net, sub="produzione − cessazioni",
                  serie=[a - b for a, b in zip(prod, so)])


@kpi("V3_AVANZAMENTO")
def _avanzamento(d, p, rif):
    target = _produzione(rif, p.anno_intero())
    if target < 1e-9:
        return Misura(None, "nessuna produzione a piano nell'anno")
    return Misura(_produzione(d, p) / target,
                  sub=f"target anno {fmt.numero(target)} contratti (versione di riferimento)")


PUNTI_COMMODITY = {"Power": "POD", "Gas": "PDR"}


@kpi("L3_SALES")
def _sales_plan(d, p, rif):
    """Attivazioni a consuntivo / attivazioni del BP nel periodo, su tutti i
    clienti, con il dettaglio per commodity. Il consuntivo non c'è ancora
    (fase 3): la tessera dice quanto il BP chiede di attivare, senza fingere un
    100% che sarebbe il BP confrontato con se stesso."""
    obiettivi = {c: _produzione(d, p, commodity=c) for c in COMMODITY}
    totale = sum(obiettivi.values())
    if totale < 1e-9:
        return Misura(None, "il BP non prevede attivazioni nel periodo")
    return Misura(None, rif=(f"obiettivo BP {fmt.numero(totale)} contratti · "
                             f"{fmt.periodo_label(p.anno, p.mese_da, p.mese_a)}"),
                  commodity={c: f"{fmt.numero(v)} {PUNTI_COMMODITY[c]}"
                             for c, v in obiettivi.items()},
                  commodity_valori={c: None for c in COMMODITY})


@kpi("V3_CAC")
def _cac(d, p, rif):
    costo = (-d.flusso("provvigioni_una_tantum", p, canale="Agenti")
             - d.voce("spese_point", p))
    m = rapporto(costo, _produzione(d, p), p, "nessuna produzione nel periodo")
    m.sub = f"gettoni + spese point {fmt.eur_compatto(costo)}"
    return m


# =============================================================================
# KPI VAS
# =============================================================================

@kpi("V4_VAS_ATTIVI")
def _vas_attivi(d, p, rif):
    pw = d.stock("vas_attivi", p.anno, p.mese_a, commodity="Power")
    gs = d.stock("vas_attivi", p.anno, p.mese_a, commodity="Gas")
    return Misura(pw + gs, sub=f"su POD {fmt.numero(pw)} · su PDR {fmt.numero(gs)}",
                  serie=d.mensile("vas_attivi", p.anno))


@kpi("V4_PENETRAZIONE")
def _penetrazione(d, p, rif):
    vas = d.stock("vas_attivi", p.anno, p.mese_a)
    tot = _pdp(d, p.anno, p.mese_a)
    m = rapporto(vas, tot, p, "nessun PdP attivo")
    pod = rapporto(d.stock("vas_attivi", p.anno, p.mese_a, commodity="Power"),
                   _pdp(d, p.anno, p.mese_a, commodity="Power"), p, "")
    pdr = rapporto(d.stock("vas_attivi", p.anno, p.mese_a, commodity="Gas"),
                   _pdp(d, p.anno, p.mese_a, commodity="Gas"), p, "")
    if m.valore is not None:
        m.sub = f"POD {fmt.pct(pod.valore)} · PDR {fmt.pct(pdr.valore)} · obiettivo 45%"
    return m


@kpi("V4_EXTRA_PROFITTO")
def _extra_profitto(d, p, rif):
    pw = d.flusso("margine_vas", p, commodity="Power")
    gs = d.flusso("margine_vas", p, commodity="Gas")
    return Misura(pw + gs, sub=f"Power {fmt.eur_compatto(pw)} · Gas {fmt.eur_compatto(gs)}",
                  serie=d.mensile("margine_vas", p.anno))


@kpi("V4_MARGINE_MEDIO")
def _margine_vas_medio(d, p, rif):
    m = rapporto(d.flusso("margine_vas", p) * _annualizza(p),
                 d.stock_medio("vas_attivi", p), p, "nessun VAS attivo")
    m.sub = "per punto con VAS all'anno"
    return m


# =============================================================================
# KPI Operations
# =============================================================================

@kpi("V5_NEWATT_PUNTO")
def _newatt(d, p, rif):
    m = _cts(d, p, ("srv_newatt",))
    m.sub = "contratto intragruppo su PdP medi, annualizzato"
    return m


def _fte(d: Dati, p: Periodo, ruolo_driver: str, ruoli_piano) -> Misura:
    nec = d.stock_medio("fte_necessari", p, ruolo=ruolo_driver)
    piano = d.stock_medio("fte_pianificati", p, ruolo=list(ruoli_piano))
    gap = nec - piano
    avvisi = []
    if gap > 0.5:
        avvisi.append(Badge(f"! mancano {fmt.numero(gap, 1)} FTE al piano", "cattivo"))
    elif gap < -0.5:
        avvisi.append(Badge(f"{fmt.numero(-gap, 1)} FTE oltre il fabbisogno", "attenzione"))
    return Misura(nec, sub=f"pianificati {fmt.numero(piano, 1)} · gap "
                           f"{fmt.segno(gap, fmt.numero(gap, 1))}",
                  serie=d.mensile("fte_necessari", p.anno, ruolo=ruolo_driver),
                  avvisi=avvisi)


@kpi("V5_FTE_CC")
def _fte_cc(d, p, rif):
    return _fte(d, p, "Customer Care", ("Customer Care",))


@kpi("V5_FTE_OP")
def _fte_op(d, p, rif):
    return _fte(d, p, "Operation", RUOLI_OPERATION)


@kpi("V5_COSTO_FTE")
def _costo_fte(d, p, rif):
    m = rapporto(-d.voce("personale", p) * _annualizza(p),
                 d.stock_medio("fte_pianificati", p), p, "nessun FTE pianificato")
    m.sub = "costo personale operativo su FTE pianificati medi"
    return m


# =============================================================================
# Confronto e semaforo direzionale
# =============================================================================

@dataclass
class Confronto:
    assoluto: Optional[float]
    relativo: Optional[float]
    stato: str                         # ok | warn | crit | neutral


def confronta(a: Optional[float], b: Optional[float], unita: str, direzione: int,
              gialla: Optional[float], rossa: Optional[float]) -> Confronto:
    """Δ = B − A (B = confronto, A = riferimento). Semaforo con soglia e
    direzione dal catalogo: favorevole o entro la soglia gialla = ok;
    sfavorevole oltre la gialla = warn, oltre la rossa = crit. Sulle
    percentuali le soglie sono in punti %. Direzione 0 = ogni scostamento
    oltre soglia è da guardare (warn/crit), senza verso."""
    if a is None or b is None:
        return Confronto(None, None, "neutral")
    d = b - a
    rel = d / abs(a) if abs(a) > 1e-9 else None
    misura = d * 100 if unita == "%" else (rel * 100 if rel is not None else None)
    if misura is None:
        return Confronto(d, rel, "neutral")
    sfav = abs(misura) if direzione == 0 else -misura * direzione
    g = 5.0 if gialla is None or pd.isna(gialla) else float(gialla)
    r = 10.0 if rossa is None or pd.isna(rossa) else float(rossa)
    stato = "ok" if sfav <= g else ("warn" if sfav <= r else "crit")
    return Confronto(d, rel, stato)


def stato_voce(a: float, b: float, gialla: float = 5.0, rossa: float = 10.0) -> Confronto:
    """Semaforo sulle voci CE: i costi sono negativi, quindi per ogni voce
    'più alto è meglio' (un costo che scende è uno scostamento positivo)."""
    return confronta(a, b, "€", 1, gialla, rossa)


# =============================================================================
# Badge delle tessere (stile DeD): tendenza, benchmark, trend
# =============================================================================

def _tono(diff: float, direzione: int) -> str:
    if direzione == 0 or abs(diff) < 1e-12:
        return "neutro"
    return "buono" if diff * direzione > 0 else "cattivo"


def tendenza(codice: str, d: Dati, p: Periodo, unita: str, direzione: int) -> Optional[Badge]:
    """Variazione rispetto allo stesso periodo dell'anno precedente: è il
    delta sotto il numero quando non c'è una versione di confronto. La
    freccia segue il valore, il colore dice se è un bene (direzione)."""
    prec = Periodo(p.anno - 1, p.mese_a, p.mese_da)
    if d.vuota or prec.anno not in d.anni:
        return None
    a, b = calcola(codice, d, prec, d), calcola(codice, d, p, d)
    if a is None or b is None or fmt.manca(a.valore) or fmt.manca(b.valore):
        return None
    diff = b.valore - a.valore
    rif = f"vs {prec.anno}"
    if unita == "%":
        if abs(diff) < 0.0005:
            return Badge(f"= stabile {rif}")
        freccia = "▲" if diff > 0 else "▼"
        return Badge(f"{freccia} {fmt.segno(diff, fmt.numero(diff * 100, 1))} pt {rif}",
                     _tono(diff, direzione))
    if abs(a.valore) < 1e-9:
        return Badge("primo anno operativo") if abs(b.valore) > 1e-9 else None
    rel = diff / abs(a.valore)
    if abs(rel) < 0.005:
        return Badge(f"= stabile {rif}")
    freccia = "▲" if diff > 0 else "▼"
    return Badge(f"{freccia} {fmt.pct_segno(rel, 0 if abs(rel) >= 0.1 else 1)} {rif}",
                 _tono(diff, direzione))


def _fmt_bench(x: float, unita: str) -> str:
    return fmt.pct(x, 0) if unita == "%" else fmt.numero(x)


def avviso_benchmark(valore: Optional[float], unita: str, direzione: int,
                     bench_min, bench_max) -> Optional[Badge]:
    """Confronto con l'intervallo sano del catalogo (bench_min/bench_max).
    Dentro = insight; fuori nel verso sbagliato = avviso «!»."""
    if fmt.manca(valore):
        return None
    lo = None if bench_min is None or pd.isna(bench_min) else float(bench_min)
    hi = None if bench_max is None or pd.isna(bench_max) else float(bench_max)
    if lo is None and hi is None:
        return None
    euro = " €" if unita.startswith("€") else ""
    if lo is not None and hi is not None:
        # l'unità si scrive una volta sola: «10–15 €», «75–85%»
        primo = fmt.numero(lo * 100) if unita == "%" else fmt.numero(lo)
        rng = f"{primo}–{_fmt_bench(hi, unita)}{euro}"
    else:
        rng = _fmt_bench(lo if lo is not None else hi, unita) + euro
    sopra = hi is not None and valore > hi
    sotto = lo is not None and valore < lo
    if not (sopra or sotto):
        return Badge(f"in linea col benchmark {rng}", "buono")
    if direzione == 0:
        return Badge(f"! fuori dal target {rng}", "attenzione")
    if sopra and direzione < 0:
        volte = valore / hi if hi else None
        if volte and volte >= 1.5:
            return Badge(f"! {fmt.numero(volte, 1)}× il benchmark {rng}", "cattivo")
        return Badge(f"! sopra il benchmark {rng}", "cattivo")
    if sotto and direzione > 0:
        if unita == "%":
            return Badge(f"! {fmt.numero((lo - valore) * 100, 1)} pt sotto l'obiettivo {rng}",
                         "cattivo")
        return Badge(f"! sotto l'obiettivo {rng}", "cattivo")
    return Badge(f"meglio del benchmark {rng}", "buono")


def avviso_trend(serie: Optional[list], anno: int, mese_a: int, direzione: int,
                 minimo: int = 3) -> Optional[Badge]:
    """«In calo da N mesi»: mesi consecutivi di peggioramento che finiscono
    nel mese di fine periodo. Solo per KPI dove più alto è meglio (sui costi
    la crescita segue quella del portafoglio e sarebbe solo rumore)."""
    if not serie or direzione <= 0:
        return None
    mesi = [m for m in range(1, mese_a + 1) if (anno, m) >= bi.INIZIO_PIANO]
    n = 0
    for m in reversed(mesi[1:]):
        if serie[m - 1] < serie[m - 2] - 1e-9:
            n += 1
        else:
            break
    return Badge(f"! in calo da {n} mesi", "attenzione") if n >= minimo else None


# =============================================================================
# Aggregazioni per grafici e tabelle
# =============================================================================

def ce_sintetico(a: Dati, b: Optional[Dati], p: Periodo, livello_max: int = 1) -> pd.DataFrame:
    """CE per voce (livello <= livello_max) nel periodo e nell'anno intero,
    con confronto B − A se B è presente."""
    righe = []
    fy = p.anno_intero()
    for ordine, v in enumerate(bi.VOCI):
        if v.livello > livello_max:
            continue
        va, va_fy = a.voce(v.codice, p), a.voce(v.codice, fy)
        if b is None and abs(va_fy) < 1e-9 and v.livello > 1:
            continue
        riga = {"codice": v.codice, "voce": ("   " * (v.livello - 1)) + v.etichetta,
                "livello": v.livello, "natura": v.natura, "ordine": ordine,
                "mese": a.voce(v.codice, Periodo(p.anno, p.mese_a, p.mese_a)),
                "periodo": va, "anno": va_fy}
        ric = a.voce("ricavi", p)
        riga["su_ricavi"] = (va / ric) if abs(ric) > 1e-9 and not p.avviamento else None
        if b is not None:
            vb, vb_fy = b.voce(v.codice, p), b.voce(v.codice, fy)
            c = stato_voce(va, vb)
            riga.update(confronto_periodo=vb, confronto_anno=vb_fy, delta=c.assoluto,
                        delta_pct=c.relativo, stato=c.stato)
        righe.append(riga)
    return pd.DataFrame(righe)


def waterfall(d: Dati, p: Periodo) -> pd.DataFrame:
    """Ponte Ricavi -> Risultato netto per il periodo (in €)."""
    passi = [
        ("Ricavi", "totale", d.voce("ricavi", p)),
        ("Costo materia", "delta", d.voce("costi_appr", p)),
        ("PM lordo", "totale", d.voce("pm_lordo", p)),
        ("Provvigioni e point", "delta", d.voci(("provvigioni", "spese_point"), p)),
        ("Costi generali", "delta", d.voci(VOCI_COSTI_GENERALI, p)),
        ("Personale", "delta", d.voce("personale", p)),
        ("EBITDA", "totale", d.voce("ebitda", p)),
        ("Perdite, amm., oneri", "delta",
         d.voci(("perdite_crediti", "ammortamenti", "oneri_diversi"), p)),
        ("Gestione finanziaria", "delta", d.voci(("proventi_fin", "oneri_fin"), p)),
        ("Imposte", "delta", d.voce("imposte", p)),
        ("Risultato netto", "totale", d.voce("risultato_netto", p)),
    ]
    righe, livello = [], 0.0
    for i, (nome, tipo, val) in enumerate(passi):
        if tipo == "totale":
            inizio, fine, livello = 0.0, val, val
        else:
            inizio, fine = livello, livello + val
            livello = fine
        righe.append({"ordine": i, "passo": nome, "tipo": tipo, "valore": val,
                      "inizio": inizio, "fine": fine})
    return pd.DataFrame(righe)


def serie_mensile(d: Dati, anni: list[int], voce: Optional[str] = None,
                  driver: Optional[str] = None, **dims) -> pd.DataFrame:
    """Serie mensile su più anni: [anno, mese, etichetta, ordine, valore]."""
    righe = []
    for anno in anni:
        vals = d.voce_mensile(voce, anno) if voce else d.mensile(driver, anno, **dims)
        for m, v in enumerate(vals, start=1):
            if (anno, m) < bi.INIZIO_PIANO:
                continue
            righe.append({"anno": anno, "mese": m, "etichetta": fmt.mese_label(anno, m),
                          "ordine": anno * 100 + m, "valore": v})
    return pd.DataFrame(righe)


def cts_per_famiglia(d: Dati, anni: list[int]) -> pd.DataFrame:
    """Costi operativi per famiglia e anno, in € e in € per PdP medio."""
    foglie = [v for v in bi.VOCI if v.famiglia and v.padre in VOCI_COSTI_GENERALI]
    righe = []
    for anno in anni:
        p = Periodo(anno)
        medi = _pdp_medi(d, p)
        fam: dict[str, float] = {}
        for v in foglie:
            fam[v.famiglia] = fam.get(v.famiglia, 0.0) - d.voce(v.codice, p)
        fam["Personale"] = -d.voce("personale", p)
        for nome, euro in fam.items():
            righe.append({"anno": anno, "famiglia": nome, "euro": euro,
                          "per_pdp": (euro / medi) if medi > 0 and not p.avviamento else None})
    return pd.DataFrame(righe)


def matrice_scostamenti(a: Dati, b: Optional[Dati], anno: int,
                        livello_max: int = 1) -> pd.DataFrame:
    """Voce × mese per la heatmap: valori A/B, Δ, Δ%, stato; senza B la quota
    del mese sul totale annuo della voce (mensilizzazione). Sempre con le
    colonne, anche vuota (es. 2026 senza confronto: tutte le voci a zero)."""
    colonne = ["codice", "voce", "livello", "ordine", "mese", "mese_label", "a"] + (
        ["b", "delta", "delta_pct", "stato"] if b is not None else ["quota"])
    righe = []
    for ordine, v in enumerate(bi.VOCI):
        if v.livello > livello_max:
            continue
        mens_a = a.voce_mensile(v.codice, anno)
        tot_a = sum(mens_a)
        if b is None and abs(tot_a) < 1e-9:
            continue
        mens_b = b.voce_mensile(v.codice, anno) if b is not None else None
        for m in range(1, 13):
            if (anno, m) < bi.INIZIO_PIANO:
                continue
            riga = {"codice": v.codice, "voce": v.etichetta, "livello": v.livello,
                    "ordine": ordine, "mese": m, "mese_label": fmt.MESI[m - 1],
                    "a": mens_a[m - 1]}
            if mens_b is not None:
                c = stato_voce(mens_a[m - 1], mens_b[m - 1])
                riga.update(b=mens_b[m - 1], delta=c.assoluto, delta_pct=c.relativo,
                            stato=c.stato)
            else:
                riga["quota"] = (mens_a[m - 1] / tot_a) if abs(tot_a) > 1e-9 else None
            righe.append(riga)
    return pd.DataFrame(righe, columns=colonne)
