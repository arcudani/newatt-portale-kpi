"""
V5 — Operations & Servizio (L30 · COO). Blueprint §5.

Cost-to-Serve e sua scomposizione, FTE da driver vs pianificati, perdite su
crediti; quattro segnaposto DeD per la qualità del servizio (fase 4).

Gerarchia visiva DeD: prima la fascia delle tessere attive (il numero domina),
poi il Cost-to-Serve — serie per anno a sinistra e scomposizione a barre
dell'anno selezionato a destra — la serie mensile degli FTE a tutta larghezza,
la tabella dei costi operativi e, in fondo come nella V9, i segnaposto DeD.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import bp_calcoli as bc
import branding
import formato as fmt
import ui

ctx = ui.carica_contesto()
ui.testata("V5", "Quanto costa servire un cliente? La struttura regge i volumi del piano?", ctx)
ui.richiedi_versione(ctx)
p = ctx.periodo

ui.ambiti(ctx, "V5", layout="fasce", stato="attivo")

FAMIGLIE = ["Personale", "IT", "Contratto NeWatt", "Servizi generali", "Oneri bancari",
            "Marketing", "Beni di terzi"]
COLORI_F = branding.CATEGORICHE[:len(FAMIGLIE)]
COLORE_RUOLO = {"Customer Care": branding.CATEGORICHE[0],
                "Operation": branding.CATEGORICHE[1]}

# --- Costi operativi per famiglia: base comune al grafico e alla scomposizione ---
anni = [a for a in ctx.a.anni if not bc.Periodo(a).avviamento]
parti = []
for nome, d in ((ctx.nome_a, ctx.a), (ctx.nome_b, ctx.b)):
    if d is None:
        continue
    f = bc.cts_per_famiglia(d, anni)
    f["serie"] = nome
    parti.append(f)
f = pd.concat(parti, ignore_index=True)
if not ctx.bros:   # perimetro viewer: il contratto intragruppo confluisce nei servizi
    f["famiglia"] = f["famiglia"].replace({"Contratto NeWatt": "Servizi generali"})
    f = f.groupby(["anno", "famiglia", "serie"], as_index=False)[["euro", "per_pdp"]].sum()
presenti = [x for x in FAMIGLIE if f[f["famiglia"] == x]["euro"].abs().sum() > 0]
f = f[f["famiglia"].isin(presenti)].copy()
colori = [COLORI_F[FAMIGLIE.index(x)] for x in presenti]
colore_di = dict(zip(presenti, colori))

c1, c2 = st.columns([1.25, 1])
with c1, ui.pannello("🧮 Cost-to-Serve per famiglia di costo", "v5_cts"):
    g = f.copy()
    g["anno"] = g["anno"].astype(str)
    g["ordine_f"] = g["famiglia"].map(presenti.index)
    g["testo"] = g["per_pdp"].map(lambda v: fmt.numero(v, 1))
    enc = dict(
        x=alt.X("anno:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("per_pdp:Q", stack=True, title="€ per PdP medio"),
        color=alt.Color("famiglia:N", scale=alt.Scale(domain=presenti, range=colori), legend=None),
        order=alt.Order("ordine_f:Q"),
        tooltip=[alt.Tooltip("serie:N", title="Versione"), alt.Tooltip("anno:N", title="Anno"),
                 alt.Tooltip("famiglia:N", title="Famiglia"), alt.Tooltip("testo:N", title="€/PdP")])
    dominio = [ctx.nome_a] + ([ctx.nome_b] if ctx.b is not None else [])
    if ctx.b is not None:
        enc["xOffset"] = alt.XOffset("serie:N", scale=alt.Scale(domain=dominio))
        enc["opacity"] = alt.Opacity("serie:N", scale=alt.Scale(domain=dominio, range=[1.0, 0.55]),
                                     legend=None)
    st.markdown(branding.legenda([("box", c, n) for n, c in zip(presenti, colori)]),
                unsafe_allow_html=True)
    branding.altair_it(alt.Chart(g).mark_bar(size=18 if ctx.b is not None else 34).encode(**enc)
                       .properties(height=290))
    didascalia = "Costi operativi su PdP attivi medi dell'anno (2026 escluso: avviamento)."
    if ctx.b is not None:
        didascalia += f" Barre piene = {ctx.nome_a}, chiare = {ctx.nome_b}."
    st.caption(didascalia)

with c2, ui.pannello(f"🧩 Peso per famiglia · {p.anno}", "v5_cts_anno"):
    def _per_pdp(serie: str) -> dict[str, float]:
        """€ per PdP medio dell'anno selezionato, per famiglia, di una versione."""
        r = f[(f["anno"] == p.anno) & (f["serie"] == serie)]
        return {x["famiglia"]: float(x["per_pdp"]) for _, x in r.iterrows()
                if not fmt.manca(x["per_pdp"])}

    val_a = _per_pdp(ctx.nome_a)
    val_b = _per_pdp(ctx.nome_b) if ctx.b is not None else {}
    totale = sum(val_a.values())
    if totale <= 1e-9:
        st.caption(f"Nel {p.anno} il BP non prevede PdP attivi medi (avviamento): il costo "
                   "per punto non è calcolabile. Seleziona un anno operativo.")
    else:
        st.caption(f"Anno {p.anno} · totale {fmt.numero(totale, 1)} € per PdP medio · "
                   f"{ctx.nome_a}")
        righe = []
        for nome_f, v in sorted(val_a.items(), key=lambda x: -x[1]):
            quota = v / totale
            riga = {"nome": nome_f, "quota": quota, "colore": colore_di[nome_f],
                    "valore": f"{fmt.numero(v, 1)} € · {fmt.pct(quota, 0)}"}
            if nome_f in val_b:
                c = bc.confronta(v, val_b[nome_f], "€", -1, None, None)
                if c.relativo is not None:
                    riga["delta"] = f"{fmt.pct_segno(c.relativo)} vs {ctx.nome_b}"
                    riga["tono"] = branding.STATO_TONO[c.stato]
            righe.append(riga)
        ui.barre(righe)
        st.caption("Quote sul totale dei costi operativi per punto dell'anno selezionato, "
                   "dalla famiglia più pesante alla più leggera.")

with ui.pannello("👥 FTE da driver vs FTE pianificati", "v5_fte"):
    parti = []
    for ruolo in COLORE_RUOLO:
        s = bc.serie_mensile(ctx.a, ctx.a.anni, driver="fte_necessari", ruolo=ruolo)
        s["ruolo"] = f"Necessari · {ruolo}"
        parti.append(s)
    fte = pd.concat(parti, ignore_index=True)
    fte["testo"] = fte["valore"].map(lambda v: fmt.numero(v, 1))
    piano = bc.serie_mensile(ctx.a, ctx.a.anni, driver="fte_pianificati")
    piano["testo"] = piano["valore"].map(lambda v: fmt.numero(v, 1))
    asse = piano.sort_values("ordine")["etichetta"].tolist()
    x_tutti = alt.X("etichetta:N", sort=asse, title=None,
                    axis=alt.Axis(values=[e for e in asse if e.startswith(("gen", "lug"))],
                                  labelAngle=0))
    ruoli_nec = [f"Necessari · {r}" for r in COLORE_RUOLO]
    colonne_nec = list(COLORE_RUOLO.values())
    grafico_barre = alt.Chart(fte).mark_bar().encode(
        x=x_tutti, y=alt.Y("valore:Q", stack=True, title="FTE"),
        color=alt.Color("ruolo:N", scale=alt.Scale(domain=ruoli_nec, range=colonne_nec),
                        legend=None),
        tooltip=[alt.Tooltip("ruolo:N", title="FTE"), alt.Tooltip("etichetta:N", title="Mese"),
                 alt.Tooltip("testo:N", title="FTE")])
    linea = alt.Chart(piano).mark_line(color=branding.C_BP, strokeWidth=2).encode(
        x=x_tutti, y="valore:Q",
        tooltip=[alt.Tooltip("etichetta:N", title="Mese"), alt.Tooltip("testo:N", title="Pianificati")])
    st.markdown(branding.legenda(
        [("box", c, n) for n, c in zip(ruoli_nec, colonne_nec)]
        + [("solid", branding.C_BP, "Pianificati (foglio Personale)")]), unsafe_allow_html=True)
    branding.altair_it((grafico_barre + linea).properties(height=250))
    st.caption("Gli FTE da driver non sono ancora collegati al conto economico: il costo "
               "del personale nel CE segue l'organico pianificato. Dettaglio in V9.")

with ui.pannello(f"🧾 Costi operativi per voce · {fmt.periodo_label(p.anno, p.mese_da, p.mese_a)}",
                 "v5_costi"):
    t = bc.ce_sintetico(ctx.a, ctx.b, p, 2)
    padri = set(bc.VOCI_CTS)
    t = t[(t["codice"].isin(padri)) | (t["codice"].map(
        lambda c: (bc.bi.VOCI_PER_CODICE[c].padre in padri)))]
    t = t[~t["codice"].isin(ui.voci_riservate(ctx))].reset_index(drop=True)
    if ctx.b is None:
        show = pd.DataFrame({"Voce": t["voce"], "Periodo": t["periodo"].map(fmt.eur),
                             f"Anno {p.anno}": t["anno"].map(fmt.eur),
                             "% sui ricavi": t["su_ricavi"].map(lambda v: fmt.pct(v, 2))})
    else:
        show = pd.DataFrame({"Voce": t["voce"], ctx.nome_a: t["periodo"].map(fmt.eur),
                             ctx.nome_b: t["confronto_periodo"].map(fmt.eur),
                             "Δ €": [fmt.segno(v, fmt.numero(v)) for v in t["delta"]],
                             "Δ %": t["delta_pct"].map(fmt.pct_segno),
                             "Esito": t["stato"].map(ui.STATO_TESTO)})
    livelli = t["livello"].tolist()
    st.dataframe(show.style.apply(lambda r: ["font-weight: 700" if livelli[r.name] == 1 else ""
                                             for _ in r], axis=1),
                 hide_index=True, width="stretch", height=min(40 + 35 * len(show), 640))
    st.caption("Il dettaglio per conto contabile (foglio IPO - Costi) arriva con il mapping "
               "del consuntivo (fase 3).")
    ui.scarica(t.drop(columns=["ordine"]), f"costi_operativi_{p.anno}")

# La fascia dei segnaposto DeD chiude la vista (blueprint §5: puntualità
# switch-in, fatture on-time, reclami, time-to-activate): la struttura deve
# restare la stessa quando in fase 4 arriveranno i dati operativi.
st.markdown("<div class='mg-side-label'>Qualità del servizio · in attesa dei dati operativi "
            "(fase 4)</div>", unsafe_allow_html=True)
ui.ambiti(ctx, "V5", layout="fasce", stato="segnaposto", per_riga=4)
