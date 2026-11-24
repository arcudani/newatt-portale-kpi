"""
V3 — Commerciale Agenti (L30 · Direttore Commerciale). Blueprint §5.

Tessere raggruppate per ambito (fasce stile DeD: acquisizione e portafoglio);
subito sotto la scomposizione statica del canale — portafoglio a fine periodo
e produzione del periodo per segmento e commodity — a barre orizzontali con
quota sul totale. I grafici restano alle serie temporali (flussi mensili, PdP
attivi, provvigioni) con i filtri locali di segmento e commodity; chiude la
tabella degli sportelli con l'export.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import bp_calcoli as bc
import bp_import as bi
import branding
import formato as fmt
import ui

ctx = ui.carica_contesto()
ui.testata("V3", "Il canale agenti produce e trattiene i clienti previsti? Quanto costa acquisirli?", ctx)
ui.richiedi_versione(ctx)
p = ctx.periodo

ui.ambiti(ctx, "V3", layout="fasce")

# =============================================================================
# Composizione del canale: quote sul totale (barre orizzontali, non grafici)
# =============================================================================

DIMENSIONI = (("Per segmento", branding.C_SEGMENTO, "segmento"),
              ("Per commodity", branding.C_COMMODITY, "commodity"))


def _tinta(colore: str, quanto: float) -> str:
    """Schiarisce un colore verso il bianco (0 = invariato, 1 = bianco)."""
    canali = (int(colore[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(int(c + (255 - c) * quanto) for c in canali))


# Segmento × commodity del grafico ad area: la tinta è quella del segmento
# nelle barre qui sotto (branding.C_SEGMENTO), il Gas è la versione chiara.
# Così sulla pagina un colore vuole dire sempre la stessa cosa.
COLORI_GRUPPO = {(seg, com): (colore if com == "Power" else _tinta(colore, 0.45))
                 for seg, colore in branding.C_SEGMENTO.items()
                 for com in branding.C_COMMODITY}


def _riga_quota(nome: str, colore: str, valore: float, valore_b, totale: float) -> dict:
    """Una riga di ui.barre: valore, quota sul totale e, se c'è uno scenario
    di confronto, lo scostamento con il suo semaforo."""
    quota = valore / totale if totale > 1e-9 else 0.0
    riga = {"nome": nome, "quota": quota, "colore": colore,
            "valore": f"{fmt.numero(valore)} · {fmt.pct(quota, 0)}"}
    if valore_b is not None:
        c = bc.confronta(valore, valore_b, "N.", 1, None, None)
        if c.relativo is not None:
            riga["delta"] = f"{fmt.pct_segno(c.relativo)} vs {ctx.nome_b}"
            riga["tono"] = branding.STATO_TONO[c.stato]
    return riga


def _composizione(misura, totale: float) -> None:
    """Due blocchi di barre (segmento e commodity) sulla stessa misura."""
    for etichetta, mappa, dimensione in DIMENSIONI:
        st.markdown(f"<div class='mg-side-label'>{etichetta}</div>", unsafe_allow_html=True)
        ui.barre([
            _riga_quota(nome, colore, misura(ctx.a, **{dimensione: nome}),
                        misura(ctx.b, **{dimensione: nome}) if ctx.b is not None else None,
                        totale)
            for nome, colore in mappa.items()])


def _pdp_fine(d, **dims) -> float:
    return d.stock("pdp_attivi", p.anno, p.mese_a, canale="Agenti", **dims)


def _prodotti(d, **dims) -> float:
    return d.flusso("produzione", p, canale="Agenti", **dims)


etichetta_periodo = fmt.periodo_label(p.anno, p.mese_da, p.mese_a)
q1, q2 = st.columns(2)
with q1, ui.pannello("🧭 Portafoglio a fine periodo", "v3_mix_pdp"):
    tot_pdp = _pdp_fine(ctx.a)
    st.caption(f"{etichetta_periodo} · {fmt.numero(tot_pdp)} PdP attivi · {ctx.nome_a}")
    if tot_pdp <= 1e-9:
        st.caption("A fine periodo il BP non prevede PdP attivi sul canale agenti.")
    else:
        _composizione(_pdp_fine, tot_pdp)

with q2, ui.pannello("🚚 Produzione del periodo", "v3_mix_prod"):
    tot_prod = _prodotti(ctx.a)
    st.caption(f"{etichetta_periodo} · {fmt.numero(tot_prod)} contratti prodotti · {ctx.nome_a}")
    if tot_prod <= 1e-9:
        st.caption("Nel periodo selezionato il BP non prevede produzione sul canale agenti.")
    else:
        _composizione(_prodotti, tot_prod)

st.caption("Le quote sono calcolate sul totale del canale agenti — lo stesso perimetro delle "
           "tessere qui sopra — e non risentono dei filtri locali qui sotto.")

# =============================================================================
# Filtri locali e serie temporali
# =============================================================================

f1, f2, f3 = st.columns([1.2, 1.2, 2])
seg = f1.segmented_control("Segmento", ["Tutti", "Retail", "Business"], default="Tutti",
                           key="v3_seg") or "Tutti"
com = f2.segmented_control("Commodity", ["Tutte", "Power", "Gas"], default="Tutte",
                           key="v3_com") or "Tutte"
f3.caption("Segmento e commodity filtrano grafici e tabella; tessere e composizione restano "
           "sul totale del canale agenti.")
dims: dict = {"canale": "Agenti"}
if seg != "Tutti":
    dims["segmento"] = seg
if com != "Tutte":
    dims["commodity"] = com

dominio = [ctx.nome_a] + ([ctx.nome_b] if ctx.b is not None else [])
scala_serie = alt.Scale(domain=dominio, range=[branding.C_BP, branding.C_CONFRONTO][:len(dominio)])
scala_tratto = alt.Scale(domain=dominio, range=[[1, 0], [6, 4]][:len(dominio)])
mesi = [m for m in range(1, 13) if (p.anno, m) >= bi.INIZIO_PIANO]
etichette = [fmt.mese_label(p.anno, m) for m in mesi]
x_mesi = alt.X("etichetta:N", sort=etichette, title=None, axis=alt.Axis(labelAngle=-45))

c1, c2 = st.columns(2)
with c1, ui.pannello(f"🔁 Produzione, cessazioni e net adds · {p.anno}", "v3_flussi"):
    prod = ctx.a.mensile("produzione", p.anno, **dims)
    so = ctx.a.mensile("switch_out", p.anno, **dims)
    barre = pd.DataFrame([
        {"etichetta": fmt.mese_label(p.anno, m), "misura": mis, "valore": val,
         "testo": fmt.numero(abs(val))}
        for m in mesi for mis, val in (("Produzione", prod[m - 1]), ("Cessazioni", -so[m - 1]))])
    linee = []
    for nome, d in ((ctx.nome_a, ctx.a), (ctx.nome_b, ctx.b)):
        if d is None:
            continue
        pr, sw = d.mensile("produzione", p.anno, **dims), d.mensile("switch_out", p.anno, **dims)
        linee += [{"etichetta": fmt.mese_label(p.anno, m), "serie": nome,
                   "valore": pr[m - 1] - sw[m - 1], "testo": fmt.numero(pr[m - 1] - sw[m - 1])}
                  for m in mesi]
    linee = pd.DataFrame(linee)
    g_barre = alt.Chart(barre).mark_bar(size=16).encode(
        x=x_mesi, y=alt.Y("valore:Q", title="contratti"),
        color=alt.Color("misura:N", scale=alt.Scale(domain=["Produzione", "Cessazioni"],
                                                    range=["#009E73", "#E69F00"]), legend=None),
        tooltip=[alt.Tooltip("etichetta:N", title="Mese"), alt.Tooltip("misura:N", title="Misura"),
                 alt.Tooltip("testo:N", title="Contratti")])
    g_linee = alt.Chart(linee).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=30)).encode(
        x=x_mesi, y="valore:Q",
        color=alt.Color("serie:N", scale=scala_serie, legend=None),
        strokeDash=alt.StrokeDash("serie:N", scale=scala_tratto, legend=None),
        tooltip=[alt.Tooltip("serie:N", title="Net adds"), alt.Tooltip("etichetta:N", title="Mese"),
                 alt.Tooltip("testo:N", title="Contratti")])
    voci_leg = [("box", "#009E73", "Produzione"), ("box", "#E69F00", "Cessazioni"),
                ("solid", branding.C_BP, f"Net adds · {ctx.nome_a}")]
    if ctx.b is not None:
        voci_leg.append(("dash", branding.C_CONFRONTO, f"Net adds · {ctx.nome_b}"))
    st.markdown(branding.legenda(voci_leg), unsafe_allow_html=True)
    branding.altair_it((g_barre + g_linee).properties(height=290))

with c2, ui.pannello("👥 PdP attivi per segmento e commodity", "v3_pdp"):
    gruppi = [g for g in COLORI_GRUPPO if seg in ("Tutti", g[0]) and com in ("Tutte", g[1])]
    nomi_g = [f"{s} · {c}" for s, c in gruppi]
    parti = []
    for i, (s, c) in enumerate(gruppi):
        df = bc.serie_mensile(ctx.a, ctx.a.anni, driver="pdp_attivi", canale="Agenti",
                              segmento=s, commodity=c)
        df["gruppo"], df["ordine_g"] = f"{s} · {c}", i
        parti.append(df)
    df = pd.concat(parti, ignore_index=True)
    df["testo"] = df["valore"].map(fmt.numero)
    asse = df.drop_duplicates("etichetta").sort_values("ordine")["etichetta"].tolist()
    x_tutti = alt.X("etichetta:N", sort=asse, title=None,
                    axis=alt.Axis(values=[e for e in asse if e.startswith(("gen", "lug"))],
                                  labelAngle=0))
    grafico = alt.Chart(df).mark_area(opacity=0.9).encode(
        x=x_tutti, y=alt.Y("valore:Q", stack=True, title="PdP attivi"),
        color=alt.Color("gruppo:N", scale=alt.Scale(
            domain=nomi_g, range=[COLORI_GRUPPO[g] for g in gruppi]), legend=None),
        order=alt.Order("ordine_g:Q"),
        tooltip=[alt.Tooltip("gruppo:N", title="Gruppo"), alt.Tooltip("etichetta:N", title="Mese"),
                 alt.Tooltip("testo:N", title="PdP")])
    voci_leg = [("box", COLORI_GRUPPO[g], n) for g, n in zip(gruppi, nomi_g)]
    if ctx.b is not None:
        tot_b = None
        for s, c in gruppi:
            sb = bc.serie_mensile(ctx.b, ctx.a.anni, driver="pdp_attivi", canale="Agenti",
                                  segmento=s, commodity=c)
            tot_b = sb if tot_b is None else tot_b.assign(valore=tot_b["valore"] + sb["valore"])
        tot_b["testo"] = tot_b["valore"].map(fmt.numero)
        grafico = grafico + alt.Chart(tot_b).mark_line(
            color=branding.C_CONFRONTO, strokeDash=[6, 4], strokeWidth=2).encode(
            x=x_tutti, y="valore:Q",
            tooltip=[alt.Tooltip("etichetta:N", title="Mese"),
                     alt.Tooltip("testo:N", title=f"PdP · {ctx.nome_b}")])
        voci_leg.append(("dash", branding.C_CONFRONTO, f"Totale · {ctx.nome_b}"))
    st.markdown(branding.legenda(voci_leg), unsafe_allow_html=True)
    branding.altair_it(grafico.properties(height=290))

with ui.pannello(f"💼 Provvigioni agenti: una tantum e ricorrenti · {p.anno}", "v3_provv"):
    ut = ctx.a.mensile("provvigioni_una_tantum", p.anno, **dims)
    ric = ctx.a.mensile("provvigioni_ricorrenti", p.anno, **dims)
    tipi = ["Una tantum (gettoni)", "Ricorrenti / rinnovi"]
    dfp = pd.DataFrame([
        {"etichetta": fmt.mese_label(p.anno, m), "tipo": t, "valore": -v / 1e3,
         "testo": fmt.numero(-v / 1e3, 1)}
        for m in mesi for t, v in zip(tipi, (ut[m - 1], ric[m - 1]))])
    st.markdown(branding.legenda([("box", "#0072B2", tipi[0]), ("box", "#CC79A7", tipi[1])]),
                unsafe_allow_html=True)
    branding.altair_it(alt.Chart(dfp).mark_bar(size=22).encode(
        x=x_mesi, y=alt.Y("valore:Q", stack=True, title="k€ di costo"),
        color=alt.Color("tipo:N", scale=alt.Scale(domain=tipi, range=["#0072B2", "#CC79A7"]),
                        legend=None),
        tooltip=[alt.Tooltip("etichetta:N", title="Mese"), alt.Tooltip("tipo:N", title="Tipo"),
                 alt.Tooltip("testo:N", title="k€")]).properties(height=250))
    incid = bc.calcola("V2_PROVV_PM", ctx.a, p)
    st.caption(f"Incidenza delle provvigioni totali (con ENASARCO) sul PM lordo nel periodo: "
               f"**{fmt.pct(incid.valore) if incid and incid.valore is not None else 'n.d.'}**. "
               "Sopra lo zero = costo; sotto lo zero = ricavo.")
    positivi = [fmt.mese_label(p.anno, m) for m in mesi if ric[m - 1] > 0.5]
    if positivi:
        ui.nota(f"<b>Rinnovi positivi in {len(positivi)} mesi</b> ({', '.join(positivi)}): la "
                "formula del ricorrente restituisce un ricavo quando il churn supera la "
                "produzione. È un rilievo aperto sull'Excel (requisiti §5): va chiuso o "
                "modellato come parametro prima del motore.")

with ui.pannello(f"🏪 Sportelli, produzione e volumi · {p.anno}", "v3_sportelli"):
    senza_com = {k: v for k, v in dims.items() if k != "commodity"}
    sportelli = ctx.a.mensile("aperture_sportelli", p.anno, canale="Agenti")
    pdp = ctx.a.mensile("pdp_attivi", p.anno, **dims)
    mwh_p = (ctx.a.mensile("mwh", p.anno, **senza_com, commodity="Power")
             if com in ("Tutte", "Power") else [0.0] * 12)
    mwh_g = (ctx.a.mensile("mwh", p.anno, **senza_com, commodity="Gas")
             if com in ("Tutte", "Gas") else [0.0] * 12)
    righe = []
    for m in mesi:
        sp = sportelli[m - 1]
        righe.append({"Mese": fmt.mese_label(p.anno, m), "Sportelli attivi": sp,
                      "Produzione": prod[m - 1],
                      "Produzione per sportello": (prod[m - 1] / sp) if sp > 0 else None,
                      "Cessazioni": so[m - 1], "Net adds": prod[m - 1] - so[m - 1],
                      "PdP a fine mese": pdp[m - 1], "MWh Power": mwh_p[m - 1],
                      "MWh Gas": mwh_g[m - 1]})
    tab = pd.DataFrame(righe)
    show = tab.copy()
    for c in show.columns[1:]:
        show[c] = show[c].map(fmt.numero)
    st.dataframe(show, hide_index=True, width="stretch", height=min(40 + 35 * len(show), 480))
    st.caption("«Sportelli attivi» è il parametro del BP (1 = sportello operativo nel mese). "
               "La performance per agente arriva con i dati operativi (V7, segnaposto SAL-14).")
    ui.scarica(tab, f"commerciale_agenti_{p.anno}")
