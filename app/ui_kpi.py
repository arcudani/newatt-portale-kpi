"""
Interfaccia del Portale KPI NeWatt: dashboard di società e panoramica di
gruppo, sui valori storicizzati in cte-newatt (kpi_dati).

Ogni riquadro (una Tessera del catalogo) mostra il valore year-to-date del
mese del report scelto, il mese di competenza (M o M-1), il dettaglio per
commodity o le righe di dettaglio, e il confronto con il report precedente:
  * flussi (EBITDA, fatturato, MWh…): il valore del SOLO mese, ricavato per
    differenza tra due YTD dello stesso anno;
  * stock e rapporti: la variazione rispetto al report precedente.
Semaforo: se per la società e l'anno del report c'è un obiettivo (pagina
«Obiettivi KPI», tabella kpi_obiettivi) lo stato è In target / Da
attenzionare / Critico; senza obiettivo resta «Consuntivo» (dato presente) o
«In attesa» (dato mancante).
"""
from __future__ import annotations

import dataclasses
from html import escape
from typing import Optional

import pandas as pd
import streamlit as st

import branding
import formato as fmt
import kpi_catalogo as kc
import kpi_dati
import kpi_obiettivi as ko
import registro_moduli

MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"]
COMMODITY_SLICER = {"Tutte": None, "Energia elettrica": "Power", "Gas naturale": "Gas"}
# tema grafico di ogni società (design system NeWatt + identità della società)
TEMA = {"lifegate": "lifegate", "gazel": "gazel", "migliora": "migliora_kpi"}
CONTATORI = [("ok", "In target"), ("warn", "Da attenzionare"), ("crit", "Critico"),
             ("bp", "Senza obiettivo"), ("pend", "Dato mancante")]


def mese_lungo(anno: int, mese: int) -> str:
    return f"{MESI_IT[mese - 1]} {anno}"


def _testo_valore(v: Optional[float], unita: str) -> str:
    if v is None or pd.isna(v):
        return "—"
    numero, piccola = fmt.formatta(v, unita)
    return f"{numero} {piccola}".strip()


def _mappa(df: pd.DataFrame, anno: int, mese: int) -> dict:
    """codice -> (valore, testo, anno_comp, mese_comp) di un report."""
    sel = df[(df["anno"] == anno) & (df["mese"] == mese)]
    return {r.codice: (None if pd.isna(r.valore) else float(r.valore), r.testo,
                       int(r.anno_comp), int(r.mese_comp)) for r in sel.itertuples()}


def _somma(mappa: dict, codici) -> Optional[float]:
    vals = [mappa.get(c, (None,))[0] for c in codici]
    return None if any(v is None for v in vals) else float(sum(vals))


def modello(t: kc.Tessera, attuale: dict, precedente: dict, serie: list,
            commodity: Optional[str] = None, obiettivo: Optional[tuple] = None) -> dict:
    """Riquadro di una tessera per il report scelto (attuale) rispetto al
    report precedente dello stesso anno (precedente, può essere vuoto).
    obiettivo = (direzione, obiettivo, soglia) della società per l'anno del
    report: accende il semaforo (non sul dettaglio di una sola commodity)."""
    m = t.misura
    codici = t.misure
    ripartito = commodity is not None and commodity in t.commodity
    if ripartito:
        codici = (t.commodity[commodity],)
    valore = _somma(attuale, codici)
    prima = _somma(precedente, codici) if precedente else None
    comp = attuale.get(codici[0])
    vm = {"nome": t.nome, "definizione": t.definizione, "owner": "", "note": [],
          "codice": f"Liv. {'I' if t.livello == 1 else 'II'} · {m.rif}", "split": {},
          "valore": None, "unita": ""}

    # dettaglio per commodity (lampadina / fiamma) e righe di dettaglio
    for c, codice in t.commodity.items():
        if ripartito and c != commodity:
            continue
        testo = _testo_valore(attuale.get(codice, (None,))[0], PER_UNITA(codice))
        if c in t.quota and attuale.get(t.quota[c], (None,))[0] is not None:
            testo += f" · {fmt.pct(attuale[t.quota[c]][0], 1)}"
        vm["split"][c] = testo
    if not ripartito:
        for etichetta, codice in t.dettaglio:
            v = attuale.get(codice)
            testo = _testo_valore(v[0] if v else None, PER_UNITA(codice))
            if v and v[1]:
                testo += f" · {v[1]}"
            vm["split"][etichetta] = testo

    if comp is not None:
        anno_c, mese_c = comp[2], comp[3]
        etichetta_comp = {"flusso": "da inizio anno", "stock": "a fine mese"}.get(m.natura, "")
        vm["rif"] = f"{mese_lungo(anno_c, mese_c)}" + (f" · {etichetta_comp}" if etichetta_comp else "")
    else:
        vm["rif"] = "—"
    if ripartito:
        vm["note"].append(f"Solo {branding.NOME_COMMODITY[commodity].lower()}")
    if t.affianco and not ripartito:      # il churn progressivo non è ripartito per commodity
        etichetta, codice = t.affianco
        v = attuale.get(codice, (None,))[0]
        if v is not None:
            vm["affianco"] = (etichetta, _testo_valore(v, PER_UNITA(codice)))

    if valore is None:
        vm["stato"] = "pend"
        vm["note"].append("Dato mancante nel foglio DASHBOARD di questo mese.")
        return vm

    numero, piccola = fmt.formatta_hero(valore, m.unita)
    vm.update(stato="bp", label_stato="Consuntivo", valore=numero, unita=piccola)
    if obiettivo is not None and not ripartito and comp is not None:
        d, ob, so = obiettivo
        ob_m = ko.obiettivo_al_mese(ob, m.natura, comp[3])
        so_m = None if so is None else ko.obiettivo_al_mese(so, m.natura, comp[3])
        vm["stato"] = ko.stato(valore, d, ob_m, so_m)
        vm.pop("label_stato")
        segno = "≥" if d == 1 else "≤"
        testo = f"Obiettivo {comp[2]}: {segno} {_testo_valore(ob, m.unita)}"
        if m.natura == "flusso" and comp[3] < 12:
            testo += f" (a {MESI_IT[comp[3] - 1]}: {_testo_valore(ob_m, m.unita)})"
        if so is not None:
            testo += f" · attenzione {'sotto' if d == 1 else 'sopra'} {_testo_valore(so_m, m.unita)}"
        vm["note"].append(testo)

    # confronto con il report precedente
    if prima is not None and comp is not None:
        prec_comp = precedente.get(codici[0])
        if m.natura == "flusso":
            if prec_comp and prec_comp[2] == comp[2]:      # stesso anno: mese = differenza
                nel_mese = valore - prima
                vm["note"].insert(0, f"Nel solo mese di {MESI_IT[comp[3] - 1]}: "
                                     f"{_testo_valore(nel_mese, m.unita)}")
        else:
            diff = valore - prima
            if abs(diff) > 1e-12:
                tono = ("neutro" if t.direzione == 0 else
                        "buono" if diff * t.direzione > 0 else "cattivo")
                freccia = "▲" if diff > 0 else "▼"
                vm["delta"] = (f"{freccia} {fmt.formatta_delta(diff, diff / prima if prima else None, m.unita)}"
                               f" vs {MESI_IT[prec_comp[3] - 1]}", tono)
    elif comp is not None and m.natura == "flusso" and comp[3] == 1:
        vm["note"].insert(0, "Primo mese dell'anno: il dato YTD è il valore del mese.")

    if len([v for v in serie if v is not None]) >= 2 and not ripartito:
        vm["spark"] = branding.sparkline(serie)
    return vm


def PER_UNITA(codice: str) -> str:
    return kc.PER_CODICE[codice].unita


def _serie(df: pd.DataFrame, t: kc.Tessera, anno: int, fino_a: int) -> list:
    """Valori della tessera nei report dell'anno fino al mese scelto: per i
    flussi il valore di ogni singolo mese, per gli altri il valore puntuale."""
    out, prima = [], None
    for mese in range(1, fino_a + 1):
        mappa = _mappa(df, anno, mese)
        v = _somma(mappa, t.misure) if mappa else None
        if t.misura.natura == "flusso" and v is not None:
            # il primo YTD dell'anno vale «un mese» solo a gennaio: altrimenti
            # mescolerebbe il cumulato con i valori mensili (finta caduta)
            out.append(v - prima if prima is not None else (v if mese == 1 else None))
        else:
            out.append(v)
        prima = v if v is not None else prima
    return out


# =============================================================================
# Disegno
# =============================================================================

def _riquadro(chiave: str, vm: dict, dest: Optional[registro_moduli.Modulo] = None) -> None:
    with st.container(key=f"kpi_{chiave}"):
        st.markdown(branding.riquadro_kpi(vm), unsafe_allow_html=True)
        if dest is not None:
            st.page_link(dest.file, label=f"Apri {kc.SOCIETA.get(dest.societa, '')} · {dest.titolo}")


# Logo a colori di ogni società (file in assets/, altezza nel riquadro bianco)
LOGO_SOCIETA = {"lifegate": ("Logo_LifeGate.png", 15), "gazel": ("Logo_Gazel.png", 44),
                "migliora": ("Logo_Migliora_marchio.png", 24)}


def _logo_societa(societa: str) -> str:
    """Logo della società in un riquadro bianco: leggibile su ogni colore."""
    file, altezza = LOGO_SOCIETA[societa]
    b64 = branding._b64(branding.APP_DIR / "assets" / file)
    if not b64:
        return ""
    return ("<span style='display:inline-flex;align-items:center;justify-content:center;"
            "background:#fff;border-radius:12px;padding:8px 12px;margin-bottom:12px;"
            "box-shadow:0 1px 3px rgba(20,22,43,.18);max-width:100%'>"
            f"<img src='data:image/png;base64,{b64}' alt='{escape(kc.SOCIETA[societa])}' "
            f"style='height:{altezza}px;width:auto;max-width:100%;display:block'/></span>")


def _fascia(chiave: str, nome: str, indice: int, voci: list, sotto: str = "",
            logo: str = "") -> None:
    """voci = [(chiave_riquadro, vm, dest)]; stessa struttura delle fasce
    del design system (colonna del titolo + area riquadri auto-fill).
    logo = HTML del logo della società al posto dell'icona dell'ambito."""
    with st.container(key=f"band_{chiave}"):
        with st.container(key=f"bandh_{chiave}_a{indice % 4}"):
            testa = branding.testata_ambito(nome, len(voci))
            if logo:
                testa = logo + testa.split("</svg>", 1)[-1]
            if sotto == "nessun report":     # niente «1 KPI» su una società senza dati
                testa = testa.split("<span class='mg-amb-cnt'>")[0]
            if sotto:
                testa += f"<span class='mg-amb-cnt' style='text-transform:none;letter-spacing:0;" \
                         f"font-weight:600;opacity:.9'>{escape(sotto)}</span>"
            st.markdown(testa, unsafe_allow_html=True)
        with st.container(key=f"bandk_{chiave}"):
            for k, vm, dest in voci:
                _riquadro(k, vm, dest)


def _chips(caricamenti: pd.DataFrame, anno: int, mese: int, n_valori: int) -> str:
    versioni = caricamenti[(caricamenti["anno"] == anno) & (caricamenti["mese"] == mese)
                           & ~caricamenti["annullato"]]
    chips = [f"<span class='mg-chip'>Report <b>{escape(mese_lungo(anno, mese))}</b></span>",
             f"<span class='mg-chip'>Indicatori <b>{n_valori}/{len(kc.MISURE)}</b></span>"]
    if len(versioni) > 1:
        chips.append(f"<span class='mg-chip'>Versione <b>{len(versioni)}</b></span>")
    return "".join(chips)


ROMANI = {1: "I", 2: "II"}


def pagina_societa(societa: str, livello: int = 1) -> None:
    """Pagina di una società per UN livello del foglio DASHBOARD
    (moduli/kpi_<società>.py = Livello I, kpi_<società>_l2.py = Livello II):
    tema, testata, barra filtri, fasce del livello, storico del livello."""
    tema = TEMA[societa]
    branding.applica_tema(tema)
    nome = f"{kc.SOCIETA[societa]} · Livello {ROMANI[livello]}"
    testata = st.empty()     # la testata va SOPRA la barra filtri ma si scrive dopo
    try:
        df = kpi_dati.carica_valori(societa)
        caricamenti = kpi_dati.carica_caricamenti(societa)
    except Exception as e:  # rete/pooler giù: pagina informativa, non crash
        testata.markdown(branding.testata(f"Cruscotto KPI · {nome}", "", "", tema=tema),
                         unsafe_allow_html=True)
        st.error(f"📡 Impossibile leggere i KPI dal database: {e}")
        if st.button("🔄 Riprova"):
            kpi_dati.svuota_cache()
            st.rerun()
        st.stop()

    if df.empty:
        testata.markdown(branding.testata(f"Cruscotto KPI · {nome}", "Nessun report caricato",
                                          "", tema=tema), unsafe_allow_html=True)
        st.markdown(branding.stato_vuoto(
            "Ancora nessun report",
            f"Per {kc.SOCIETA[societa]} non è stato caricato nessun Excel «Dashboard KPI»: il "
            "cruscotto si riempie con il primo caricamento mensile."), unsafe_allow_html=True)
        if st.session_state.get("ruolo") in registro_moduli.CARICANO:
            st.page_link(registro_moduli.PER_CODICE["UP"].file, label="Vai a Carica KPI",
                         icon=":material/upload_file:")
        return

    mesi = sorted({(int(a), int(m)) for a, m in zip(df["anno"], df["mese"])})
    etichette = {f"{mese_lungo(a, m)}": (a, m) for a, m in reversed(mesi)}
    with st.container(key="mg_slicer"):
        c_mese, c_com, c_cnt = st.columns([1.3, 1.3, 3.4], vertical_alignment="bottom")
        scelta = c_mese.selectbox("Mese del report", list(etichette), key=f"kpi_mese_{societa}")
        com = c_com.selectbox("Commodity", list(COMMODITY_SLICER), key=f"kpi_com_{societa}")
    anno, mese = etichette[scelta]
    commodity = COMMODITY_SLICER[com]
    attuale = _mappa(df, anno, mese)
    precedenti = [x for x in mesi if x < (anno, mese)]
    precedente = _mappa(df, *precedenti[-1]) if precedenti else {}

    righe = df[(df["anno"] == anno) & (df["mese"] == mese)]
    ultimo = righe.iloc[0]
    quando = pd.Timestamp(ultimo["caricato_il"])
    quando = quando.tz_convert("Europe/Rome") if quando.tzinfo else quando
    aggiornato = f"Caricato il {quando:%d/%m/%Y · %H:%M} da {ultimo['caricato_da']}"
    n_valori = int(righe["valore"].notna().sum())

    obiettivi = kpi_dati.obiettivi_anno(societa, anno)
    modelli = {t.codice: modello(t, attuale, precedente, _serie(df, t, anno, mese), commodity,
                                 obiettivi.get(t.codice))
               for t in kc.TESSERE if t.livello == livello}
    conteggi: dict[str, int] = {}
    for vm in modelli.values():
        conteggi[vm["stato"]] = conteggi.get(vm["stato"], 0) + 1
    c_cnt.markdown(branding.contatori(conteggi, CONTATORI), unsafe_allow_html=True)

    testata.markdown(
        branding.testata(f"Cruscotto KPI · {nome}", aggiornato,
                         _chips(caricamenti, anno, mese, n_valori), tema=tema),
        unsafe_allow_html=True)

    for i, ambito in enumerate(kc.AMBITI):
        voci = [(f"{societa}_{t.codice}", modelli[t.codice], None)
                for t in kc.tessere(livello, ambito)]
        if voci:
            _fascia(f"{societa}_L{livello}_{i}", ambito, i, voci)

    st.caption("Valori year-to-date del foglio DASHBOARD; «M-1» = mese precedente al report "
               "(dati contabili). Per i flussi la nota dà il valore del solo mese, ricavato per "
               "differenza con il report precedente. Il semaforo si accende sui KPI che hanno un "
               "obiettivo per l'anno (pagina «Obiettivi KPI»); per i flussi da inizio anno "
               "l'obiettivo annuo si confronta in proporzione ai mesi trascorsi.")
    with st.expander(f"Storico dei KPI di Livello {ROMANI[livello]}", expanded=False):
        storico = tabella_storico(df, livello)
        st.dataframe(storico, hide_index=True, width="stretch")
        st.download_button("⬇️ Scarica Excel", _excel(storico), file_name=f"storico_kpi_{societa}_livello_{livello}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"dl_storico_{societa}_{livello}")


def _excel(df: pd.DataFrame) -> bytes:
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Storico KPI", index=False)
    return buf.getvalue()


def tabella_storico(df: pd.DataFrame, livello: Optional[int] = None) -> pd.DataFrame:
    """KPI × mese del report (ultima versione), valori formattati; con
    livello solo le misure di quel livello del foglio DASHBOARD."""
    mesi = sorted({(int(a), int(m)) for a, m in zip(df["anno"], df["mese"])})
    righe = []
    for misura in kc.MISURE:
        liv = kc.livello_misura(misura.codice)
        if livello is not None and liv != livello:
            continue
        riga = {"Livello": ROMANI[liv], "KPI": misura.etichetta, "Rif.": misura.rif}
        for a, m in mesi:
            v = _mappa(df, a, m).get(misura.codice, (None,))[0]
            riga[f"{MESI_IT[m - 1][:3]} {a}"] = _testo_valore(v, misura.unita)
        righe.append(riga)
    return pd.DataFrame(righe)


# =============================================================================
# Panoramica di gruppo
# =============================================================================

TESSERE_PANORAMICA = ("EBITDA", "SALES_BP", "PDP_ATTIVI", "COSTO_CLIENTE")
# seconda cifra, più piccola, accanto a quella principale (solo nella panoramica)
AFFIANCO_PANORAMICA = {"COSTO_CLIENTE": ("Cost to serve", "CTS")}
COLORE_SOCIETA = {"lifegate": "#006454", "gazel": "#354697", "migliora": "#28326f"}


def panoramica(perimetro: list[str]) -> None:
    st.markdown(branding.testata("Portale KPI · Gruppo NeWatt",
                                 "LifeGate Energy · Gazel · Migliora", "", tema="newatt"),
                unsafe_allow_html=True)
    if not perimetro:
        st.warning("Il tuo utente non ha società assegnate: chiedi all'amministratore.")
        return
    st.markdown("<style>" + "".join(
        f"div[class*='st-key-bandh_G_{s}'] {{ --amb:{COLORE_SOCIETA[s]} !important; }}"
        for s in perimetro) + "</style>", unsafe_allow_html=True)
    for i, societa in enumerate(perimetro):
        nome = kc.SOCIETA[societa]
        dest = registro_moduli.PER_SOCIETA[societa]          # Livello I
        try:
            df = kpi_dati.carica_valori(societa)
        except Exception as e:
            st.error(f"📡 {nome}: impossibile leggere i KPI ({e}).")
            continue
        if df.empty:
            vm = {"nome": nome, "stato": "pend", "valore": None, "rif": "nessun report caricato",
                  "note": ["Carica l'Excel «Dashboard KPI» dalla pagina Carica KPI."],
                  "codice": "—", "owner": "", "split": {}}
            _fascia(f"G_{societa}", nome, i, [(f"G_{societa}_vuoto", vm, dest)], "nessun report",
                    logo=_logo_societa(societa))
            continue
        mesi = sorted({(int(a), int(m)) for a, m in zip(df["anno"], df["mese"])})
        anno, mese = mesi[-1]
        attuale = _mappa(df, anno, mese)
        precedente = _mappa(df, *mesi[-2]) if len(mesi) > 1 else {}
        obiettivi = kpi_dati.obiettivi_anno(societa, anno)
        voci = []
        for codice in TESSERE_PANORAMICA:
            t = kc.PER_TESSERA[codice]
            if codice in AFFIANCO_PANORAMICA:
                t = dataclasses.replace(t, affianco=AFFIANCO_PANORAMICA[codice])
            voci.append((f"G_{societa}_{codice}",
                         modello(t, attuale, precedente, _serie(df, t, anno, mese),
                                 obiettivo=obiettivi.get(codice)),
                         registro_moduli.PER_SOCIETA_LIVELLO[(societa, t.livello)]))
        _fascia(f"G_{societa}", nome, i, voci, f"report {mese_lungo(anno, mese)}",
                logo=_logo_societa(societa))
    st.caption("Clicca un riquadro per aprire il cruscotto completo della società.")
