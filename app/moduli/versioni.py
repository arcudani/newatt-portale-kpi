"""
V11 — Versioni (L300). Blueprint §5, §8, §9.

Elenco delle versioni, esito della quadratura con l'Excel (±0,1% per voce
annuale), confronto dei KPI del Cruscotto tra due versioni. Admin: cambio
stato (una versione fuori quadratura non è approvabile) ed eliminazione
delle bozze. Admin ed editor: import di un nuovo BP Excel come bozza.

Forma (linguaggio DeD): scheda della versione con numero dominante e
pillole di stato, quadratura scomposta in barre orizzontali per grandezza,
esiti del confronto KPI riassunti in pillole prima della tabella.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import bp_calcoli as bc
import bp_dati
import bp_import as bi
import branding
import formato as fmt
import ui

ctx = ui.carica_contesto()
ui.testata("V11", "Quale versione del piano stiamo leggendo, e quadra con l'Excel?", ctx)

versioni = bp_dati.carica_versioni()
if not ctx.bros:
    versioni = versioni[versioni["stato"] == "approvata"]
ICONA_STATO = {"approvata": "✅ approvata", "bozza": "✏️ bozza", "archiviata": "🗄️ archiviata"}
TONO_STATO = {"approvata": "buono", "bozza": "attenzione", "archiviata": "neutro"}
ETICHETTA_ESITO = {"ok": ("KPI in linea", "KPI in linea"),
                   "warn": ("KPI in attenzione", "KPI in attenzione"),
                   "crit": ("KPI critico", "KPI critici"),
                   "neutral": ("KPI neutro", "KPI neutri")}


def _quadratura_txt(r) -> str:
    q = r["quadratura"] or []
    if not q:
        return f"{fmt.ND} · nessun esito"      # mai «✓ 0/0» (blueprint §3)
    ko = sum(1 for x in q if not x.get("ok"))
    return f"✓ {len(q) - ko}/{len(q)}" if ko == 0 else f"✗ {ko} fuori tolleranza"


def _data(v) -> str:
    return "" if v is None or pd.isna(v) else f"{pd.Timestamp(v):%d/%m/%Y %H:%M}"


# --- markup del design system (pillole di stato, blocchi con numero dominante) ---

def _conta(n: int, singolare: str, plurale: str) -> str:
    return f"{fmt.numero(n)} {singolare if n == 1 else plurale}"


def _pillola(testo: str, tono: str = "neutro") -> str:
    """Come le pillole delle tessere (ui._html_badges): un testo che inizia
    con «!» porta l'icona tonda del design system, non il punto esclamativo."""
    icona = "<span class='ico'>!</span>" if testo.startswith("!") else ""
    return f"<span class='mg-pill {tono}'>{icona}{escape(testo.lstrip('! '))}</span>"


def _pillole(pezzi: list[tuple[str, str]]) -> None:
    """Riga di pillole di stato (solo quelle valorizzate)."""
    corpo = "".join(_pillola(t, tono) for t, tono in pezzi if t)
    if corpo:
        st.markdown(f"<div class='mg-hk-badges' style='margin:0 0 10px'>{corpo}</div>",
                    unsafe_allow_html=True)


def _blocco(etichetta: str, valore: str, unita: str = "", pillole=(), note=(),
            nd: bool = False, compatto: bool = False, vsep: bool = False) -> str:
    """Blocco «numero dominante» della scheda versione: etichetta piccola in
    maiuscoletto, valore grande, pillole di stato, righe di dettaglio."""
    classi = "mg-hk vsep" if vsep else "mg-hk"
    classe_val = "mg-hk-val nd" if nd else "mg-hk-val"
    stile = ("" if nd or not compatto else
             " style='font-size:clamp(19px,2vw,28px);letter-spacing:-.6px;white-space:normal'")
    piccola = f"<small>{escape(unita)}</small>" if unita else ""
    badge = "".join(_pillola(t, tono) for t, tono in pillole if t)
    badge = f"<div class='mg-hk-badges'>{badge}</div>" if badge else ""
    sub = "".join(f"<div class='mg-hk-sub'>{n}</div>" for n in note if n)
    return (f"<div class='{classi}'><div class='mg-hk-top'>"
            f"<span class='mg-hk-label'>{escape(etichetta)}</span></div>"
            f"<div class='{classe_val}'{stile}>{escape(valore)}{piccola}</div>"
            f"{badge}{sub}</div>")


def _barre_quadratura(q: pd.DataFrame) -> list[dict]:
    """Una barra per grandezza: quota di controlli in tolleranza e
    scostamento massimo rilevato (scomposizione statica, stile DeD)."""
    righe = []
    for grandezza, g in q.groupby("grandezza", sort=False):
        totale = len(g)
        ok = int(g["ok"].astype(bool).sum())
        scost = (pd.to_numeric(g.get("delta_pct"), errors="coerce").abs().max()
                 if "delta_pct" in g else None)
        delta = "" if fmt.manca(scost) else f"scost. max {fmt.pct(float(scost), 2)}"
        tono = "buono" if ok == totale else "cattivo"
        righe.append({"nome": str(grandezza), "valore": f"{ok}/{totale}",
                      "quota": ok / totale if totale else 0.0, "delta": delta,
                      "tono": tono, "colore": branding.TONO_COLORE[tono]})
    return righe


if versioni.empty:
    st.info("Nessuna versione disponibile." if ctx.bros else
            "Nessuna versione è ancora stata approvata da Bros.")
else:
    ids = [int(i) for i in versioni["id"]]
    nomi = dict(zip(ids, versioni["nome"]))
    predefinita = ctx.versione["id"] if ctx.versione and ctx.versione["id"] in ids else ids[0]
    sel = st.selectbox("Versione da esaminare", ids, index=ids.index(predefinita),
                       format_func=nomi.get, key="v11_sel")
    riga = versioni[versioni["id"] == sel].iloc[0]

    # --- Scheda della versione in esame: stato e quadratura a colpo d'occhio ---
    qt = pd.DataFrame(riga["quadratura"] or [])
    n_tot = len(qt)
    n_ok = int(qt["ok"].astype(bool).sum()) if n_tot else 0
    n_ko = n_tot - n_ok
    stato = str(riga["stato"])
    approvata = stato == "approvata"
    # stessa fonte del bottone «Approva» (bp_dati rifiuta se non è TRUE)
    quadra = bool(riga["quadratura_ok"])
    cambio = _data(riga["stato_il"])

    with ui.pannello("🧾 Versione in esame", "v11_scheda"):
        blocchi = [
            _blocco("Versione", str(riga["nome"]), compatto=True,
                    pillole=[(ICONA_STATO.get(stato, stato), TONO_STATO.get(stato, "neutro"))],
                    note=[f"origine: <b>{escape(str(riga['origine'] or '—'))}</b>",
                          f"creata da <b>{escape(str(riga['creata_da'] or '—'))}</b> "
                          f"il {escape(_data(riga['created_at']) or '—')}",
                          f"ultimo cambio stato: <b>{escape(cambio)}</b> · "
                          f"{escape(str(riga['stato_da'] or '—'))}" if cambio else ""]),
            _blocco("Quadratura Excel",
                    fmt.numero(n_ok) if n_tot else fmt.ND,
                    f"su {_conta(n_tot, 'controllo', 'controlli')}" if n_tot else "",
                    nd=not n_tot, vsep=True,
                    pillole=[("✓ tutti in tolleranza", "buono") if n_tot and not n_ko
                             else (f"! {_conta(n_ko, 'controllo fuori tolleranza', 'controlli fuori tolleranza')}",
                                   "cattivo") if n_tot
                             else ("nessun esito registrato", "neutro")],
                    note=["tolleranza <b>±0,1%</b> per voce annuale (o 1 €)",
                          "una versione fuori quadratura non è approvabile"]),
            _blocco("Visibile a NeWatt", "Sì" if approvata else "No", compatto=True, vsep=True,
                    pillole=[("perimetro NeWatt", "buono") if approvata
                             else ("solo Bros", "neutro")],
                    note=["Il viewer NeWatt vede solo le versioni <b>approvate</b>: "
                          "bozze e archiviate restano interne."]),
        ]
        colonne = st.columns(3, gap="small")
        for col, html in zip(colonne, blocchi):
            col.markdown(html, unsafe_allow_html=True)

    with ui.pannello("🗂️ Versioni del BP", "v11_elenco"):
        stati = versioni["stato"].value_counts()
        n_app, n_boz, n_arc = (int(stati.get(s, 0)) for s in
                               ("approvata", "bozza", "archiviata"))
        # una versione senza esito registrato non è «fuori quadratura»: è n.d.
        con_esito = versioni["quadratura"].map(bool)
        ok_q = versioni["quadratura_ok"].fillna(False).astype(bool)
        fuori = int((con_esito & ~ok_q).sum())
        senza = int((~con_esito).sum())
        _pillole([
            (_conta(len(versioni), "versione", "versioni"), "neutro"),
            (_conta(n_app, "approvata", "approvate"), "buono") if n_app
            else ("nessuna versione approvata", "attenzione"),
            (_conta(n_boz, "bozza", "bozze"), "attenzione") if n_boz else ("", "neutro"),
            (_conta(n_arc, "archiviata", "archiviate"), "neutro") if n_arc else ("", "neutro"),
            (f"! {_conta(fuori, 'versione fuori quadratura', 'versioni fuori quadratura')}",
             "cattivo") if fuori else ("", "neutro"),
            (_conta(senza, "versione senza esito di quadratura",
                    "versioni senza esito di quadratura"), "neutro") if senza else ("", "neutro"),
            ("tutte in quadratura con l'Excel", "buono") if not fuori and not senza
            else ("", "neutro"),
        ])
        show = pd.DataFrame({
            "Versione": versioni["nome"], "Stato": versioni["stato"].map(ICONA_STATO),
            "Origine": versioni["origine"], "Creata da": versioni["creata_da"],
            "Creata il": versioni["created_at"].map(_data),
            "Quadratura Excel": versioni.apply(_quadratura_txt, axis=1),
            "Ultimo cambio stato": [f"{_data(i)} · {d}" if d else "" for i, d in
                                    zip(versioni["stato_il"], versioni["stato_da"])],
            "Descrizione": versioni["descrizione"],
        })
        st.dataframe(show, hide_index=True, width="stretch")

    c1, c2 = st.columns([1.25, 1])
    with c1, ui.pannello("🧮 Quadratura con l'Excel", "v11_quadratura"):
        if qt.empty:
            st.caption("Nessun esito di quadratura registrato.")
        else:
            ui.barre(_barre_quadratura(qt))
            st.caption("Controlli in tolleranza per grandezza · somme annue dei mesi importati "
                       "confrontate con il foglio «Riepilogo Business Plan».")
            st.divider()
            q = qt
            solo_ko = st.toggle("Solo fuori tolleranza", value=False, key="v11_solo_ko")
            if solo_ko:
                q = q[~q["ok"].astype(bool)]
            qs = pd.DataFrame({"Grandezza": q["grandezza"], "Anno": q["anno"].astype(str),
                               "Excel": q["excel"].map(fmt.numero),
                               "Import": q["motore"].map(fmt.numero),
                               "Δ": q["delta"].map(lambda v: fmt.numero(v, 2)),
                               "Esito": q["ok"].map({True: "✓ ok", False: "✗ fuori ±0,1%"})})
            st.dataframe(qs, hide_index=True, width="stretch", height=320)
            ui.scarica(q, f"quadratura_{riga['nome']}")

    with c2, ui.pannello("⚖️ KPI a confronto", "v11_kpi"):
        altre = [i for i in ids if i != sel]
        if not altre:
            st.caption("Serve almeno una seconda versione per il confronto.")
        else:
            altra = st.selectbox("Confronta con", altre, format_func=nomi.get, key="v11_altra")
            anno = ctx.periodo.anno
            da = bc.Dati(bp_dati.carica_ce(sel), bp_dati.carica_driver(sel))
            db_ = bc.Dati(bp_dati.carica_ce(altra), bp_dati.carica_driver(altra))
            cat = ctx.catalogo[ctx.catalogo["vista"] == "V1"].sort_values("ordine")
            righe = []
            esiti: dict[str, int] = {}
            for _, k in cat.iterrows():
                ma = bc.calcola(k["codice"], da, bc.Periodo(anno), da)
                mb = bc.calcola(k["codice"], db_, bc.Periodo(anno), da)
                if ma is None or mb is None:
                    continue
                c = bc.confronta(ma.valore, mb.valore, k["unita"], int(k["direzione"]),
                                 k["soglia_gialla"], k["soglia_rossa"])
                esiti[c.stato] = esiti.get(c.stato, 0) + 1
                righe.append({"KPI": k["nome"], nomi[sel]: " ".join(fmt.formatta(ma.valore, k["unita"])),
                              nomi[altra]: " ".join(fmt.formatta(mb.valore, k["unita"])),
                              "Δ": fmt.formatta_delta(c.assoluto, c.relativo, k["unita"]),
                              "Esito": ui.STATO_TESTO[c.stato]})
            if not righe:      # mai una tabella vuota senza spiegazione (§3)
                st.caption(f"{fmt.ND} · nessun KPI del Cruscotto è calcolabile su "
                           f"entrambe le versioni per l'anno {anno}.")
            else:
                _pillole([(_conta(esiti[s], *ETICHETTA_ESITO[s]), branding.STATO_TONO[s])
                          for s in ("crit", "warn", "ok", "neutral") if esiti.get(s)])
                st.caption(f"KPI del Cruscotto · anno {anno} intero (dal filtro globale) · "
                           f"riferimento «{nomi[sel]}»")
                st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")

    if ctx.ruolo == "admin":
        with ui.pannello("🔐 Stato della versione", "v11_stato"):
            # «nessun esito registrato» non è una quadratura KO: resta n.d. (§3)
            if quadra:
                approvabilita = ("", "neutro") if approvata else ("approvabile", "buono")
            elif n_tot:
                approvabilita = ("! quadratura KO: non approvabile", "cattivo")
            else:
                approvabilita = (f"{fmt.ND} · nessun esito di quadratura: non approvabile",
                                 "attenzione")
            _pillole([
                (f"{ICONA_STATO.get(stato, stato)} · {riga['nome']}",
                 TONO_STATO.get(stato, "neutro")),
                approvabilita,
            ])
            b1, b2, b3, b4 = st.columns(4)
            if b1.button("✅ Approva", disabled=approvata or not quadra,
                         help=None if quadra else
                         ("Quadratura KO: non approvabile" if n_tot else
                          "Nessun esito di quadratura registrato: non approvabile"),
                         type="primary", key="v11_approva"):
                bp_dati.aggiorna_stato(sel, "approvata", ctx.utente)
                st.rerun()
            if b2.button("✏️ Riporta in bozza", disabled=stato == "bozza", key="v11_bozza"):
                bp_dati.aggiorna_stato(sel, "bozza", ctx.utente)
                st.rerun()
            if b3.button("🗄️ Archivia", disabled=stato == "archiviata", key="v11_archivia"):
                bp_dati.aggiorna_stato(sel, "archiviata", ctx.utente)
                st.rerun()
            conferma = b4.checkbox("Confermo l'eliminazione", key="v11_conferma",
                                   disabled=stato != "bozza")
            if b4.button("🗑️ Elimina bozza", disabled=stato != "bozza" or not conferma,
                         key="v11_elimina"):
                bp_dati.elimina_bozza(sel)
                st.rerun()
            st.caption("Il viewer NeWatt vede solo le versioni approvate; le bozze si possono "
                       "eliminare, le versioni approvate e archiviate no.")
    elif ctx.ruolo == "editor":
        st.caption("Approvazione e archiviazione delle versioni sono riservate agli admin.")


@st.cache_data(show_spinner="📥 Leggo il BP Excel…", max_entries=3)
def _leggi(contenuto: bytes) -> bi.BPImportato:
    return bi.leggi_bp(contenuto)


if ctx.bros:
    with ui.pannello("📤 Importa un BP Excel (bozza)", "v11_import"):
        st.caption("Si leggono i valori calcolati dei fogli Risultato Mensile, CdV, IPO FTE e "
                   "Personale; la quadratura con il Riepilogo è obbligatoria per approvare.")
        up = st.file_uploader("BP Excel (.xlsx)", type=["xlsx"], key="v11_upload")
        if up is not None:
            try:
                bp = _leggi(up.getvalue())
            except bi.StrutturaInattesa as e:
                st.error(f"Il file non ha la struttura attesa del BP: {e}")
                st.stop()
            ko = [x for x in bp.quadratura if not x["ok"]]
            n_q = len(bp.quadratura)
            if not n_q:      # nessun controllo eseguito: mai un «0/0» verde (§3)
                esito_q = [(f"! {fmt.ND} · nessun controllo di quadratura eseguito",
                            "attenzione")]
            else:
                esito_q = [
                    (f"{fmt.numero(n_q - len(ko))} su "
                     f"{_conta(n_q, 'controllo', 'controlli')} in tolleranza",
                     "cattivo" if ko else "buono"),
                    (f"! {_conta(len(ko), 'controllo fuori tolleranza', 'controlli fuori tolleranza')}"
                     " · non approvabile", "cattivo") if ko
                    else ("quadratura Excel OK", "buono"),
                ]
            _pillole(esito_q + [
                (f"! {_conta(len(bp.avvisi), 'avviso di lettura', 'avvisi di lettura')}",
                 "attenzione") if bp.avvisi else ("", "neutro"),
            ])
            for a in bp.avvisi:
                st.warning(a)
            nome = st.text_input("Nome della versione", value=Path(up.name).stem, key="v11_nome")
            descr = st.text_input("Descrizione", key="v11_descr")
            if st.button("Crea versione in bozza", type="primary", key="v11_crea"):
                esistenti = set(bp_dati.carica_versioni()["nome"])
                if not nome.strip() or nome.strip() in esistenti:
                    st.error("Serve un nome nuovo (i nomi delle versioni sono univoci).")
                else:
                    vid = bp_dati.salva_versione(nome.strip(), descr, up.name, bp, ctx.utente)
                    st.success(f"Versione «{nome.strip()}» creata in bozza (id {vid}).")
                    st.rerun()
