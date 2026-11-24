"""
V4 — VAS (L30 · Responsabile VAS). Blueprint §5.

Punti con VAS, penetrazione sul portafoglio, extra-profitto per prodotto e
commodity. Le tessere sono raggruppate per ambito (fasce stile DeD), la
scomposizione dell'extra-profitto del periodo è a barre orizzontali con quota
sul totale; il grafico resta alla serie temporale dei punti con VAS.
Se la versione modella il VAS come canale autonomo (BP v5) lo dice in testa
alla vista: è il rilievo della Nota ricostruzione VAS (10/09/2026).
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
ui.testata("V4", "Quanti clienti hanno un VAS e quanto margine aggiungono?", ctx)
ui.richiedi_versione(ctx)
p = ctx.periodo
anni_operativi = [a for a in ctx.a.anni if ctx.a.voce("ricavi", bc.Periodo(a)) > 0]

if any(ctx.a.flusso("produzione", bc.Periodo(a), canale="VAS") > 0 for a in ctx.a.anni):
    pen = {a: bc.calcola("V4_PENETRAZIONE", ctx.a, bc.Periodo(a)) for a in anni_operativi}
    serie_pen = " · ".join(f"{a}: {fmt.pct(m.valore)}" for a, m in pen.items() if m and m.valore)
    # la serie anno per anno si aggiunge solo se c'è: mai una parentesi vuota
    dettaglio = (f"La penetrazione implicita varia di anno in anno ({serie_pen}) invece "
                 "del 45% del BP 26-27. ") if serie_pen else ""
    ui.nota("<b>In questa versione il VAS è un canale di vendita autonomo</b> (produzione, "
            "switch-out e PdP propri), non un cross-sell sui clienti energia: se cambia il "
            f"piano agenti il VAS non si muove. {dettaglio}La <i>Nota ricostruzione VAS</i> "
            "propone di legarlo al portafoglio agenti (v6).")

ui.ambiti(ctx, "V4", layout="fasce")

prodotti = bi.PRODOTTI_VAS
colori_p = [branding.C_PRODOTTO[x] for x in prodotti]
COMMODITY = [("Power", "Power · su POD"), ("Gas", "Gas · su PDR")]


def _scala(totale: float) -> tuple[float, str, int]:
    """Unità unica per tutta la scomposizione, scelta sul totale del periodo:
    confrontare '10,2 k€' con '7,6 k€' è immediato, '10 k€' con '7.618 €' no
    (è quello che farebbe eur_compatto riga per riga)."""
    if totale >= 1e6:
        return 1e6, "M€", 2
    if totale >= 1e4:
        return 1e3, "k€", 1
    return 1.0, "€", 0


def _riga_margine(nome: str, colore: str, totale: float, **dims) -> dict:
    """Una riga di ui.barre: valore del periodo, quota sul totale e, se c'è
    uno scenario di confronto, lo scostamento con il suo semaforo."""
    valore = ctx.a.flusso("margine_vas", p, **dims)
    quota = valore / totale if totale > 1e-9 else 0.0
    k, unita, dec = _scala(totale)
    riga = {"nome": nome, "quota": quota, "colore": colore,
            "valore": f"{fmt.numero(valore / k, dec)} {unita} · {fmt.pct(quota, 0)}"}
    if ctx.b is not None:
        c = bc.confronta(valore, ctx.b.flusso("margine_vas", p, **dims), "€", 1, None, None)
        if c.relativo is not None:
            riga["delta"] = f"{fmt.pct_segno(c.relativo)} vs {ctx.nome_b}"
            riga["tono"] = branding.STATO_TONO[c.stato]
    return riga


c1, c2 = st.columns([1.15, 1])
with c1, ui.pannello("🧩 Punti con VAS per prodotto", "v4_stock"):
    parti = []
    for i, prod in enumerate(prodotti):
        df = bc.serie_mensile(ctx.a, ctx.a.anni, driver="vas_attivi", prodotto_vas=prod)
        if df.empty:          # versione senza mesi di piano: niente colonne da mappare
            continue
        df["prodotto"], df["ordine_p"] = prod, i
        parti.append(df)
    if not parti:
        st.caption("La versione non ha una serie mensile dei punti con VAS.")
    else:
        df = pd.concat(parti, ignore_index=True)
        df["testo"] = df["valore"].map(fmt.numero)
        asse = df.drop_duplicates("etichetta").sort_values("ordine")["etichetta"].tolist()
        x_tutti = alt.X("etichetta:N", sort=asse, title=None,
                        axis=alt.Axis(values=[e for e in asse if e.startswith(("gen", "lug"))],
                                      labelAngle=0))
        grafico = alt.Chart(df).mark_area(opacity=0.9).encode(
            x=x_tutti, y=alt.Y("valore:Q", stack=True, title="punti con VAS"),
            color=alt.Color("prodotto:N", scale=alt.Scale(domain=prodotti, range=colori_p),
                            legend=None),
            order=alt.Order("ordine_p:Q"),
            tooltip=[alt.Tooltip("prodotto:N", title="Prodotto"),
                     alt.Tooltip("etichetta:N", title="Mese"),
                     alt.Tooltip("testo:N", title=f"Punti · {ctx.nome_a}")])
        voci_leg = [("box", c, n) for n, c in zip(prodotti, colori_p)]
        tb = bc.serie_mensile(ctx.b, ctx.a.anni, driver="vas_attivi") if ctx.b is not None \
            else pd.DataFrame()
        if not tb.empty:
            tb["testo"] = tb["valore"].map(fmt.numero)
            grafico = grafico + alt.Chart(tb).mark_line(
                color=branding.C_CONFRONTO, strokeDash=[6, 4], strokeWidth=2).encode(
                x=x_tutti, y="valore:Q",
                tooltip=[alt.Tooltip("etichetta:N", title="Mese"),
                         alt.Tooltip("testo:N", title=f"Totale · {ctx.nome_b}")])
            voci_leg.append(("dash", branding.C_CONFRONTO, f"Totale · {ctx.nome_b}"))
        st.markdown(branding.legenda(voci_leg), unsafe_allow_html=True)
        branding.altair_it(grafico.properties(height=290))
        st.caption(f"Punti con VAS a fine mese, impilati per prodotto · {ctx.nome_a}. "
                   "Il grafico copre tutti gli anni di piano, non solo il periodo filtrato.")

with c2, ui.pannello("💶 Extra-profitto del periodo", "v4_margine"):
    totale = ctx.a.flusso("margine_vas", p)
    quando = fmt.periodo_label(p.anno, p.mese_da, p.mese_a)
    if totale <= 1e-9:
        # niente "totale 0 €": lo zero qui è un'assenza di piano, non un calcolo
        st.caption(f"{quando} · il BP non prevede margine VAS in questo periodo "
                   f"({ctx.nome_a}): la scomposizione compare dal primo anno con VAS a piano.")
    else:
        k_s, u_s, d_s = _scala(totale)
        st.caption(f"{quando} · totale {fmt.numero(totale / k_s, d_s)} {u_s} · {ctx.nome_a}")
        st.markdown("<div class='mg-side-label'>Per prodotto</div>", unsafe_allow_html=True)
        ui.barre([_riga_margine(prod, branding.C_PRODOTTO[prod], totale, prodotto_vas=prod)
                  for prod in prodotti])
        st.markdown("<div class='mg-side-label'>Per commodity</div>", unsafe_allow_html=True)
        ui.barre([_riga_margine(etichetta, branding.C_COMMODITY[comm], totale, commodity=comm)
                  for comm, etichetta in COMMODITY])
        st.caption("Le quote sono calcolate sul totale del periodo; il margine è quello "
                   "fisso per punto previsto dal BP, non ancora consuntivato.")

with ui.pannello(f"📋 Sviluppo VAS per mese · {p.anno}", "v4_tabella"):
    mesi = [m for m in range(1, 13) if (p.anno, m) >= bi.INIZIO_PIANO]
    att = ctx.a.mensile("produzione", p.anno, canale="VAS")
    ces = ctx.a.mensile("switch_out", p.anno, canale="VAS")
    stock = ctx.a.mensile("vas_attivi", p.anno)
    marg = ctx.a.mensile("margine_vas", p.anno)
    pdp = ctx.a.mensile("pdp_attivi", p.anno, canale="Agenti")
    tab = pd.DataFrame([{
        "Mese": fmt.mese_label(p.anno, m), "Attivazioni": att[m - 1], "Cessazioni": ces[m - 1],
        "Punti con VAS": stock[m - 1],
        "Penetrazione su PdP": (stock[m - 1] / pdp[m - 1]) if pdp[m - 1] > 0 else None,
        "Margine VAS (€)": marg[m - 1],
        "Margine per punto (€/mese)": (marg[m - 1] / stock[m - 1]) if stock[m - 1] > 0 else None,
    } for m in mesi])
    show = tab.copy()
    for c in ("Attivazioni", "Cessazioni", "Punti con VAS", "Margine VAS (€)"):
        show[c] = show[c].map(fmt.numero)
    show["Penetrazione su PdP"] = show["Penetrazione su PdP"].map(fmt.pct)
    show["Margine per punto (€/mese)"] = show["Margine per punto (€/mese)"].map(
        lambda v: fmt.numero(v, 2))
    st.dataframe(show, hide_index=True, width="stretch", height=min(40 + 35 * len(show), 480))
    st.caption("I costi del canale VAS sono a zero nel BP (tessera segnaposto): il margine "
               "fisso è già netto del fornitore del servizio ma non di eventuali provvigioni.")
    ui.scarica(tab, f"vas_{p.anno}")
