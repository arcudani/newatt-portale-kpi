"""
Import del BP Excel di Migliora (v5 e successive) — funzioni PURE, testabili
offline, nessun accesso a DB o rete.

Legge i valori CALCOLATI (openpyxl data_only) e li porta in forma lunga per
bp_ce_mensile / bp_driver_mensile. Parsing content-first: le colonne dei mesi
si trovano dalla riga d'intestazione con le date, le righe dall'etichetta
normalizzata cercata DOPO un'ancora (la sezione) — mai da coordinate fisse,
così una riga aggiunta nell'Excel non sposta i dati.

Regole di contenuto:
  * piano da ottobre 2026 (INIZIO_PIANO): i mesi precedenti del foglio sono
    colonne vuote e vengono scartati;
  * i costi mantengono il segno negativo del BP; i conteggi (switch-out)
    diventano positivi;
  * IRES e IRAP esistono solo come totale annuo: imputate a DICEMBRE, e il
    risultato netto di dicembre viene rettificato delle stesse imposte, così
    la somma dei mesi quadra con il Riepilogo;
  * la quadratura confronta le somme annue con il foglio "Riepilogo
    Business Plan" (tolleranza ±0,1%, requisiti §5).
"""
from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

INIZIO_PIANO = (2026, 10)
TOLLERANZA_QUADRATURA = 0.001      # ±0,1% per voce annuale
FOGLIO_CE = "Risultato Mensile"
FOGLIO_RIEPILOGO = "Riepilogo Business Plan"


def norm(testo) -> str:
    """Etichetta normalizzata: minuscolo, solo lettere/cifre/% (gli accenti e
    il simbolo ° dell'Excel arrivano in encoding diversi: si scartano)."""
    if testo is None:
        return ""
    return re.sub(r"[^a-z0-9%]+", " ", str(testo).lower()).strip()


# =============================================================================
# Piano delle voci CE (codice, etichetta, padre, livello, natura, commodity,
# famiglia CtS, ancora, etichetta Excel). Etichetta Excel None = voce
# calcolata come somma dei figli. "IRES*" = etichetta per prefisso (l'aliquota
# nell'etichetta può cambiare).
# =============================================================================

@dataclass(frozen=True)
class Voce:
    codice: str
    etichetta: str
    padre: Optional[str]
    livello: int
    natura: str                      # ricavo | costo | margine
    commodity: str = ""
    famiglia: str = ""               # famiglia di costo per il Cost-to-Serve
    ancora: Optional[str] = None     # sezione del foglio dopo cui cercare
    excel: Optional[str] = None      # etichetta nel foglio Risultato Mensile


def _v(codice, etichetta, padre, livello, natura, excel=None, ancora=None,
       commodity="", famiglia="") -> Voce:
    return Voce(codice, etichetta, padre, livello, natura, commodity,
                famiglia, ancora, excel)


def _commodity_voci(com: str) -> list[Voce]:
    c = com.lower()
    return [
        _v(f"ricavi_{c}", f"Ricavi {com}", "ricavi", 2, "ricavo",
           f"Totale Ricavi {com}", com, com),
        _v(f"ricavi_{c}_materia", "Materia prima", f"ricavi_{c}", 3, "ricavo",
           "Ricavi Materia Prima", com, com),
        _v(f"ricavi_{c}_quota_fissa", "Quota fissa", f"ricavi_{c}", 3, "ricavo",
           "Ricavi Quota Fissa", com, com),
        _v(f"ricavi_{c}_pratiche", "Pratiche", f"ricavi_{c}", 3, "ricavo",
           "Ricavi Pratiche", com, com),
        _v(f"ricavi_{c}_oneri", "Oneri passanti", f"ricavi_{c}", 3, "ricavo",
           "Ricavi Oneri Passanti", com, com),
        _v(f"ricavi_{c}_sopravv", "Sopravvenienze attive", f"ricavi_{c}", 3,
           "ricavo", "Ricavi Sopravvenienze Attive", com, com),
    ]


def _commodity_costi(com: str) -> list[Voce]:
    c = com.lower()
    return [
        _v(f"appr_{c}", f"Approvvigionamento {com}", "costi_appr", 2, "costo",
           f"Totale Costi {com}", com, com),
        _v(f"appr_{c}_materia", "Materia prima", f"appr_{c}", 3, "costo",
           "Costi Materia Prima", com, com),
        _v(f"appr_{c}_quota_fissa", "Quota fissa", f"appr_{c}", 3, "costo",
           "Costi Quota Fissa", com, com),
        _v(f"appr_{c}_oneri", "Oneri passanti", f"appr_{c}", 3, "costo",
           "Costi Oneri Passanti", com, com),
        _v(f"appr_{c}_sopravv", "Sopravvenienze passive", f"appr_{c}", 3,
           "costo", "Costi Sopravvenienze Passive", com, com),
    ]


VOCI: list[Voce] = [
    _v("ricavi", "Ricavi", None, 1, "ricavo", "Totale Ricavi"),
    *_commodity_voci("Power"),
    *_commodity_voci("Gas"),
    _v("altre_vendite", "Altre vendite", "ricavi", 2, "ricavo", "ALTRE VENDITE"),
    _v("costi_appr", "Costi di approvvigionamento", None, 1, "costo", "Totale Costi"),
    *_commodity_costi("Power"),
    *_commodity_costi("Gas"),
    _v("pm_lordo", "Primo margine lordo", None, 1, "margine", "Primo Margine Lordo"),
    _v("provvigioni", "Provvigioni", None, 1, "costo", "Provvigioni"),
    _v("spese_point", "Spese point", None, 1, "costo", "Spese Point"),
    _v("pm_netto", "Primo margine netto", None, 1, "margine",
       "Primo Margine Netto Totale"),
    _v("costi_marketing", "Costi marketing e commerciali", None, 1, "costo",
       "Costi Marketing e Commerciali (non variabili)", famiglia="Marketing"),
    _v("mkt_viaggi", "Viaggi e rimborsi spese", "costi_marketing", 2, "costo",
       "Viaggi e rimborsi spese", famiglia="Marketing"),
    _v("mkt_contratti", "Contratti di servizio specifici", "costi_marketing", 2,
       "costo", "Contratti di Servizio Specifici", famiglia="Marketing"),
    _v("mkt_altri", "Altri costi marketing e commerciali", "costi_marketing", 2,
       "costo", "Altri costi Marketing e commerciali", famiglia="Marketing"),
    _v("costi_servizi", "Costi servizi generali", None, 1, "costo",
       "Costi Servizi Generali", famiglia="Servizi generali"),
    _v("srv_newatt", "Contratto di servizio NeWatt", "costi_servizi", 2, "costo",
       "Contratto di Servizio Newatt", famiglia="Contratto NeWatt"),
    _v("srv_assicurazioni", "Assicurazioni e fideiussioni", "costi_servizi", 2,
       "costo", "Assicurazioni e Fidejussioni", famiglia="Servizi generali"),
    _v("srv_legali", "Spese legali e amministrative", "costi_servizi", 2, "costo",
       "Spese Legali e Amministrative", famiglia="Servizi generali"),
    _v("srv_paghe", "Studio paghe, revisore, commercialista", "costi_servizi", 2,
       "costo", "Studio Paghe, Revisore, Commercialista",
       famiglia="Servizi generali"),
    _v("srv_straordinarie", "Spese amministrative straordinarie", "costi_servizi",
       2, "costo", "Spese Amministrative Straordinarie",
       famiglia="Servizi generali"),
    _v("srv_it", "Spese gestione IT", "costi_servizi", 2, "costo",
       "Spese Gestione IT", famiglia="IT"),
    _v("srv_pasti", "Pasti, soggiorni, buoni pasto", "costi_servizi", 2, "costo",
       "Pasti, Soggiorni, Buoni Pasto", famiglia="Servizi generali"),
    _v("srv_note_spese", "Note spese amministratori", "costi_servizi", 2, "costo",
       "Note Spese Amministratori", famiglia="Servizi generali"),
    _v("srv_cda", "Costo CdA", "costi_servizi", 2, "costo", "Costo CDA",
       famiglia="Servizi generali"),
    _v("srv_sede", "Spese di sede", "costi_servizi", 2, "costo", "Spese di Sede",
       famiglia="Servizi generali"),
    _v("srv_altri", "Altri costi per servizi", "costi_servizi", 2, "costo",
       "Altri costi per servizi", famiglia="Servizi generali"),
    _v("srv_oneri_sdd", "Oneri bancari / SDD", "costi_servizi", 2, "costo",
       "Oneri bancari / SDD", famiglia="Oneri bancari"),
    _v("srv_oneri_altri", "Oneri bancari altri costi", "costi_servizi", 2,
       "costo", "Oneri bancari altri costi", famiglia="Oneri bancari"),
    _v("costi_god_beni", "Costi godimento beni di terzi", None, 1, "costo",
       "Costi God. Beni di Terzi", famiglia="Beni di terzi"),
    _v("gbt_affitto", "Affitto", "costi_god_beni", 2, "costo", "Affitto",
       famiglia="Beni di terzi"),
    _v("gbt_auto", "Auto e veicoli", "costi_god_beni", 2, "costo",
       "Auto/veicoli", famiglia="Beni di terzi"),
    _v("gbt_noleggi", "Altri noleggi", "costi_god_beni", 2, "costo",
       "Altri Noleggi", famiglia="Beni di terzi"),
    _v("gbt_software", "Licenze software", "costi_god_beni", 2, "costo",
       "Lic. Software", famiglia="IT"),
    _v("valore_aggiunto", "Valore aggiunto", None, 1, "margine", "VALORE AGGIUNTO"),
    _v("personale", "Costo del personale", None, 1, "costo", "Costo Personale",
       famiglia="Personale"),
    _v("pers_salari", "Salari e stipendi", "personale", 2, "costo",
       "Salari e Stipendi", famiglia="Personale"),
    _v("pers_oneri", "Oneri sociali", "personale", 2, "costo", "Oneri Sociali",
       famiglia="Personale"),
    _v("pers_tfr", "TFR", "personale", 2, "costo", "TFR", famiglia="Personale"),
    _v("ebitda", "EBITDA", None, 1, "margine", "EBITDA"),
    _v("ammortamenti", "Ammortamenti", None, 1, "costo"),
    _v("amm_immateriali", "Ammortamenti immateriali", "ammortamenti", 2, "costo",
       "Ammortamenti Immateriali"),
    _v("amm_materiali", "Ammortamenti materiali", "ammortamenti", 2, "costo",
       "Ammortamenti Materiali"),
    _v("perdite_crediti", "Perdite su crediti e accantonamenti", None, 1, "costo"),
    _v("perdite", "Perdite su crediti", "perdite_crediti", 2, "costo",
       "Perdite su Crediti"),
    _v("acc_rischi_crediti", "Accantonamento rischi su crediti",
       "perdite_crediti", 2, "costo", "Accantonamento Rischi su Crediti"),
    _v("acc_altri_rischi", "Accantonamento altri rischi", "perdite_crediti", 2,
       "costo", "Accantonamento Altri Rischi"),
    _v("oneri_diversi", "Oneri diversi di gestione", None, 1, "costo",
       "Oneri div. di gestione (incluse sopravv. Passive)"),
    _v("ebit", "EBIT", None, 1, "margine", "EBIT"),
    _v("proventi_fin", "Proventi finanziari", None, 1, "ricavo",
       "Proventi Finanziari"),
    _v("pf_depositi", "Interessi attivi su depositi", "proventi_fin", 2, "ricavo",
       "Interessi Attivi su Depositi Bancari"),
    _v("pf_mora", "Interessi attivi di mora", "proventi_fin", 2, "ricavo",
       "Interessi Attivi di Mora"),
    _v("oneri_fin", "Oneri finanziari", None, 1, "costo", "Oneri Finanziari"),
    _v("of_bancari", "Interessi passivi bancari", "oneri_fin", 2, "costo",
       "Interessi Passivi Bancari"),
    _v("of_mutui", "Interessi passivi su mutui", "oneri_fin", 2, "costo",
       "Interessi Passivi su Mutui"),
    _v("of_finanziamenti", "Interessi passivi su finanziamenti", "oneri_fin", 2,
       "costo", "Interessi Passivi su Finanziamenti"),
    _v("of_anticipi", "Interessi passivi su c/anticipi", "oneri_fin", 2, "costo",
       "Interessi Passivi su c/Anticipi"),
    _v("of_fornitori", "Interessi passivi verso fornitori", "oneri_fin", 2,
       "costo", "Interessi Passivi verso Fornitori"),
    _v("ebt", "EBT", None, 1, "margine", "EBT"),
    _v("imposte", "Imposte", None, 1, "costo"),
    _v("ires", "IRES", "imposte", 2, "costo", "IRES*"),
    _v("irap", "IRAP", "imposte", 2, "costo", "IRAP*"),
    _v("risultato_netto", "Risultato netto", None, 1, "margine", "Risultato Netto"),
]
VOCI_PER_CODICE = {v.codice: v for v in VOCI}
VOCI_ANNUALI = ("ires", "irap")     # esistono solo come totale annuo


# =============================================================================
# Driver fisici: (foglio, ancora, etichetta, driver, dimensioni, segno)
# =============================================================================

@dataclass(frozen=True)
class SpecDriver:
    foglio: str
    ancora: Optional[str]
    etichetta: str
    driver: str
    dims: dict = field(default_factory=dict)
    segno: float = 1.0


def _d(foglio, ancora, etichetta, driver, segno=1.0, **dims) -> SpecDriver:
    return SpecDriver(foglio, ancora, etichetta, driver, dims, segno)


_AG, _VAS = "CdV - Sviluppo Agenti", "CdV - Sviluppo VAS"
_PMV, _PMA = "CdV - Calcolo PM VAS", "CdV - Calcolo PM Agenti"
_FCC, _FOP, _PER = "IPO - FTE Customer Care", "IPO - FTE Operation", "IPO - Personale"
_SEG_COM = [("Retail", "Power"), ("Retail", "Gas"), ("Business", "Power"),
            ("Business", "Gas")]
PRODOTTI_VAS = ["Assicurazione", "Manutenzione", "Telecomunicazioni"]
_ETICHETTA_PDP = {("Retail", "Power"): "POD Retail", ("Retail", "Gas"): "PDR Retail",
                  ("Business", "Power"): "POD Business",
                  ("Business", "Gas"): "PDR Business"}

SPEC_DRIVER: list[SpecDriver] = [
    # --- Canale Agenti: produzione, cessazioni, portafoglio, volumi ---
    *[_d(_AG, "Produzione", f"Prod. {c} {s}", "produzione",
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    *[_d(_AG, "Switch-out", f"Switch-out {c} {s}", "switch_out", -1.0,
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    *[_d(_AG, None, _ETICHETTA_PDP[(s, c)], "pdp_attivi",
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    *[_d(_AG, None, f"MWh {c} {s}", "mwh",
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    _d(_AG, None, "Apertura Sportelli", "aperture_sportelli", canale="Agenti"),
    # --- Economia del canale Agenti ---
    *[_d(_PMA, "Provvigioni", f"Provvigioni {c} {s}", "provvigioni_una_tantum",
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    *[_d(_PMA, "Rinnovi", f"Provvigioni {c} {s}", "provvigioni_ricorrenti",
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    *[_d(_PMA, None, f"Margine Totale {c} {s}", "margine_lordo",
         canale="Agenti", segmento=s, commodity=c) for s, c in _SEG_COM],
    # --- Canale VAS (nel v5 è un canale autonomo: vedi nota ricostruzione) ---
    *[_d(_VAS, "Produzione", f"Prod. {c} Retail", "produzione",
         canale="VAS", segmento="Retail", commodity=c) for c in ("Power", "Gas")],
    *[_d(_VAS, "Switch-out", f"Switch-out {c} Retail", "switch_out", -1.0,
         canale="VAS", segmento="Retail", commodity=c) for c in ("Power", "Gas")],
    *[_d(_VAS, None, f"{pref} Retail {p}", "vas_attivi", canale="VAS",
         segmento="Retail", commodity=c, prodotto_vas=p)
      for pref, c in (("POD", "Power"), ("PDR", "Gas")) for p in PRODOTTI_VAS],
    # Nel foglio PM VAS le righe gas sono etichettate "Power" (rilievo v5):
    # si leggono quindi per posizione, dopo l'ancora del totale gas.
    *[_d(_PMV, f"Margine Totale {c} Retail", f"Margine Fisso Power {p}",
         "margine_vas", canale="VAS", segmento="Retail", commodity=c,
         prodotto_vas=p) for c in ("Power", "Gas") for p in PRODOTTI_VAS],
    # --- FTE da driver (Customer Care / Operation) ---
    _d(_FCC, None, "PdP attivi totali", "pdp_base_fte", ruolo="Customer Care"),
    _d(_FCC, None, "Chiamate gestite da operatore", "carico_chiamate",
       ruolo="Customer Care"),
    _d(_FCC, None, "Contatti scritti gestiti da operatore",
       "carico_contatti_scritti", ruolo="Customer Care"),
    _d(_FCC, None, "Reclami gestiti da operatore", "carico_reclami",
       ruolo="Customer Care"),
    _d(_FCC, None, "FTE necessari", "fte_necessari", ruolo="Customer Care"),
    _d(_FOP, None, "Fatture emesse", "carico_fatture", ruolo="Operation"),
    _d(_FOP, None, "Pratiche switch-in", "carico_switch_in", ruolo="Operation"),
    _d(_FOP, None, "Pratiche di cessazione", "carico_cessazioni", ruolo="Operation"),
    _d(_FOP, None, "Volture/subentri gestiti", "carico_volture", ruolo="Operation"),
    _d(_FOP, None, "Pratiche incasso gestite", "carico_incassi", ruolo="Operation"),
    _d(_FOP, None, "FTE necessari", "fte_necessari", ruolo="Operation"),
    # --- Organico pianificato (foglio Personale) ---
    *[_d(_PER, None, et, "fte_pianificati", ruolo=ruolo) for et, ruolo in (
        ("Servizio clienti", "Customer Care"), ("Operation", "Operation"),
        ("Operation VAS", "Operation VAS"), ("Fatturazione", "Fatturazione"),
        ("Credito", "Credito"), ("Commerciale", "Commerciale"))],
    # nel blocco "Riepilogo Livelli" solo i primi due hanno il prefisso "Liv."
    *[_d(_PER, "Riepilogo Livelli", et, "organico_livello", ruolo=liv)
      for et, liv in (("Liv. Alto", "Alto"), ("Liv. Medio", "Medio"),
                      ("Apprendistato", "Apprendistato"), ("Tirocinio", "Tirocinio"))],
    *[_d(_PER, "Salari e Stipendi", liv, "salari_livello", ruolo=liv)
      for liv in ("Alto", "Medio", "Apprendistato", "Tirocinio")],
]
DIMENSIONI = ["canale", "segmento", "commodity", "prodotto_vas", "ruolo"]


# =============================================================================
# Quadratura con il foglio Riepilogo (annuale)
# =============================================================================

QUADRATURA_CE = [
    ("ricavi", "Fatturato Totale"),
    ("costi_appr", "Costi per Approvvigionamento"),
    ("pm_lordo", "Primo Margine Lordo"),
    ("provvigioni", "Provvigioni"),
    ("costi_marketing", "Costi Marketing & Comunicazione"),
    ("costi_servizi", "Costi Servizi Generali"),
    ("costi_god_beni", "Costi per God. Beni di Terzi"),
    ("personale", "Costo per il Personale Operativo"),
    ("ebitda", "EBITDA"),
    ("perdite_crediti", "Perdite su Crediti e Fondo Rischi"),
    ("ebit", "EBIT"),
    ("ires", "IRES"),
    ("irap", "IRAP"),
    ("risultato_netto", "Risultato Netto"),
]
# (etichetta Riepilogo, driver, filtro dimensioni, 'stock' = valore a dicembre)
QUADRATURA_DRIVER = [
    ("N° PdP", "pdp_attivi", {}, "stock"),
    ("MWH Power Venduti", "mwh", {"commodity": "Power"}, "flusso"),
    ("MWH Gas Venduti", "mwh", {"commodity": "Gas"}, "flusso"),
    ("di cui n° POD VAS", "vas_attivi", {"commodity": "Power"}, "stock"),
    ("di cui n° PDR VAS", "vas_attivi", {"commodity": "Gas"}, "stock"),
]


# =============================================================================
# Lettura del foglio
# =============================================================================

class StrutturaInattesa(ValueError):
    """Il file non ha la struttura attesa del BP (foglio o riga mancante)."""


@dataclass
class Foglio:
    """Foglio in memoria: righe (tuple di valori) + mappa colonne -> mese."""
    nome: str
    righe: list
    col_mesi: dict           # indice colonna -> (anno, mese)
    col_anni: dict           # indice colonna -> anno (totale annuo)


def _e_data(v) -> bool:
    return isinstance(v, (dt.datetime, dt.date))


def _leggi_foglio(wb, nome: str) -> Foglio:
    if nome not in wb.sheetnames:
        raise StrutturaInattesa(f"foglio '{nome}' assente")
    righe = [tuple(r) for r in wb[nome].iter_rows(values_only=True)]
    for r in righe[:40]:
        if sum(_e_data(v) for v in r) >= 10:
            col_mesi = {j: (v.year, v.month) for j, v in enumerate(r) if _e_data(v)}
            col_anni = {j: int(v) for j, v in enumerate(r)
                        if isinstance(v, int) and 2000 < v < 2100}
            return Foglio(nome, righe, col_mesi, col_anni)
    raise StrutturaInattesa(f"'{nome}': riga d'intestazione dei mesi non trovata")


def _corrisponde(riga: tuple, etichetta: str) -> bool:
    """True se una delle prime 3 celle della riga ha quell'etichetta.
    'XYZ*' = corrispondenza per prefisso."""
    if etichetta.endswith("*"):
        pref = norm(etichetta[:-1])
        return any(norm(c).startswith(pref) for c in riga[:3] if isinstance(c, str))
    target = norm(etichetta)
    return any(norm(c) == target for c in riga[:3] if isinstance(c, str))


def _trova_riga(f: Foglio, etichetta: str, ancora: Optional[str]) -> int:
    inizio = 0
    if ancora:
        for i, r in enumerate(f.righe):
            if _corrisponde(r, ancora):
                inizio = i + 1
                break
        else:
            raise StrutturaInattesa(f"'{f.nome}': sezione '{ancora}' non trovata")
    for i in range(inizio, len(f.righe)):
        if _corrisponde(f.righe[i], etichetta):
            return i
    dove = f" dopo '{ancora}'" if ancora else ""
    raise StrutturaInattesa(f"'{f.nome}': riga '{etichetta}'{dove} non trovata")


def _num(v) -> float:
    """Valore numerico di una cella; vuota o testo (#DIV/0!) -> 0."""
    if isinstance(v, bool) or v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _nel_piano(anno: int, mese: int) -> bool:
    return (anno, mese) >= INIZIO_PIANO


def _valori_mensili(f: Foglio, i: int) -> dict:
    r = f.righe[i]
    return {am: _num(r[j]) for j, am in f.col_mesi.items()
            if j < len(r) and _nel_piano(*am)}


def _totali_annui(f: Foglio, i: int) -> dict:
    r = f.righe[i]
    return {a: _num(r[j]) for j, a in f.col_anni.items() if j < len(r)}


# =============================================================================
# CE mensile
# =============================================================================

def _figli(codice: str) -> list[str]:
    return [v.codice for v in VOCI if v.padre == codice]


def estrai_ce(f: Foglio) -> tuple[pd.DataFrame, list[str]]:
    """CE mensile in forma lunga [voce, anno, mese, importo] + avvisi."""
    avvisi: list[str] = []
    valori: dict[str, dict] = {}
    annui: dict[str, dict] = {}
    for v in VOCI:
        if v.excel is None:
            continue
        i = _trova_riga(f, v.excel, v.ancora)
        valori[v.codice] = _valori_mensili(f, i)
        annui[v.codice] = _totali_annui(f, i)

    # Voci solo annuali (imposte): totale annuo imputato a dicembre.
    imposte_dic: dict[int, float] = {}
    for cod in VOCI_ANNUALI:
        mens = valori[cod]
        for anno, tot in annui[cod].items():
            mesi_anno = [am for am in mens if am[0] == anno]
            if not mesi_anno:
                continue
            if all(abs(mens[am]) < 1e-9 for am in mesi_anno) and abs(tot) > 1e-9:
                for am in mesi_anno:
                    mens[am] = 0.0
                mens[(anno, 12)] = tot
                imposte_dic[anno] = imposte_dic.get(anno, 0.0) + tot

    # Risultato netto: nel foglio i mesi sono ante imposte; si rettifica
    # dicembre solo se la differenza col totale annuo è proprio l'imposta.
    rn, rn_annuo = valori["risultato_netto"], annui["risultato_netto"]
    for anno, imp in imposte_dic.items():
        somma = sum(val for (a, _m), val in rn.items() if a == anno)
        diff = rn_annuo.get(anno, somma) - somma
        if abs(diff - imp) < 1.0 and (anno, 12) in rn:
            rn[(anno, 12)] += diff
        elif abs(diff) >= 1.0:
            avvisi.append(f"Risultato netto {anno}: i mesi non quadrano con il "
                          f"totale annuo (Δ {diff:,.0f} €) e la differenza non "
                          f"è spiegata dalle imposte.")

    # Voci calcolate (somma dei figli), dal livello più profondo.
    for v in sorted(VOCI, key=lambda x: -x.livello):
        if v.excel is None:
            figli = _figli(v.codice)
            chiavi = set().union(*(valori[c].keys() for c in figli))
            valori[v.codice] = {am: sum(valori[c].get(am, 0.0) for c in figli)
                                for am in chiavi}

    # Coerenza gerarchia: il totale del foglio deve essere la somma dei figli.
    for v in VOCI:
        figli = _figli(v.codice)
        if v.excel is None or not figli:
            continue
        for anno in sorted({a for a, _m in valori[v.codice]}):
            tot = sum(val for (a, _m), val in valori[v.codice].items() if a == anno)
            som = sum(val for c in figli
                      for (a, _m), val in valori[c].items() if a == anno)
            if abs(tot - som) > 1.0:
                avvisi.append(f"{v.etichetta} {anno}: totale {tot:,.0f} € ≠ somma "
                              f"delle sottovoci {som:,.0f} €.")

    righe = [(cod, a, m, val) for cod, mens in valori.items()
             for (a, m), val in mens.items()]
    ce = pd.DataFrame(righe, columns=["voce", "anno", "mese", "importo"])
    return ce.sort_values(["voce", "anno", "mese"], ignore_index=True), avvisi


# =============================================================================
# Driver mensili
# =============================================================================

def estrai_driver(fogli: dict[str, Foglio]) -> pd.DataFrame:
    righe = []
    for s in SPEC_DRIVER:
        f = fogli[s.foglio]
        i = _trova_riga(f, s.etichetta, s.ancora)
        dims = {d: s.dims.get(d, "") for d in DIMENSIONI}
        for (a, m), val in _valori_mensili(f, i).items():
            righe.append({"driver": s.driver, **dims, "anno": a, "mese": m,
                          "valore": val * s.segno})
    drv = pd.DataFrame(righe, columns=["driver", *DIMENSIONI, "anno", "mese",
                                       "valore"])
    return drv.sort_values(["driver", *DIMENSIONI, "anno", "mese"],
                           ignore_index=True)


# =============================================================================
# Quadratura
# =============================================================================

def _leggi_riepilogo(wb) -> tuple[list, dict]:
    if FOGLIO_RIEPILOGO not in wb.sheetnames:
        raise StrutturaInattesa(f"foglio '{FOGLIO_RIEPILOGO}' assente")
    righe = [tuple(r) for r in wb[FOGLIO_RIEPILOGO].iter_rows(values_only=True)]
    for r in righe[:10]:
        anni = {j: int(v) for j, v in enumerate(r)
                if isinstance(v, int) and 2000 < v < 2100}
        if len(anni) >= 3:
            return righe, anni
    raise StrutturaInattesa("Riepilogo: riga degli anni non trovata")


def _esito(grandezza: str, anno: int, excel: float, motore: float) -> dict:
    delta = motore - excel
    base = abs(excel)
    ok = abs(delta) <= max(1.0, TOLLERANZA_QUADRATURA * base)
    return {"grandezza": grandezza, "anno": anno, "excel": round(excel, 2),
            "motore": round(motore, 2), "delta": round(delta, 2),
            "delta_pct": (delta / base) if base > 1e-9 else None, "ok": ok}


def quadratura(ce: pd.DataFrame, drv: pd.DataFrame, righe_riep: list,
               col_anni: dict) -> list[dict]:
    """Confronto annuale import vs Riepilogo Excel (±0,1% o 1 €)."""
    riep = Foglio(FOGLIO_RIEPILOGO, righe_riep, {}, col_anni)
    out = []
    ce_anno = ce.groupby(["voce", "anno"])["importo"].sum()
    for cod, etichetta in QUADRATURA_CE:
        i = _trova_riga(riep, etichetta, None)
        for anno, excel in _totali_annui(riep, i).items():
            motore = float(ce_anno.get((cod, anno), 0.0))
            out.append(_esito(VOCI_PER_CODICE[cod].etichetta, anno, excel, motore))
    for etichetta, driver, filtro, tipo in QUADRATURA_DRIVER:
        i = _trova_riga(riep, etichetta, None)
        d = drv[drv["driver"] == driver]
        for k, v in filtro.items():
            d = d[d[k] == v]
        for anno, excel in _totali_annui(riep, i).items():
            da = d[d["anno"] == anno]
            if tipo == "stock":
                motore = float(da[da["mese"] == 12]["valore"].sum())
            else:
                motore = float(da["valore"].sum())
            out.append(_esito(etichetta.replace("n° ", "").replace("N° ", ""),
                              anno, excel, motore))
    return out


# =============================================================================
# Punto d'ingresso
# =============================================================================

@dataclass
class BPImportato:
    ce: pd.DataFrame
    driver: pd.DataFrame
    quadratura: list
    avvisi: list

    @property
    def quadratura_ok(self) -> bool:
        return all(q["ok"] for q in self.quadratura)


def leggi_bp(contenuto: bytes) -> BPImportato:
    """Legge il BP Excel (bytes) e restituisce CE, driver, quadratura, avvisi.
    Solleva StrutturaInattesa con un messaggio leggibile se manca qualcosa."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(contenuto), read_only=True, data_only=True)
    try:
        ce, avvisi = estrai_ce(_leggi_foglio(wb, FOGLIO_CE))
        fogli = {nome: _leggi_foglio(wb, nome)
                 for nome in {s.foglio for s in SPEC_DRIVER}}
        drv = estrai_driver(fogli)
        righe_riep, col_anni = _leggi_riepilogo(wb)
        q = quadratura(ce, drv, righe_riep, col_anni)
    finally:
        wb.close()
    return BPImportato(ce, drv, q, avvisi)
