"""
V2 — Economico (L30 · CFO / Controller). Blueprint §5.

Sei tessere economiche in due fasce (ricavi e margini, costi), il ponte
ricavi → utile — la firma della vista — con accanto la composizione dei
costi del periodo e l'andamento mensile della voce scelta, e sotto il CE
sintetico (click su una riga → V6 Scostamenti).
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import bp_calcoli as bc
import bp_import as bi
import branding
import formato as fmt
import registro_moduli
import ui

ctx = ui.carica_contesto()
ui.testata("V2", "Quale voce del conto economico si scosta dal piano, e con che tendenza?", ctx)
ui.richiedi_versione(ctx)
p = ctx.periodo
periodo_txt = fmt.periodo_label(p.anno, p.mese_da, p.mese_a)

ui.ambiti(ctx, "V2", layout="fasce")
st.caption("Passa il mouse su una tessera per la definizione del KPI · l'anello e le pillole "
           "segnalano benchmark, tendenze e scostamenti oltre soglia.")

dominio = [ctx.nome_a] + ([ctx.nome_b] if ctx.b is not None else [])
colori = [branding.C_BP, branding.C_CONFRONTO][:len(dominio)]

# Etichette corte per il ponte: il nome esteso resta nel tooltip.
ETICHETTE_PONTE = {
    "Costo materia": "Materia",
    "Provvigioni e point": "Provv. e point",
    "Costi generali": "Costi gen.",
    "Perdite, amm., oneri": "Perdite e amm.",
    "Gestione finanziaria": "Gest. fin.",
    "Risultato netto": "Utile netto",
}

# Blocchi di costo fino all'EBITDA, nello stesso ordine dei passi del ponte.
BLOCCHI_COSTO = [
    ("Approvvigionamento", ("costi_appr",)),
    ("Provvigioni e point", ("provvigioni", "spese_point")),
    ("Costi generali", tuple(bc.VOCI_COSTI_GENERALI)),
    ("Personale", ("personale",)),
]
riservate = ui.voci_riservate(ctx)
blocchi = [(nome, tuple(c for c in voci if c not in riservate))
           for nome, voci in BLOCCHI_COSTO]


def _costi(d: bc.Dati, voci) -> float:
    """Costi in positivo: nel CE hanno segno negativo."""
    return -d.voci(voci, p)


c1, c2 = st.columns([1.35, 1], gap="small")

with c1, ui.pannello("🌉 Dai ricavi all'utile", "v2_ponte"):
    parti = []
    for nome, d in ((ctx.nome_a, ctx.a), (ctx.nome_b, ctx.b)):
        if d is None:
            continue
        w = bc.waterfall(d, p)
        w["serie"] = nome
        parti.append(w)
    w = pd.concat(parti, ignore_index=True)
    for c in ("inizio", "fine", "valore"):
        w[c] = w[c] / 1e6
    w["alto"] = w[["inizio", "fine"]].max(axis=1)
    w["testo"] = w["valore"].map(lambda v: fmt.numero(v, 1))
    w["etichetta"] = w["passo"].map(lambda x: ETICHETTE_PONTE.get(x, x))
    ordine = w.drop_duplicates("passo").sort_values("ordine")["etichetta"].tolist()
    enc = {"x": alt.X("etichetta:N", sort=ordine, title=None,
                      axis=alt.Axis(labelAngle=-35, labelLimit=95, labelOverlap=False))}
    if ctx.b is not None:
        enc["xOffset"] = alt.XOffset("serie:N", scale=alt.Scale(domain=dominio))
    base = alt.Chart(w).encode(**enc)
    barre = base.mark_bar(cornerRadius=2).encode(
        y=alt.Y("inizio:Q", title="M€"), y2="fine:Q",
        color=alt.Color("serie:N", scale=alt.Scale(domain=dominio, range=colori), legend=None),
        opacity=alt.condition(alt.datum.tipo == "totale", alt.value(1.0), alt.value(0.45)),
        tooltip=[alt.Tooltip("passo:N", title="Passo"), alt.Tooltip("serie:N", title="Versione"),
                 alt.Tooltip("testo:N", title="M€")])
    testi = base.mark_text(dy=-7, fontSize=11, fontWeight=700).encode(
        y=alt.Y("alto:Q", axis=None), text="testo:N",   # asse unico: lo disegna la barra
        color=alt.condition(alt.datum.tipo == "totale",
                            alt.value(branding.C_BP), alt.value("#8a8484")))
    ui.legenda_versioni(ctx, tratteggio_b=False)
    branding.altair_it((barre + testi).properties(height=330))
    st.caption("Barre piene = totali (ricavi, PM lordo, EBITDA, utile netto); barre chiare "
               "= passaggi. Le imposte sono annuali e imputate a dicembre.")

with c2:
    with ui.pannello("💶 Composizione dei costi", "v2_costi"):
        valori = [(nome, _costi(ctx.a, voci), voci) for nome, voci in blocchi]
        totale = sum(v for _, v, _ in valori)
        ricavi = ctx.a.voce("ricavi", p)
        if totale <= 0:
            st.info(f"Nessun costo a piano nel periodo ({periodo_txt}).")
        else:
            righe = []
            for nome, costo, voci in valori:
                riga = {"nome": nome, "valore": fmt.eur_compatto(costo),
                        "quota": costo / totale}
                if ctx.b is not None:
                    # stesso semaforo delle tessere e della tabella CE (soglie
                    # 5% / 10%), direzione -1: un costo più alto è sfavorevole
                    c = bc.confronta(costo, _costi(ctx.b, voci), "€", -1, None, None)
                    riga["delta"] = fmt.segno(c.assoluto, fmt.eur_compatto(c.assoluto))
                    riga["tono"] = branding.STATO_TONO[c.stato]
                elif ricavi > 1e-9:
                    riga["delta"] = f"{fmt.pct(costo / ricavi, 0)} ricavi"
                righe.append(riga)
            ui.barre(righe)
            su_ricavi = (f" · {fmt.pct(totale / ricavi, 0)} dei ricavi"
                         if ricavi > 1e-9 else "")
            coda = (f"A destra lo scostamento di {ctx.nome_b} (positivo = spende di più): "
                    "verde se in risparmio o in linea, ambra oltre il +5%, rosso oltre il +10%."
                    if ctx.b is not None else
                    "A destra l'incidenza sui ricavi del periodo.")
            st.caption(f"Costi fino all'EBITDA · {periodo_txt}: {fmt.eur_compatto(totale)}"
                       f"{su_ricavi}. La barra è la quota sul totale. {coda}")

    with ui.pannello("📈 Andamento mensile", "v2_mensile"):
        livello1 = [v for v in bi.VOCI if v.livello == 1]
        codici = [v.codice for v in livello1]
        nomi = {v.codice: v.etichetta for v in livello1}
        f1, f2 = st.columns([1.5, 1])
        voce = f1.selectbox("Voce", codici, index=codici.index("ebitda"), format_func=nomi.get,
                            key="v2_voce")
        modo = f2.segmented_control("Valori", ["Cumulati", "Mensili"], default="Cumulati",
                                    key="v2_modo") or "Cumulati"
        df = ui.serie_confronto(ctx, [p.anno], cumulato=(modo == "Cumulati"), scala=1e3, voce=voce)
        ui.legenda_versioni(ctx)
        if df.empty:
            st.info("Nessun valore per la voce nell'anno selezionato.")
        else:
            branding.altair_it(ui.grafico_linee(df, ctx, "k€", altezza=250))

with ui.pannello("🧾 Conto economico sintetico", "v2_ce"):
    dettaglio = st.segmented_control("Dettaglio", ["Voci principali", "Con sottovoci"],
                                     default="Voci principali", key="v2_dettaglio") or "Voci principali"
    t = bc.ce_sintetico(ctx.a, ctx.b, p, 1 if dettaglio == "Voci principali" else 2)
    t = t[~t["codice"].isin(riservate)].reset_index(drop=True)
    mese_txt = fmt.MESI_LUNGHI[p.mese_a - 1].capitalize()
    if ctx.b is None:
        show = pd.DataFrame({
            "Voce": t["voce"],
            f"{mese_txt} {p.anno}": t["mese"].map(fmt.eur),
            "Periodo": t["periodo"].map(fmt.eur),
            f"Anno {p.anno}": t["anno"].map(fmt.eur),
            "% sui ricavi": t["su_ricavi"].map(fmt.pct),
        })
        export = t[["voce", "mese", "periodo", "anno", "su_ricavi"]].rename(columns={
            "mese": f"{mese_txt} {p.anno}", "periodo": periodo_txt, "anno": f"anno {p.anno}",
            "su_ricavi": "quota su ricavi"})
    else:
        show = pd.DataFrame({
            "Voce": t["voce"],
            f"{ctx.nome_a}": t["periodo"].map(fmt.eur),
            f"{ctx.nome_b}": t["confronto_periodo"].map(fmt.eur),
            "Δ €": [fmt.segno(v, fmt.numero(v)) for v in t["delta"]],
            "Δ %": t["delta_pct"].map(fmt.pct_segno),
            "Esito": t["stato"].map(ui.STATO_TESTO),
            f"{ctx.nome_a} · anno": t["anno"].map(fmt.eur),
            f"{ctx.nome_b} · anno": t["confronto_anno"].map(fmt.eur),
        })
        export = t[["voce", "periodo", "confronto_periodo", "delta", "delta_pct", "stato",
                    "anno", "confronto_anno"]]
    nature = t["natura"].tolist()
    stile = show.style.apply(
        lambda r: ["font-weight: 700; background-color: #f8fafc"
                   if nature[r.name] == "margine" else "" for _ in r], axis=1)
    ev = st.dataframe(stile, hide_index=True, width="stretch", on_select="rerun",
                      selection_mode="single-row", key="v2_tabella",
                      height=min(40 + 35 * len(show), 720))
    righe_sel = getattr(getattr(ev, "selection", None), "rows", []) or []
    if righe_sel:
        scelta = t.iloc[righe_sel[0]]
        st.session_state["v6_voce"] = scelta["codice"]
        st.page_link(registro_moduli.PER_CODICE["V6"].file, icon="🌡️",
                     label=f"Apri «{scelta['voce'].strip()}» in Scostamenti voce × mese")
    else:
        st.caption(f"Periodo {periodo_txt}. Seleziona una riga per aprirla mese per mese "
                   "nella vista Scostamenti. I costi hanno segno negativo come nel BP.")
    ui.scarica(export, f"ce_sintetico_{p.anno}")
