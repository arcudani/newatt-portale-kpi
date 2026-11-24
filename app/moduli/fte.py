"""
V9 — FTE e Personale (L300, sola lettura in v1). Blueprint §5.

Driver di carico (Customer Care, Operation), FTE da driver vs organico
pianificato, costo del personale. Evidenzia il doppio conteggio della base
di lavoro (PdP Agenti + PdP VAS) segnalato dalla Nota ricostruzione VAS.

Forma DeD: in testa i tre numeri dominanti della struttura (FTE Customer
Care, FTE Operation, costo per FTE: sono i KPI attivi del catalogo su cui
questa vista è il dettaglio), poi il rilievo sul doppio conteggio, i piccoli
multipli dei driver con la legenda dei due ruoli, l'organico di dicembre come
scomposizione a barre orizzontali (quota sul totale + scostamento), la tabella
per anno con export e i segnaposto in fascia per ambito.
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
ui.testata("V9", "Quali driver generano gli FTE e quanto costa la struttura?", ctx)
ui.richiedi_versione(ctx)
p = ctx.periodo

RUOLI = ["Customer Care", "Operation", "Operation VAS", "Fatturazione", "Credito",
         "Commerciale"]
# I driver di carico coprono il Servizio clienti e l'Operation: il Commerciale
# non ha driver, quindi resta fuori dal confronto "FTE da driver vs piano"
# (stesso perimetro delle tessere V5_FTE_CC / V5_FTE_OP qui in testa).
RUOLI_DA_DRIVER = ["Customer Care", *bc.RUOLI_OPERATION]
COLORE_RUOLO = {r: branding.CATEGORICHE[i] for i, r in enumerate(RUOLI)}
LIVELLI = ["Alto", "Medio", "Apprendistato", "Tirocinio"]
DRIVER = [("carico_chiamate", "Chiamate gestite", "Customer Care"),
          ("carico_contatti_scritti", "Contatti scritti", "Customer Care"),
          ("carico_reclami", "Reclami", "Customer Care"),
          ("carico_fatture", "Fatture emesse", "Operation"),
          ("carico_switch_in", "Pratiche switch-in", "Operation"),
          ("carico_cessazioni", "Pratiche di cessazione", "Operation"),
          ("carico_volture", "Volture e subentri", "Operation"),
          ("carico_incassi", "Pratiche incasso", "Operation")]

# Tessere in testa (DeD: prima il numero, poi il grafico). Il catalogo tiene FTE
# e costo per FTE nell'ambito Struttura della V5 e questa vista ne è il dettaglio
# L300: li si mostra qui insieme agli eventuali KPI attivi della V9, così la
# pagina apre con i numeri di cui parla.
CODICI_TESTA = ["V5_FTE_CC", "V5_FTE_OP", "V5_COSTO_FTE"]
attivi_v9 = ctx.catalogo[(ctx.catalogo["vista"] == "V9")
                         & (ctx.catalogo["stato"] == "attivo")]["codice"].tolist()
ui.tessere(ctx, CODICI_TESTA + attivi_v9, per_riga=3)

base = ctx.a.stock("pdp_base_fte", p.anno, 12, ruolo="Customer Care")
agenti = ctx.a.stock("pdp_attivi", p.anno, 12, canale="Agenti")
if agenti > 0 and base > agenti * 1.01:
    ui.nota(f"<b>Doppio conteggio nella base di lavoro.</b> I fogli FTE sommano i PdP del "
            f"canale Agenti e quelli del canale VAS: a dicembre {p.anno} "
            f"<b>{fmt.numero(base)}</b> punti contro <b>{fmt.numero(agenti)}</b> clienti "
            f"effettivi ({fmt.pct_segno(base / agenti - 1)}). Con la logica di cross-sell sono "
            "gli stessi clienti: la Nota ricostruzione VAS stima circa il 30% di FTE in meno.")

with ui.pannello(f"📦 Driver di carico per mese · {p.anno}", "v9_driver"):
    st.markdown(branding.legenda([("solid", COLORE_RUOLO["Customer Care"], "Customer Care"),
                                  ("solid", COLORE_RUOLO["Operation"], "Operation")]),
                unsafe_allow_html=True)
    mesi = [m for m in range(1, 13) if (p.anno, m) >= bi.INIZIO_PIANO]
    etichette = [fmt.mese_label(p.anno, m) for m in mesi]
    for inizio in (0, 4):
        colonne = st.columns(4)
        for col, (drv, titolo, ruolo) in zip(colonne, DRIVER[inizio:inizio + 4]):
            serie = ctx.a.mensile(drv, p.anno, ruolo=ruolo)
            df = pd.DataFrame({"etichetta": etichette, "valore": [serie[m - 1] for m in mesi]})
            df["testo"] = df["valore"].map(fmt.numero)
            with col:
                st.markdown(f"<div class='mg-k-name'>{titolo}</div>", unsafe_allow_html=True)
                branding.altair_it(alt.Chart(df).mark_line(
                    color=COLORE_RUOLO[ruolo], strokeWidth=2,
                    point=alt.OverlayMarkDef(size=18)).encode(
                    x=alt.X("etichetta:N", sort=etichette, title=None,
                            axis=alt.Axis(labelAngle=0, values=etichette[::3])),
                    y=alt.Y("valore:Q", title=None),
                    tooltip=[alt.Tooltip("etichetta:N", title="Mese"),
                             alt.Tooltip("testo:N", title="N. / mese")]).properties(height=130))
    didascalia = ("Volumi al mese lavorati da operatore (al netto dell'automazione), dai fogli "
                  "IPO - FTE Customer Care e IPO - FTE Operation.")
    if ctx.b is not None:      # i driver non hanno confronto: dire quale versione si legge
        didascalia += f" Le serie sono quelle della versione di riferimento {ctx.nome_a}."
    st.caption(didascalia)


def _riga_ruolo(ruolo: str, valore: float, totale: float, dec: int) -> dict:
    """Una riga di ui.barre: organico di dicembre, quota sul totale e, se c'è
    uno scenario di confronto, lo scostamento con il suo semaforo (altrimenti
    la variazione sul dicembre precedente)."""
    quota = valore / totale if totale > 1e-9 else 0.0
    riga = {"nome": ruolo, "quota": quota, "colore": COLORE_RUOLO[ruolo],
            "valore": f"{fmt.numero(valore, dec)} · {fmt.pct(quota, 0)}"}
    if ctx.b is not None:
        c = bc.confronta(valore, ctx.b.stock("fte_pianificati", p.anno, 12, ruolo=ruolo),
                         "N.", 0, None, None)
        if c.relativo is not None:
            riga["delta"] = f"{fmt.pct_segno(c.relativo)} vs {ctx.nome_b}"
            riga["tono"] = branding.STATO_TONO[c.stato]
    elif (p.anno - 1) in ctx.a.anni:
        diff = valore - ctx.a.stock("fte_pianificati", p.anno - 1, 12, ruolo=ruolo)
        if abs(diff) >= 0.05:      # niente pillola quando l'organico non si muove
            riga["delta"] = f"{fmt.segno(diff, fmt.numero(diff, dec))} vs dic {p.anno - 1}"
            riga["tono"] = "neutro"
    return riga


def _riga_livello(livello: str, organico: dict, totale: float, dec: int) -> dict:
    """Stessa grammatica delle righe per ruolo (persone · quota) così la
    lettura non cambia a metà pannello; i salari dell'anno restano di fianco
    come annotazione secondaria."""
    salari = -ctx.a.flusso("salari_livello", p.anno_intero(), ruolo=livello)
    quota = organico[livello] / totale if totale > 1e-9 else 0.0
    riga = {"nome": livello, "quota": quota,
            "valore": f"{fmt.numero(organico[livello], dec)} · {fmt.pct(quota, 0)}"}
    if abs(salari) >= 1:
        riga["delta"], riga["tono"] = fmt.eur_compatto(salari), "neutro"
    return riga


c1, c2 = st.columns([1, 1.3])
with c1, ui.pannello(f"🏢 Organico pianificato · dicembre {p.anno}", "v9_organico"):
    org_ruolo = {r: ctx.a.stock("fte_pianificati", p.anno, 12, ruolo=r) for r in RUOLI}
    org_liv = {lv: ctx.a.stock("organico_livello", p.anno, 12, ruolo=lv) for lv in LIVELLI}
    totale_ruoli = sum(org_ruolo.values())
    presenti = sorted([r for r in RUOLI if org_ruolo[r] > 0],
                      key=lambda r: -org_ruolo[r])
    # un decimale solo se l'organico è frazionario, e lo stesso nei due blocchi
    dec = 0 if all(abs(v - round(v)) < 0.05 for v in
                   list(org_ruolo.values()) + list(org_liv.values())) else 1
    if not presenti:
        st.caption(f"Il BP non prevede organico pianificato a dicembre {p.anno} "
                   "(anno di avviamento).")
    else:
        st.caption(f"Totale <b>{fmt.numero(totale_ruoli, dec)}</b> persone · {ctx.nome_a} · "
                   "quota di ogni ruolo sull'organico di fine anno.", unsafe_allow_html=True)
        st.markdown("<div class='mg-side-label'>Per ruolo</div>", unsafe_allow_html=True)
        ui.barre([_riga_ruolo(r, org_ruolo[r], totale_ruoli, dec) for r in presenti])

    livelli_presenti = [lv for lv in LIVELLI if org_liv[lv]
                        or ctx.a.flusso("salari_livello", p.anno_intero(), ruolo=lv)]
    if livelli_presenti:
        st.markdown("<div class='mg-side-label'>Per livello contrattuale</div>",
                    unsafe_allow_html=True)
        totale_liv = sum(org_liv[lv] for lv in livelli_presenti)
        ui.barre([_riga_livello(lv, org_liv, totale_liv, dec) for lv in livelli_presenti])
        st.caption(f"Persone a dicembre {p.anno} per livello e, di fianco, i salari "
                   f"dell'anno {p.anno} (fogli Riepilogo Livelli e Salari e Stipendi).")

with c2, ui.pannello("📊 FTE da driver, organico e costo per anno", "v9_tabella"):
    righe = []
    for a in ctx.a.anni:
        pa = bc.Periodo(a)
        cc = ctx.a.mensile("fte_necessari", a, ruolo="Customer Care")
        op = ctx.a.mensile("fte_necessari", a, ruolo="Operation")
        piano = ctx.a.stock_medio("fte_pianificati", pa)
        coperti = ctx.a.stock_medio("fte_pianificati", pa, ruolo=RUOLI_DA_DRIVER)
        costo = -ctx.a.voce("personale", pa)
        mesi_a = [m for m in range(1, 13) if (a, m) >= bi.INIZIO_PIANO]
        cc_m = sum(cc[m - 1] for m in mesi_a) / len(mesi_a)
        op_m = sum(op[m - 1] for m in mesi_a) / len(mesi_a)
        righe.append({"Anno": a, "FTE CC medi": cc_m, "FTE CC picco": max(cc),
                      "FTE Operation medi": op_m, "FTE Operation picco": max(op),
                      "Organico pianificato medio": piano,
                      "Gap medio (driver − piano)": cc_m + op_m - coperti,
                      "Costo personale (€)": costo,
                      "Costo per FTE pianificato (€)": (costo / piano) if piano > 0 else None})
    tab = pd.DataFrame(righe)
    show = tab.copy()
    for c in show.columns[1:]:
        dec_c = 0 if "€" in c else 1
        show[c] = show[c].map(lambda v, d=dec_c: fmt.numero(v, d))
    show["Anno"] = show["Anno"].astype(str)
    st.dataframe(show, hide_index=True, width="stretch")
    st.caption("Gli FTE da driver sono la media dei mesi di piano; il gap li confronta con "
               "l'organico dei soli ruoli che hanno un driver (Commerciale escluso), come le "
               "tessere in testa. Il costo del CE è quello del personale operativo.")
    ui.scarica(tab, "fte_personale")

st.markdown("<div class='mg-side-label'>Segnaposto DeD · in arrivo con le fonti operative</div>",
            unsafe_allow_html=True)
ui.ambiti(ctx, "V9", layout="fasce", stato="segnaposto", per_riga=4)
