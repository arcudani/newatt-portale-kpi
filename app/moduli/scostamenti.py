"""
V6 — Scostamenti voce × mese (L300). Blueprint §5.

Heatmap del CE per voce e mese nei colori di stato del design system: verde
favorevole, ambra attenzione, rosso critico su sfondi tenui come le pillole,
con l'inchiostro forte del tono sul testo della cella. Con una versione di
confronto la cella porta il Δ% ed è preceduta dalla sintesi degli esiti in
barre; senza confronto mostra la mensilizzazione del piano (peso del mese sul
totale annuo della voce) su rampa grigia — il grigio è la versione di
riferimento. Nel dettaglio della voce: peso di ogni mese sull'anno in barre,
andamento mensile e cumulato, tabella esportabile.
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

# Esiti della heatmap: sfondo tenue + inchiostro forte, la stessa coppia delle
# pillole di avviso del design system (verde / ambra / rosso).
ESITI = ["favorevole", "in linea", "attenzione", "critico", "n.d."]
SFONDO_ESITO = {"favorevole": "#E3F1E9", "in linea": "#F4F2F1",
                "attenzione": "#FDF3E2", "critico": "#FADEE3", "n.d.": "#FFFFFF"}
INCHIOSTRO_ESITO = {"favorevole": "#146B47", "in linea": branding.C_BP,
                    "attenzione": "#8A5A00", "critico": branding.C_CATTIVO,
                    "n.d.": "#A8A2A1"}
TONO_ESITO = {"favorevole": "buono", "in linea": "neutro", "attenzione": "attenzione",
              "critico": "cattivo", "n.d.": "neutro"}
# Mensilizzazione: rampa grigia (il grigio è la versione di riferimento).
RAMPA_QUOTA = ["#F7F5F4", branding.C_BP]
QUOTA_CELLA_SCURA = 0.62        # oltre il 62% del massimo il testo passa in bianco

ctx = ui.carica_contesto()
ui.testata("V6", "Quale voce, in quale mese, spiega lo scostamento?", ctx)
ui.richiedi_versione(ctx)
p = ctx.periodo
riservate = ui.voci_riservate(ctx)

ui.ambiti(ctx, "V6", layout="fasce")


def nome_voce(codice: str) -> str:
    """Etichetta univoca: al livello 3 si antepone il padre (es. «Ricavi
    Power › Materia prima» vs «Approvvigionamento Power › Materia prima»)."""
    v = bi.VOCI_PER_CODICE[codice]
    if v.livello == 3 and v.padre:
        return f"{bi.VOCI_PER_CODICE[v.padre].etichetta} › {v.etichetta}"
    return v.etichetta


def esito_di(stato: str, delta_pct) -> str:
    """Semaforo della cella in parole (soglie 5% / 10%, costi già col segno)."""
    if fmt.manca(delta_pct):
        return "n.d."
    if stato == "warn":
        return "attenzione"
    if stato == "crit":
        return "critico"
    return "favorevole" if delta_pct * 100 > 5 else "in linea"


f1, f2 = st.columns([1.4, 3])
livello = f1.segmented_control("Dettaglio voci", [1, 2, 3], default=1, key="v6_livello",
                               format_func=lambda x: f"Livello {x}") or 1
m = bc.matrice_scostamenti(ctx.a, ctx.b, p.anno, livello)
m = m[~m["codice"].isin(riservate)].copy()
if m.empty:
    st.info(f"Nessun valore del conto economico nel {p.anno} per questa versione "
            f"(il 2026 è il periodo di avviamento). Scegli un altro anno in sidebar.")
    st.stop()
m["nome"] = m["codice"].map(nome_voce)
righe_y = m.drop_duplicates("codice").sort_values("ordine")["nome"].tolist()
tooltip = [alt.Tooltip("nome:N", title="Voce"), alt.Tooltip("mese_label:N", title="Mese")]

with ui.pannello(f"🌡️ Voce × mese · {p.anno}", "v6_heatmap"):
    sintesi: list[dict] = []
    risposta = ""
    if ctx.b is None:
        f2.caption("Senza versione di confronto la heatmap mostra la **mensilizzazione** del "
                   "piano: il peso di ogni mese sul totale annuo della voce. Scegli «Confronta "
                   "con» in sidebar per gli scostamenti (con il consuntivo dalla fase 3).")
        m["testo"] = m["a"].map(lambda v: fmt.numero(v / 1e3, 0))
        m["a_txt"] = m["a"].map(fmt.eur)
        m["quota_txt"] = m["quota"].map(fmt.pct)
        q_max = float(pd.to_numeric(m["quota"], errors="coerce").max())
        if fmt.manca(q_max) or q_max <= 0:
            q_max = 1.0
        # testo bianco solo sulle celle davvero scure della rampa (contrasto)
        m["inchiostro"] = ["#FFFFFF" if (not pd.isna(q) and q >= q_max * QUOTA_CELLA_SCURA)
                           else "#111111" for q in m["quota"]]
        colore = alt.Color("quota:Q", legend=None,
                           scale=alt.Scale(range=RAMPA_QUOTA, domainMin=0, clamp=True))
        tooltip += [alt.Tooltip("a_txt:N", title=ctx.nome_a),
                    alt.Tooltip("quota_txt:N", title="Quota dell'anno")]
        legenda_righe = [("box", RAMPA_QUOTA[0], "mese leggero"),
                         ("box", "#A8A2A1", "mese medio"),
                         ("box", RAMPA_QUOTA[1], "mese pesante")]
        legenda_html = "Valori in k€ · colore = quota del mese sul totale annuo della voce"
    else:
        m["esito"] = [esito_di(s, d) for s, d in zip(m["stato"], m["delta_pct"])]
        m["inchiostro"] = m["esito"].map(INCHIOSTRO_ESITO)
        m["testo"] = m["delta_pct"].map(lambda v: fmt.pct_segno(v, 0) if not fmt.manca(v) else "")
        m["a_txt"], m["b_txt"] = m["a"].map(fmt.eur), m["b"].map(fmt.eur)
        m["d_txt"] = [fmt.segno(v, fmt.eur(v)) for v in m["delta"]]
        colore = alt.Color("esito:N", legend=None, scale=alt.Scale(
            domain=ESITI, range=[SFONDO_ESITO[e] for e in ESITI]))
        tooltip += [alt.Tooltip("a_txt:N", title=ctx.nome_a), alt.Tooltip("b_txt:N", title=ctx.nome_b),
                    alt.Tooltip("d_txt:N", title="Δ €"), alt.Tooltip("testo:N", title="Δ %"),
                    alt.Tooltip("esito:N", title="Esito")]
        # stessi colori dell'inchiostro delle celle e delle barre di sintesi:
        # un solo vocabolario di colore per l'esito su tutta la vista
        legenda_righe = [("box", INCHIOSTRO_ESITO[e], t) for e, t in (
            ("favorevole", "favorevole oltre 5%"), ("in linea", "in linea entro ±5%"),
            ("attenzione", "attenzione 5-10%"), ("critico", "critico oltre 10%"))]
        legenda_html = ("Δ % = " + f"{ctx.nome_b} − {ctx.nome_a} · soglie 5% / 10% · i costi "
                        "sono negativi: un costo che scende è favorevole")
        conteggi = m["esito"].value_counts()
        totale_celle = int(conteggi.sum()) or 1
        for e in ESITI:
            n = int(conteggi.get(e, 0))
            if not n:
                continue
            quota = n / totale_celle
            sintesi.append({"nome": e, "quota": quota,
                            "valore": f"{n} {'cella' if n == 1 else 'celle'} · {fmt.pct(quota, 0)}",
                            "colore": INCHIOSTRO_ESITO[e]})
        # la risposta alla domanda della vista, in chiaro: quale voce, in quale
        # mese, pesa di più (cella con il Δ € sfavorevole più grande)
        fuori = m[m["esito"].isin(("attenzione", "critico"))]
        if fuori.empty:
            risposta = (f"<b>Nessuna cella oltre il 5%</b> nel {p.anno}: {ctx.nome_b} segue "
                        f"{ctx.nome_a} in tutte le voci e in tutti i mesi del piano.")
        else:
            r = fuori.loc[fuori["delta"].idxmin()]
            altre = len(fuori) - 1
            coda = ("" if not altre else
                    (" · un'altra cella fuori linea" if altre == 1
                     else f" · altre {altre} celle fuori linea"))
            risposta = (f"<b>Lo scostamento più grande è «{r['nome']}» a "
                        f"{fmt.MESI_LUNGHI[int(r['mese']) - 1]}</b>: "
                        f"{fmt.segno(r['delta'], fmt.eur_compatto(r['delta']))} "
                        f"({fmt.pct_segno(r['delta_pct'], 0)}) di {ctx.nome_b} rispetto a "
                        f"{ctx.nome_a}{coda}.")

    if risposta:
        ui.nota(risposta)
    if sintesi:
        s1, s2 = st.columns([2, 3], gap="medium")
        with s1:
            st.markdown("**Esiti sulle celle**")
            ui.barre(sintesi)
        with s2:
            st.markdown(branding.legenda(legenda_righe), unsafe_allow_html=True)
            st.caption(legenda_html)
    else:
        st.markdown(branding.legenda(legenda_righe), unsafe_allow_html=True)
        st.caption(legenda_html)

    base = alt.Chart(m).encode(
        x=alt.X("mese_label:N", sort=fmt.MESI, title=None,
                axis=alt.Axis(orient="top", labelAngle=0, domain=False, ticks=False)),
        y=alt.Y("nome:N", sort=righe_y, title=None,
                axis=alt.Axis(labelLimit=280, labelOverlap=False, domain=False, ticks=False)))
    celle = base.mark_rect(stroke="#ffffff", strokeWidth=2, cornerRadius=3).encode(
        color=colore, tooltip=tooltip)
    # l'inchiostro è già un colore pronto per cella: scale=None lo usa tale e
    # quale, resolve_scale tiene separate le due scale di colore dei livelli
    testi = base.mark_text(fontSize=11, fontWeight=700).encode(
        text="testo:N", color=alt.Color("inchiostro:N", scale=None), tooltip=tooltip)
    branding.altair_it((celle + testi).resolve_scale(color="independent")
                       .properties(height=max(120, 30 * len(righe_y))))

with ui.pannello("🔎 Dettaglio della voce", "v6_dettaglio"):
    tutte = [v.codice for v in bi.VOCI if v.codice not in riservate]
    richiesta = st.session_state.get("v6_voce", "ebitda")
    voce = st.selectbox("Voce", tutte, index=tutte.index(richiesta) if richiesta in tutte else 0,
                        format_func=nome_voce, key="v6_voce_sel")
    st.session_state["v6_voce"] = voce
    d1, d2 = st.columns(2)
    dominio = [ctx.nome_a] + ([ctx.nome_b] if ctx.b is not None else [])
    mensile = ui.serie_confronto(ctx, [p.anno], scala=1e3, voce=voce)
    with d1:
        st.markdown("**Mensile (k€)**")
        if not mensile.empty:
            mensile["testo"] = mensile["valore"].map(lambda v: fmt.numero(v, 1))
            ordine = mensile.drop_duplicates("etichetta").sort_values("ordine")["etichetta"].tolist()
            enc = dict(x=alt.X("etichetta:N", sort=ordine, title=None, axis=alt.Axis(labelAngle=-45)),
                       y=alt.Y("valore:Q", title="k€"),
                       color=alt.Color("serie:N", legend=None, scale=alt.Scale(
                           domain=dominio, range=[branding.C_BP, branding.C_CONFRONTO][:len(dominio)])),
                       tooltip=[alt.Tooltip("serie:N", title="Versione"),
                                alt.Tooltip("etichetta:N", title="Mese"),
                                alt.Tooltip("testo:N", title="k€")])
            if ctx.b is not None:
                enc["xOffset"] = alt.XOffset("serie:N", scale=alt.Scale(domain=dominio))
            branding.altair_it(alt.Chart(mensile).mark_bar().encode(**enc).properties(height=240))
    with d2:
        st.markdown("**Cumulato (k€)**")
        cum = ui.serie_confronto(ctx, [p.anno], cumulato=True, scala=1e3, voce=voce)
        if not cum.empty:
            branding.altair_it(ui.grafico_linee(cum, ctx, "k€", dec=1, altezza=240))
    ui.legenda_versioni(ctx)


def pesi_mensili(codice: str) -> list[dict]:
    """Peso di ogni mese sul totale dell'anno della voce, in barre: il valore
    è la quota, il nome porta l'importo, il Δ% compare solo quando è fuori
    linea (favorevole, attenzione o critico) così il colore resta leggibile.
    Il totale è in valore assoluto: una voce che cambia segno nell'anno (un
    margine negativo d'avvio) darebbe altrimenti quote sopra il 100%."""
    mens_a = ctx.a.voce_mensile(codice, p.anno)
    mens_b = ctx.b.voce_mensile(codice, p.anno) if ctx.b is not None else None
    attivi = [(mese, v) for mese, v in enumerate(mens_a, start=1)
              if (p.anno, mese) >= bi.INIZIO_PIANO]
    totale = sum(abs(v) for _, v in attivi)
    if totale < 1e-9:
        return []
    righe = []
    for mese, v in attivi:
        quota = abs(v) / totale
        riga = {"nome": f"{fmt.MESI_LUNGHI[mese - 1]} · {fmt.eur_compatto(v)}",
                "valore": fmt.pct(quota, 1), "quota": quota, "colore": branding.C_BP}
        if mens_b is not None:
            c = bc.stato_voce(v, mens_b[mese - 1])
            esito = esito_di(c.stato, c.relativo)
            if esito in ("favorevole", "attenzione", "critico"):
                riga["delta"] = fmt.pct_segno(c.relativo, 0)
                riga["tono"] = TONO_ESITO[esito]
        righe.append(riga)
    return righe


with ui.pannello(f"📅 Peso dei mesi sull'anno · {p.anno}", "v6_pesi"):
    st.caption(f"{nome_voce(voce)} · quota di ogni mese sul totale dell'anno della voce "
               "(importi in valore assoluto)"
               + (f" · Δ% = {ctx.nome_b} − {ctx.nome_a} sui mesi fuori linea"
                  if ctx.b is not None else ""))
    righe_pesi = pesi_mensili(voce)
    if not righe_pesi:
        st.caption("La voce è a zero in tutto l'anno: nessun peso mensile da mostrare.")
    else:
        meta = (len(righe_pesi) + 1) // 2
        b1, b2 = st.columns(2, gap="medium")
        with b1:
            ui.barre(righe_pesi[:meta])
        with b2:
            ui.barre(righe_pesi[meta:])
    st.caption("Note di commento firmate dall'owner e conti contabili che compongono la voce "
               "arrivano con il consuntivo (fase 3).")

with st.expander("📋 Tabella esportabile voce × mese"):
    tab = m[["nome", "mese_label", "a"] + (["b", "delta", "delta_pct", "esito"]
                                           if ctx.b is not None else ["quota"])].copy()
    tab["ytd_a"] = m.groupby("codice")["a"].cumsum()
    if ctx.b is not None:
        tab["ytd_b"] = m.groupby("codice")["b"].cumsum()
    tab["anno_a"] = m["codice"].map(lambda c: ctx.a.voce(c, p.anno_intero()))
    tab["fonte"] = "BP" if ctx.b is None else "BP vs versione"
    tab["stato_caricamento"] = "consuntivo non caricato"
    tab = tab.rename(columns={"nome": "voce", "mese_label": "mese", "a": ctx.nome_a,
                              "b": ctx.nome_b or "b", "anno_a": f"{ctx.nome_a} anno (forecast)"})
    st.dataframe(tab, hide_index=True, width="stretch", height=360)
    ui.scarica(tab, f"scostamenti_{p.anno}")
