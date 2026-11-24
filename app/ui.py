"""
Componenti di interfaccia condivisi dalle viste, nel linguaggio del Migliora
Design System e dell'handoff «Dashboard KPI Migliora — Riquadri esecutivi»:
testata blu con logo bianco e claim, barra filtri a slicer con contatori per
stato (Cruscotto), fasce per ambito con la colonna del titolo colorata,
riquadri KPI tutti uguali, pannelli ed export.

Regole del blueprint applicate qui una volta sola:
  * stato dati sempre visibile in testata (§8);
  * riquadri generati dal CATALOGO: nome, definizione, owner, direzione,
    soglie, benchmark, ambito, segnaposto (§6-§7);
  * semaforo con testo, mai solo colore (§3), e acceso solo contro un
    riferimento reale: versione di confronto, benchmark del catalogo, piano
    (avvisi del KPI). Il BP senza riferimento è «Valore BP», non «In target»;
  * n.d. con motivo, mai 0 o #DIV/0! (§3).
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from html import escape
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

import bp_calcoli as bc
import bp_dati
import branding
import filtri
import formato as fmt
import registro_moduli
from filtri import Contesto

LIVELLO_DI = {"V1": "3", "V2": "30", "V3": "30", "V4": "30", "V5": "30"}
ETICHETTA_LIVELLO = {"3": "L3 · 3 secondi", "30": "L30 · 30 secondi",
                     "300": "L300 · 300 secondi"}
PILLOLE_LIVELLO = [("3", "3″ Direzione", "V1"), ("30", "30″ Responsabili", "V2"),
                   ("300", "300″ Operativi", "V6")]
AUDIENCE = {
    "V1": "AD e CdA Migliora · Direzione NeWatt · Bros (advisor)",
    "V2": "CFO · Controller", "V3": "Direttore Commerciale",
    "V4": "Responsabile VAS", "V5": "COO · Operations",
    "V6": "Controllo di gestione · analisti Bros", "V7": "Responsabili di canale",
    "V8": "Responsabile VAS", "V9": "Operations · Customer Care · Amministrazione",
    "V10": "Amministrazione · analisti Bros", "V11": "Bros · Direzione",
    "CAT": "Tutti i livelli",
}
STATO_TESTO = {"ok": "● in linea", "warn": "▲ attenzione", "crit": "■ critico",
               "neutral": "○ —"}
TITOLO_CRUSCOTTO = "Cruscotto KPI · DeD"
# Slicer Commodity del Cruscotto: etichetta -> commodity del modello dati
COMMODITY_SLICER = {"Tutte": None, "Energia elettrica": "Power", "Gas naturale": "Gas"}
TONO_STATO = {"buono": "ok", "attenzione": "warn", "cattivo": "crit"}


def carica_contesto() -> Contesto:
    """Contesto della vista; se il DB non risponde: messaggio + Riprova + stop."""
    try:
        return filtri.contesto()
    except Exception as e:  # rete/pooler giù: pagina informativa, non crash
        st.error(f"📡 Impossibile leggere i dati del BP: {e}")
        if st.button("🔄 Riprova"):
            bp_dati.svuota_cache()
            st.rerun()
        st.stop()


def voci_riservate(ctx: Contesto) -> set[str]:
    """Voci CE fuori dal perimetro del viewer NeWatt (blueprint §9): il
    dettaglio del contratto di servizio intragruppo."""
    return set() if ctx.bros else {"srv_newatt"}


# =============================================================================
# Testata: barra blu con logo, claim, aggiornamento e stato dati
# =============================================================================

def _chip(testo: str, classe: str = "", colore: str = "") -> str:
    swatch = f"<i style='--c:{colore}'></i>" if colore else ""
    return f"<span class='mg-chip {classe}'>{swatch}{testo}</span>"


def _chips_stato(ctx: Optional[Contesto]) -> str:
    if ctx is None or ctx.versione is None:
        return ""
    v = ctx.versione
    quando = ""
    if v["stato"] == "approvata" and not fmt.manca(v.get("stato_il")) and v.get("stato_il") is not None:
        quando = f" · {pd.Timestamp(v['stato_il']):%d/%m/%Y}"
    chips = [_chip(f"BP <b>{escape(v['nome'])}</b> · {v['stato']}{quando}",
                   "" if v["stato"] == "approvata" else "warn", branding.C_BP)]
    if ctx.confronto:
        chips.append(_chip(f"Confronto <b>{escape(ctx.confronto['nome'])}</b>", "",
                           branding.C_CONFRONTO))
    q = v.get("quadratura") or []
    n_ok = sum(1 for x in q if x.get("ok"))
    if v.get("quadratura_ok"):
        chips.append(_chip(f"Quadratura Excel <b>OK</b> {n_ok}/{len(q)}"))
    else:
        chips.append(_chip(f"Quadratura Excel <b>KO</b> · {len(q) - n_ok} fuori tolleranza", "crit"))
    chips.append(_chip("Consuntivo <b>non caricato</b> · fase 3"))
    return "".join(chips)


def _aggiornato(ctx: Optional[Contesto]) -> str:
    """«Aggiornato al …»: ultimo movimento della versione letta (import o
    cambio di stato), in ora italiana."""
    if ctx is None or ctx.versione is None:
        return ""
    v = ctx.versione
    tempi = []
    for campo in ("created_at", "stato_il"):
        t = v.get(campo)
        if t is not None and pd.notna(t):
            t = pd.Timestamp(t)
            tempi.append(t.tz_convert("Europe/Rome") if t.tzinfo else t)
    return f"Aggiornato al {max(tempi):%d/%m/%Y · %H:%M}" if tempi else ""


def testata(codice_vista: str, domanda: str, ctx: Optional[Contesto],
            livello: Optional[str] = None) -> None:
    """Testata blu dell'handoff. Il Cruscotto (V1) è solo testata + barra
    filtri + fasce; le altre viste aggiungono titolo, domanda, destinatari e
    selettore di livello 3″/30″/300″."""
    m = registro_moduli.PER_CODICE[codice_vista]
    branding.applica_tema("migliora")   # nel portale NeWatt il BP resta nello stile Migliora
    if codice_vista == "V1":
        st.markdown(branding.testata(TITOLO_CRUSCOTTO, _aggiornato(ctx), _chips_stato(ctx)),
                    unsafe_allow_html=True)
        return
    liv = LIVELLO_DI.get(codice_vista, "300")
    etichetta = livello or ETICHETTA_LIVELLO[liv]
    periodo = ""
    if ctx is not None and ctx.versione is not None:
        p = ctx.periodo
        periodo = " · " + fmt.periodo_label(p.anno, p.mese_da, p.mese_a)
    st.markdown(branding.testata("Controllo del Business Plan", _aggiornato(ctx),
                                 _chips_stato(ctx)), unsafe_allow_html=True)
    st.title(f"{m.icona} {m.titolo}")
    st.markdown(f"<div class='mg-dom'>{escape(domanda)}</div>"
                f"<div class='mg-aud'>{escape(AUDIENCE.get(codice_vista, ''))} · "
                f"{escape(etichetta)}{escape(periodo)}</div>", unsafe_allow_html=True)
    _pillole_livello(liv)


def _pillole_livello(livello: str) -> None:
    """3″ / 30″ / 300″ come gruppo a pillola: il clic cambia vista tenendo
    i filtri globali (navigazione interna, non ricaricamento)."""
    try:
        contenitore = st.container(horizontal=True, key="mg_liv")
    except TypeError:      # Streamlit senza container orizzontali
        contenitore = st.container(key="mg_liv")
    with contenitore:
        for liv, etichetta, vista in PILLOLE_LIVELLO:
            chiave = "liv_on" if liv == livello else f"liv_off_{liv}"
            with st.container(key=chiave):
                st.page_link(registro_moduli.PER_CODICE[vista].file, label=etichetta)


def richiedi_versione(ctx: Contesto) -> None:
    """Stato vuoto: nessuna versione visibile al ruolo -> spiegazione + stop."""
    if ctx.versione is not None:
        return
    if ctx.bros:
        st.info("Nessuna versione del BP caricata. Importa l'Excel dalla vista "
                "**Versioni** (o con `importa_bp.py`).")
        st.page_link(registro_moduli.PER_CODICE["V11"].file, label="Vai a Versioni", icon="🗂️")
    else:
        st.info("Nessuna versione del BP è ancora stata approvata da Bros: "
                "la dashboard si popola appena ne viene approvata una.")
    st.stop()


# =============================================================================
# Riquadri KPI: modello (stato, cifra, Rif., note) e disegno
# =============================================================================

def _badge_tendenza(ctx: Contesto, r: pd.Series, ma, mb, conf) -> Optional[tuple[str, str]]:
    """Delta sotto la cifra: vs versione di confronto se c'è, altrimenti vs
    stesso periodo dell'anno precedente. -> (testo, tono)."""
    if conf is not None and mb is not None and not fmt.manca(conf.assoluto):
        return (f"{fmt.formatta_delta(conf.assoluto, conf.relativo, r['unita'])} vs {ctx.nome_b}",
                branding.STATO_TONO.get(conf.stato, "neutro"))
    t = bc.tendenza(r["codice"], ctx.a, ctx.periodo, r["unita"], int(r["direzione"]))
    return (t.testo, t.tono) if t else None


def _cifra(valore: Optional[float], unita: str) -> tuple[str, str]:
    numero, piccola = fmt.formatta_hero(valore, unita)
    return numero, piccola


def _rif_benchmark(r: pd.Series) -> str:
    lo, hi = r.get("bench_min"), r.get("bench_max")
    u = r["unita"]
    euro = " €" if u.startswith("€") else ""
    if not fmt.manca(lo) and not fmt.manca(hi):
        return f"benchmark {bc._fmt_bench(lo, u)}–{bc._fmt_bench(hi, u)}{euro}"
    if not fmt.manca(lo):
        return f"obiettivo ≥ {bc._fmt_bench(lo, u)}{euro}"
    return f"obiettivo ≤ {bc._fmt_bench(hi, u)}{euro}"


def _valore_commodity(m, commodity: Optional[str]) -> tuple[Optional[float], dict, bool]:
    """(valore, dettaglio, ripartito) della misura per lo slicer Commodity:
    sui KPI con dettaglio la cifra diventa quella della commodity scelta."""
    if m is None:
        return None, {}, False
    if commodity is None or commodity not in m.commodity:
        return m.valore, dict(m.commodity), False
    return m.commodity_valori.get(commodity), {commodity: m.commodity[commodity]}, True


def _modello(ctx: Contesto, r: pd.Series, commodity: Optional[str] = None,
             grafici: bool = True) -> dict:
    """Tutto quello che il riquadro mostra, già deciso: stato (ok, warn,
    crit, bp, pend), cifra, Rif., note, dettaglio per commodity."""
    codice, unita, direzione = r["codice"], r["unita"], int(r["direzione"])
    segnaposto = r["stato"] == "segnaposto"
    ma = bc.calcola(codice, ctx.a, ctx.periodo, ctx.a)
    mb = bc.calcola(codice, ctx.b, ctx.periodo, ctx.a) if ctx.b is not None else None
    va, split, ripartito = _valore_commodity(ma, commodity)
    vb = _valore_commodity(mb, commodity)[0] if mb is not None else None
    conf = None
    if ma is not None and mb is not None:
        conf = bc.confronta(va, vb, unita, direzione, r["soglia_gialla"], r["soglia_rossa"])
    vm = {"nome": r["nome"], "owner": r["owner"], "definizione": str(r["definizione"]),
          "split": split, "note": [], "unita": "", "valore": None,
          "codice": r["rif_ded"] or ("Segnaposto" if segnaposto and (ma is None or fmt.manca(va))
                                     else "Ipotesi BP" if segnaposto else "—")}
    if commodity is not None:
        nome_c = branding.NOME_COMMODITY[commodity]
        vm["note"].append(f"Solo {nome_c.lower()}" if ripartito
                          else "Valore totale: non ripartito per commodity")

    # --- In attesa dati: segnaposto senza valore (o senza calcolo) ---
    if ma is None or (fmt.manca(va) and segnaposto):
        vm["stato"] = "pend"
        vm["rif"] = (ma.rif if ma is not None and ma.rif else "da definire")
        if ripartito and ma is not None and ma.rif:
            vm["rif"] = f"{split[commodity]} · {fmt.periodo_label(ctx.periodo.anno, ctx.periodo.mese_da, ctx.periodo.mese_a)}"
        if ma is not None and ma.motivo:
            vm["note"].append(ma.motivo)
        vm["note"].append(f"Fonte: {r['fonte_prevista'] or r['fonte']}")
        return vm

    # --- Valore non calcolabile (es. anno di avviamento) ---
    if fmt.manca(va):
        vm.update(stato="pend", label_stato="Non calcolabile", valore="n.d.", nd=True,
                  rif=ma.rif or "da definire")
        vm["note"].append(ma.motivo or "valore non calcolabile")
        return vm

    numero, piccola = _cifra(va, unita)
    vm.update(valore=numero, unita=piccola)
    if grafici and ma.serie and not ripartito:
        vm["spark"] = branding.sparkline(ma.serie, mb.serie if mb is not None else None)
    tend = _badge_tendenza(ctx, r, ma, mb, conf) if not ripartito else None
    if tend:
        vm["delta"] = tend

    bench = bc.avviso_benchmark(va, unita, direzione, r.get("bench_min"), r.get("bench_max"))
    propri = sorted(ma.avvisi, key=lambda b: {"cattivo": 0, "attenzione": 1}.get(b.tono, 2))
    trend = bc.avviso_trend(ma.serie, ctx.periodo.anno, ctx.periodo.mese_a, direzione)
    if conf is not None and conf.stato in ("ok", "warn", "crit"):
        # 1) versione di confronto: il riferimento è il suo valore
        vb_num, vb_u = _cifra(vb, unita)
        vm.update(stato=conf.stato, rif=f"{ctx.nome_b}: {vb_num} {vb_u}".strip())
    elif bench is not None and bench.tono in TONO_STATO:
        # 2) benchmark del catalogo (es. Cost-to-Serve 10-15 €)
        vm.update(stato=TONO_STATO[bench.tono], rif=_rif_benchmark(r))
        vm["pill"] = (bench.testo.lstrip("! "), bench.tono)
    elif propri and propri[0].tono in TONO_STATO:
        # 3) avviso del KPI contro il piano (es. FTE da driver vs pianificati)
        vm.update(stato=TONO_STATO[propri[0].tono], rif="piano del BP")
        vm["pill"] = (propri[0].testo.lstrip("! "), propri[0].tono)
    elif segnaposto:
        # 4) ipotesi del BP su un dato che arriverà dalle fonti operative
        vm.update(stato="bp", label_stato="Ipotesi BP", rif=f"ipotesi BP {numero} {piccola}".strip())
    else:
        # 5) valore del piano senza un target: niente semaforo
        vm.update(stato="bp", rif=ma.rif or "da definire")
    if "pill" not in vm:
        altro = propri[0] if propri else trend
        if altro is not None:
            vm["pill"] = (altro.testo.lstrip("! "), altro.tono)
    for testo in (ma.sub, ma.nota):
        if testo and not ripartito:
            vm["note"].append(testo)
    return vm


def modelli(ctx: Contesto, vista: str, stato: Optional[str] = None,
            commodity: Optional[str] = None, grafici: bool = True) -> list[tuple[pd.Series, dict]]:
    """Righe del catalogo della vista con il modello del loro riquadro."""
    cat = ctx.catalogo[ctx.catalogo["vista"] == vista]
    if stato:
        cat = cat[cat["stato"] == stato]
    return [(r, _modello(ctx, r, commodity, grafici))
            for _, r in cat.sort_values("ordine").iterrows()]


def _riquadro(r: pd.Series, vm: dict, drill: bool) -> None:
    dest = registro_moduli.PER_CODICE.get(r["drill"]) if drill and r["drill"] else None
    with st.container(key=f"kpi_{r['codice']}"):
        st.markdown(branding.riquadro_kpi(vm), unsafe_allow_html=True)
        if dest is not None:
            st.page_link(dest.file, label=f"Apri {dest.titolo}")


def _griglia(righe: list[tuple[pd.Series, dict]], per_riga: int, drill: bool) -> None:
    for inizio in range(0, len(righe), per_riga):
        colonne = st.columns(per_riga, gap="small")
        for col, (r, vm) in zip(colonne, righe[inizio:inizio + per_riga]):
            with col:
                _riquadro(r, vm, drill)


def tessere(ctx: Contesto, codici: list[str], per_riga: int, drill: bool = False) -> None:
    """Griglia di riquadri (senza raggruppamento per ambito)."""
    # drop=False: il riquadro legge r["codice"], che senza questo sparisce
    # nell'indice (KeyError anche nel ripiego di ambiti() sui KPI senza ambito).
    cat = ctx.catalogo.set_index("codice", drop=False)
    presenti = [c for c in codici if c in cat.index]
    _griglia([(cat.loc[c], _modello(ctx, cat.loc[c])) for c in presenti], per_riga, drill)


def ambiti(ctx: Contesto, vista: str, layout: str = "fasce", drill: bool = False,
           stato: Optional[str] = None, per_riga: int = 3,
           righe: Optional[list[tuple[pd.Series, dict]]] = None) -> None:
    """Una fascia per ambito (handoff): a sinistra la colonna colorata con il
    titolo e il numero di KPI, a destra i riquadri. `righe` = modelli già
    calcolati (il Cruscotto li calcola prima per i contatori). `layout` è
    tenuto per compatibilità: tutte le viste usano le fasce."""
    righe = righe if righe is not None else modelli(ctx, vista, stato)
    if not righe:
        return
    if not any(str(r["ambito"]).strip() for r, _ in righe):   # catalogo senza ambiti
        _griglia(righe, per_riga, drill)
        return
    tutti = ctx.catalogo[ctx.catalogo["vista"] == vista]
    ordine = tutti.groupby("ambito")["ordine"].min().sort_values().index.tolist()
    gruppi: dict[str, list] = {}
    for r, vm in righe:
        gruppi.setdefault(r["ambito"], []).append((r, vm))
    for nome in sorted(gruppi, key=lambda a: ordine.index(a) if a in ordine else 99):
        i = ordine.index(nome) if nome in ordine else len(ordine)
        chiave = f"{vista}_{stato or 'tutti'}_{i}"
        # colonna del titolo + area riquadri affiancate; quanti riquadri per
        # riga lo decide il CSS sulla larghezza disponibile (auto-fill)
        with st.container(key=f"band_{chiave}"):
            with st.container(key=f"bandh_{chiave}_a{i % 4}"):
                st.markdown(branding.testata_ambito(nome, len(gruppi[nome])),
                            unsafe_allow_html=True)
            with st.container(key=f"bandk_{chiave}"):
                for r, vm in gruppi[nome]:
                    _riquadro(r, vm, drill)


def tessere_vista(ctx: Contesto, vista: str, per_riga: int = 3, stato: Optional[str] = None,
                  drill: bool = False, layout: str = "fasce") -> None:
    ambiti(ctx, vista, layout=layout, drill=drill, stato=stato, per_riga=per_riga)


def barra_filtri_cruscotto(ctx: Contesto) -> list[tuple[pd.Series, dict]]:
    """Barra filtri dell'handoff: slicer Periodo (dai filtri globali),
    Commodity (filtra i riquadri: sui KPI con dettaglio la cifra diventa
    quella della commodity), Canale (unico canale con dati nel BP) e, a
    destra, i contatori per stato calcolati sui riquadri visibili."""
    p = ctx.periodo
    with st.container(key="mg_slicer"):
        c_per, c_com, c_can, c_cnt = st.columns([1.15, 1.15, 1.15, 3.2],
                                                vertical_alignment="center")
        c_per.markdown(branding.slicer("Periodo",
                                       f"{fmt.periodo_label(p.anno, p.mese_da, p.mese_a)} · LTM"),
                       unsafe_allow_html=True)
        scelta = c_com.selectbox("Commodity", list(COMMODITY_SLICER), key="f_commodity")
        c_can.selectbox("Canale", ["Agenti"], key="f_canale", disabled=True,
                        help="Unico canale con KPI nel BP: il canale VAS vende servizi agli "
                             "stessi clienti (vista VAS).")
        righe = modelli(ctx, "V1", commodity=COMMODITY_SLICER[scelta], grafici=False)
        conteggi: dict[str, int] = {}
        for _, vm in righe:
            conteggi[vm["stato"]] = conteggi.get(vm["stato"], 0) + 1
        c_cnt.markdown(branding.contatori(conteggi), unsafe_allow_html=True)
    return righe


# =============================================================================
# Pannelli, note, barre, export
# =============================================================================

def _senza_emoji(testo: str) -> str:
    """Titoli dei pannelli senza l'emoji iniziale (stile Migliora: niente emoji)."""
    parti = testo.split(" ", 1)
    return parti[1] if len(parti) == 2 and not parti[0][:1].isalnum() else testo


@contextmanager
def pannello(titolo: str, chiave: str):
    with st.container(border=False, key=f"panel_{chiave}"):
        st.markdown(f"<div class='mg-panel-title'>{escape(_senza_emoji(titolo))}</div>",
                    unsafe_allow_html=True)
        yield


def nota(html: str) -> None:
    """Riquadro di nota: azzurro tenue con bordo sinistro azzurro (brand book)."""
    st.markdown(
        f"<div style='font-size:14px;color:{branding.INK};background:{branding.AZZURRO_TENUE};"
        f"border-left:4px solid {branding.AZZURRO};border-radius:12px;padding:12px 16px;"
        f"margin:4px 0 14px;line-height:1.5'>{html}</div>", unsafe_allow_html=True)


def barre(righe: list[dict], colore: str = branding.C_BP) -> None:
    """Barre orizzontali con valore e delta (scomposizioni)."""
    st.markdown(branding.barre(righe, colore), unsafe_allow_html=True)


def excel_bytes(df: pd.DataFrame, foglio: str) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name=foglio[:31], index=False)
    return buf.getvalue()


def scarica(df: pd.DataFrame, nome_file: str, etichetta: str = "⬇️ Scarica Excel") -> None:
    st.download_button(etichetta, excel_bytes(df, nome_file), file_name=f"{nome_file}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=f"dl_{nome_file}")


def legenda_versioni(ctx: Contesto, tratteggio_b: bool = True) -> None:
    items = [("solid", branding.C_BP, ctx.nome_a)]
    if ctx.b is not None:
        items.append(("dash" if tratteggio_b else "box", branding.C_CONFRONTO, ctx.nome_b))
    st.markdown(branding.legenda(items), unsafe_allow_html=True)


# =============================================================================
# Grafici ricorrenti
# =============================================================================

def serie_confronto(ctx: Contesto, anni: list[int], cumulato: bool = False,
                    scala: float = 1.0, **kw) -> pd.DataFrame:
    """Serie mensile A (e B) in forma lunga per i grafici di confronto."""
    parti = []
    for nome, d in ((ctx.nome_a, ctx.a), (ctx.nome_b, ctx.b)):
        if d is None:
            continue
        s = bc.serie_mensile(d, anni, **kw)
        if s.empty:
            continue
        s["valore"] = s["valore"] / scala
        if cumulato:
            s["valore"] = s.groupby("anno")["valore"].cumsum()
        s["serie"] = nome
        parti.append(s)
    return pd.concat(parti, ignore_index=True) if parti else pd.DataFrame()


def grafico_linee(df: pd.DataFrame, ctx: Contesto, titolo_y: str, dec: int = 0,
                  altezza: int = 260) -> alt.Chart:
    """Linee mensili A (blu pieno) vs B (teal tratteggiato)."""
    dominio = [ctx.nome_a] + ([ctx.nome_b] if ctx.b is not None else [])
    colori = [branding.C_BP, branding.C_CONFRONTO][:len(dominio)]
    df = df.copy()
    df["valore_txt"] = df["valore"].map(lambda v: fmt.numero(v, dec))
    ordine = df.drop_duplicates("etichetta").sort_values("ordine")["etichetta"].tolist()
    base = alt.Chart(df).encode(
        x=alt.X("etichetta:N", sort=ordine, title=None,
                axis=alt.Axis(labelAngle=-45, labelOverlap=True)),
        y=alt.Y("valore:Q", title=titolo_y),
        color=alt.Color("serie:N", scale=alt.Scale(domain=dominio, range=colori), legend=None),
        strokeDash=alt.StrokeDash("serie:N", scale=alt.Scale(domain=dominio,
                                  range=[[1, 0], [6, 4]][:len(dominio)]), legend=None),
        tooltip=[alt.Tooltip("serie:N", title="Versione"),
                 alt.Tooltip("etichetta:N", title="Mese"),
                 alt.Tooltip("valore_txt:N", title=titolo_y)],
    )
    linee = base.mark_line(strokeWidth=2.4)
    punti = base.mark_point(size=70, opacity=0, filled=True)   # bersaglio del tooltip
    return (linee + punti).properties(height=altezza)
