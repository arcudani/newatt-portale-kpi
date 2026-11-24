"""
Catalogo dei KPI del portale NeWatt — dal foglio DASHBOARD dell'Excel
«Dashboard KPI» che ogni società del gruppo produce ogni mese.

Due livelli:
  * MISURE: una per cella del foglio (codice, etichetta, mese di riferimento
    M o M-1, unità, natura). È quello che si salva nel DB (kpi_valori).
  * TESSERE: come si mostrano. Una tessera usa una misura (o la somma di più
    misure) e porta dentro il dettaglio: per commodity (lampadina / fiamma,
    regola del Cruscotto: nessuna tessera divisa per commodity) o altre
    righe (insoluto 12 mesi, churn medio/max/min, LTV attivi/cessati).

Natura (serve a ricavare il valore del singolo mese dai dati year-to-date):
  * flusso   cumulato da inizio anno: mese = YTD(m) - YTD(m-1)
  * stock    consistenza a fine periodo (PFN, liquidità, punti attivi)
  * rapporto percentuali, medie, durate: non si sottraggono
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SOCIETA = {"lifegate": "LifeGate Energy", "gazel": "Gazel", "migliora": "Migliora"}
ORDINE_SOCIETA = ["lifegate", "gazel", "migliora"]


@dataclass(frozen=True)
class Misura:
    codice: str
    etichetta: str            # come nel foglio (si confronta normalizzata)
    rif: str                  # "M" (mese del report) o "M-1" (mese precedente)
    unita: str                # "€", "%", "N.", "MWh", "mesi", "€/cliente"
    natura: str               # "flusso" | "stock" | "rapporto"
    prefisso: bool = False    # etichetta che continua con testo variabile


MISURE: list[Misura] = [
    # ---------------- Livello I · Finanziario ----------------
    Misura("EBITDA", "EBITDA M -1", "M-1", "€", "flusso"),
    Misura("PFN", "PFN M -1", "M-1", "€", "stock"),
    Misura("LIQUIDITA", "DISPONIBILITA' LIQUIDE M -1", "M-1", "€", "stock"),
    Misura("DEBITI_NEWATT", "DEBITI VERSO NEWATT M-1", "M-1", "€", "stock"),
    Misura("INSOLUTO", "% INSOLUTO adj M-1", "M-1", "%", "rapporto"),
    Misura("INSOLUTO_12M", "% INSOLUTO 12 MESI adj", "M-1", "%", "rapporto"),
    Misura("PERDITE_CREDITI", "PERDITE SU CREDITI M-1", "M-1", "€", "flusso"),
    # ---------------- Livello I · Vendite ----------------
    Misura("SALES_BP", "SALES/BP TOTALE M", "M", "%", "rapporto"),
    Misura("SALES_BP_EE", "SALES/BP ENERGIA ELETTRICA M", "M", "%", "rapporto"),
    Misura("SALES_BP_GAS", "SALES/BP GAS NATURALE M", "M", "%", "rapporto"),
    Misura("CHURN", "CHURN PDP M", "M", "%", "rapporto"),
    Misura("CHURN_EE", "CHURN ENERGIA ELETTRICA M", "M", "%", "rapporto"),
    Misura("CHURN_GAS", "CHURN GAS NATURALE M", "M", "%", "rapporto"),
    Misura("CHURN_PROGR", "CHURN PROGRESSIVO", "M", "%", "rapporto"),
    Misura("CHURN_MEDIO", "CHURN MEDIO", "M", "%", "rapporto"),
    Misura("CHURN_MAX", "CHURN MAX", "M", "%", "rapporto", prefisso=True),
    Misura("CHURN_MIN", "CHURN MIN", "M", "%", "rapporto", prefisso=True),
    # ---------------- Livello I · Cliente ----------------
    Misura("COSTO_CLIENTE", "COSTO PER CLIENTE M-1", "M-1", "€/cliente", "rapporto"),
    Misura("CTS", "COST TO SERVE M-1", "M-1", "€/cliente", "rapporto"),
    Misura("LTV", "LTV TOTALE (mesi)", "M", "mesi", "rapporto"),
    Misura("LTV_ATTIVI", "LTV attivi - Fidelizzazione clienti (mesi)", "M", "mesi", "rapporto"),
    Misura("LTV_CESSATI", "LTV cessati - Qualità agenzia (mesi)", "M", "mesi", "rapporto"),
    # ---------------- Livello II · Finanziario ----------------
    Misura("FATTURATO", "FATTURATO TOTALE M -1", "M-1", "€", "flusso"),
    Misura("PRIMO_MARGINE", "PRIMO MARGINE LORDO M -1", "M-1", "€", "flusso"),
    Misura("UTILE", "RISULTATO NETTO M -1", "M-1", "€", "flusso"),
    Misura("RESIDUO", "RESIDUO DA PAGARE M -1", "M-1", "€", "stock"),
    # ---------------- Livello II · Vendite ----------------
    Misura("POD_ATTIVI", "N POD ATTIVI M", "M", "N.", "stock"),
    Misura("PDR_ATTIVI", "N PDR ATTIVI M", "M", "N.", "stock"),
    Misura("PERC_POD", "PERCENTUALE POD ATTIVI", "M", "%", "rapporto"),
    Misura("PERC_PDR", "PERCENTUALE PDR ATTIVI", "M", "%", "rapporto"),
    Misura("MWH_EE", "MWH POWER VENDUTI M - 1", "M-1", "MWh", "flusso"),
    Misura("MWH_GAS", "MWH GAS VENDUTI M - 1", "M-1", "MWh", "flusso"),
    # ---------------- Livello II · Cliente ----------------
    Misura("LTV_EE", "LTV ENERGIA ELETTRICA (mesi)", "M", "mesi", "rapporto"),
    Misura("LTV_GAS", "LTV GAS NATURALE (mesi)", "M", "mesi", "rapporto"),
    Misura("SDD", "PERCENTUALE CLIENTI CON SDD M -1", "M-1", "%", "rapporto"),
    Misura("OFF_VARIABILE", "PERCENTUALE CLIENTI CON OFFERTA VARIABILE (M)", "M", "%", "rapporto"),
    Misura("OFF_FISSA", "PERCENTUALE CLIENTI CON OFFERTA FISSA (M)", "M", "%", "rapporto"),
]
PER_CODICE = {m.codice: m for m in MISURE}


def livello_misura(codice: str) -> int:
    """Livello del foglio DASHBOARD (1 o 2): nel catalogo le misure del
    Livello II iniziano da «FATTURATO TOTALE»."""
    codici = [m.codice for m in MISURE]
    return 1 if codici.index(codice) < codici.index("FATTURATO") else 2


@dataclass(frozen=True)
class Tessera:
    codice: str
    nome: str
    livello: int              # 1 o 2
    ambito: str               # "Finanziario" | "Vendite" | "Cliente"
    misure: tuple             # codici sommati per la cifra principale
    direzione: int = 1        # +1 più alto è meglio, -1 più basso, 0 neutro
    commodity: dict = field(default_factory=dict)   # {"Power": codice, "Gas": codice}
    dettaglio: tuple = ()     # ((etichetta, codice), ...) righe senza icona
    quota: dict = field(default_factory=dict)       # {"Power": codice %} accanto al valore
    definizione: str = ""
    affianco: tuple = ()      # (etichetta, codice): seconda cifra accanto a quella principale

    @property
    def misura(self) -> Misura:
        return PER_CODICE[self.misure[0]]


TESSERE: list[Tessera] = [
    # ======================= LIVELLO I =======================
    Tessera("EBITDA", "EBITDA", 1, "Finanziario", ("EBITDA",),
            definizione="EBITDA da inizio anno a fine mese precedente (M-1)."),
    Tessera("PFN", "PFN", 1, "Finanziario", ("PFN",), direzione=0,
            definizione="Posizione finanziaria netta a fine mese precedente (M-1)."),
    Tessera("LIQUIDITA", "Disponibilità liquide", 1, "Finanziario", ("LIQUIDITA",),
            definizione="Cassa e banche a fine mese precedente (M-1)."),
    Tessera("DEBITI_NEWATT", "Debiti verso NeWatt", 1, "Finanziario", ("DEBITI_NEWATT",),
            direzione=-1, definizione="Debiti verso la capogruppo a fine mese precedente (M-1)."),
    Tessera("INSOLUTO", "% Insoluto adj", 1, "Finanziario", ("INSOLUTO",), direzione=-1,
            dettaglio=(("Ultimi 12 mesi", "INSOLUTO_12M"),),
            definizione="Quota di fatturato non incassato (rettificata) al mese precedente; "
                        "nel dettaglio la media degli ultimi 12 mesi."),
    Tessera("PERDITE_CREDITI", "Perdite su crediti", 1, "Finanziario", ("PERDITE_CREDITI",),
            definizione="Perdite e accantonamenti su crediti da inizio anno (M-1)."),
    Tessera("SALES_BP", "Sales/BP", 1, "Vendite", ("SALES_BP",),
            commodity={"Power": "SALES_BP_EE", "Gas": "SALES_BP_GAS"},
            definizione="Vendite da inizio anno rispetto all'obiettivo del business plan, "
                        "totale energia elettrica e gas naturale."),
    Tessera("CHURN", "Churn PdP", 1, "Vendite", ("CHURN",), direzione=-1,
            commodity={"Power": "CHURN_EE", "Gas": "CHURN_GAS"},
            definizione="Punti di prelievo cessati nel mese sul portafoglio, energia elettrica e gas."),
    Tessera("CHURN_PROGR", "Churn progressivo", 1, "Vendite", ("CHURN_PROGR",), direzione=-1,
            dettaglio=(("Medio", "CHURN_MEDIO"), ("Massimo", "CHURN_MAX"), ("Minimo", "CHURN_MIN")),
            definizione="Churn cumulato da inizio anno; nel dettaglio media, massimo e minimo mensile."),
    Tessera("COSTO_CLIENTE", "Costo per cliente", 1, "Cliente", ("COSTO_CLIENTE",), direzione=-1,
            definizione="Costo complessivo per cliente al mese precedente (M-1)."),
    Tessera("CTS", "Cost to serve", 1, "Cliente", ("CTS",), direzione=-1,
            definizione="Costo di servizio per cliente al mese precedente (M-1)."),
    Tessera("LTV", "LTV totale", 1, "Cliente", ("LTV",),
            commodity={"Power": "LTV_EE", "Gas": "LTV_GAS"},
            dettaglio=(("Clienti attivi · fidelizzazione", "LTV_ATTIVI"),
                       ("Clienti cessati · qualità agenzia", "LTV_CESSATI")),
            definizione="Durata media della relazione con il cliente, in mesi."),
    # ======================= LIVELLO II =======================
    Tessera("FATTURATO", "Fatturato totale", 2, "Finanziario", ("FATTURATO",),
            definizione="Fatturato da inizio anno (M-1)."),
    Tessera("PRIMO_MARGINE", "Primo margine lordo", 2, "Finanziario", ("PRIMO_MARGINE",),
            definizione="Primo margine lordo da inizio anno (M-1)."),
    Tessera("UTILE", "Risultato netto", 2, "Finanziario", ("UTILE",),
            definizione="Risultato netto da inizio anno (M-1)."),
    Tessera("RESIDUO", "Residuo da pagare", 2, "Finanziario", ("RESIDUO",), direzione=-1,
            definizione="Importi ancora da pagare a fine mese precedente (M-1)."),
    Tessera("PDP_ATTIVI", "Punti attivi", 2, "Vendite", ("POD_ATTIVI", "PDR_ATTIVI"),
            commodity={"Power": "POD_ATTIVI", "Gas": "PDR_ATTIVI"},
            quota={"Power": "PERC_POD", "Gas": "PERC_PDR"},
            affianco=("Churn progressivo", "CHURN_PROGR"),
            definizione="POD e PDR in fornitura a fine mese; accanto il churn progressivo "
                        "(totale da inizio anno, non quello del mese)."),
    Tessera("ENERGIA", "Energia venduta", 2, "Vendite", ("MWH_EE", "MWH_GAS"),
            commodity={"Power": "MWH_EE", "Gas": "MWH_GAS"},
            definizione="MWh di energia elettrica e gas venduti da inizio anno (M-1)."),
    Tessera("SDD", "Clienti con SDD", 2, "Cliente", ("SDD",),
            definizione="Quota di clienti con addebito diretto (SDD) sul fatturato mensile (M-1)."),
    Tessera("OFFERTA", "Clienti con offerta variabile", 2, "Cliente", ("OFF_VARIABILE",),
            direzione=0, dettaglio=(("Offerta variabile", "OFF_VARIABILE"),
                                    ("Offerta fissa", "OFF_FISSA")),
            definizione="Ripartizione dei clienti per tipo di offerta."),
]
PER_TESSERA = {t.codice: t for t in TESSERE}
AMBITI = ["Finanziario", "Vendite", "Cliente"]


def tessere(livello: int, ambito: Optional[str] = None) -> list[Tessera]:
    return [t for t in TESSERE if t.livello == livello and (ambito is None or t.ambito == ambito)]


def competenza(anno: int, mese: int, rif: str) -> tuple[int, int]:
    """Mese di competenza di una misura nel report del mese (anno, mese)."""
    if rif == "M-1":
        return (anno - 1, 12) if mese == 1 else (anno, mese - 1)
    return anno, mese
