"""
Test del Portale KPI NeWatt su dati FITTIZI (nessun DB, nessun dato reale):
lettura del foglio DASHBOARD, errori per chi carica il file, mese di
competenza, valore del singolo mese dai dati YTD, slicer Commodity, pagine e
permessi (ruolo e perimetro di società).

Esecuzione (da dentro app\\):  .venv\\Scripts\\python.exe test_kpi.py
"""
from __future__ import annotations

import re

import pandas as pd

from streamlit.testing.v1 import AppTest

import auth
import dati_prova as dp
import kpi_catalogo as kc
import kpi_dati
import kpi_import as ki
import kpi_obiettivi as ko
import registro_moduli
import ui_kpi


def _errore(contenuto: bytes, nome: str = "prova.xlsx") -> str:
    try:
        ki.leggi_dashboard(contenuto, nome)
    except ki.ImportKPIError as e:
        return str(e)
    raise AssertionError("ImportKPIError atteso")


def test_lettura_dashboard():
    valori = dp.valori_kpi_prova()
    imp = ki.leggi_dashboard(dp.workbook_kpi(valori=valori), "17.11.2026.Dashboard KPI.xlsx")
    assert (imp.societa, imp.anno, imp.mese) == ("gazel", 2026, 10)
    assert imp.n_valori == len(kc.MISURE) and not imp.mancanti and not imp.avvisi
    assert all(abs(imp.valori[c] - v) < 1e-9 for c, v in valori.items()), "valori letti per etichetta"
    assert imp.testi == {"CHURN_MAX": "febbraio 2026", "CHURN_MIN": "gennaio 2026"}
    assert len(imp.sha256) == 64
    assert ki.leggi_titolo("kpi monitoring LifeGate  marzo 2027") == ("lifegate", 2027, 3)
    assert ki.leggi_titolo("KPI MONITORING MIGLIORA DICEMBRE 2026") == ("migliora", 2026, 12)
    assert ki.leggi_titolo("Report qualsiasi") == (None, None, None)
    print("OK - foglio DASHBOARD: 37/37 misure per etichetta, titolo -> società e mese, "
          "testo del churn max/min")


def test_competenza_e_righe():
    assert kc.competenza(2026, 10, "M-1") == (2026, 9)
    assert kc.competenza(2027, 1, "M-1") == (2026, 12), "gennaio: M-1 è dicembre dell'anno prima"
    assert kc.competenza(2026, 10, "M") == (2026, 10)
    imp = ki.leggi_dashboard(dp.workbook_kpi(), "x.xlsx")
    righe = {r["codice"]: r for r in ki.righe_da_salvare(imp, 2026, 10)}
    assert (righe["EBITDA"]["anno_comp"], righe["EBITDA"]["mese_comp"]) == (2026, 9)
    assert (righe["SALES_BP"]["anno_comp"], righe["SALES_BP"]["mese_comp"]) == (2026, 10)
    assert righe["CHURN_MAX"]["testo"] == "febbraio 2026" and len(righe) == len(kc.MISURE)
    print("OK - mese di competenza (M / M-1, anche a cavallo d'anno) su ogni riga da salvare")


def test_errori_per_chi_carica():
    assert ".xlsx" in _errore(b"x", "vecchio.xls")
    assert "non è un Excel" in _errore(b"a;b", "export.csv")
    assert "vuoto" in _errore(b"", "vuoto.xlsx")
    assert "password" in _errore(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 100)
    assert "danneggiato" in _errore(b"questo non e' un excel")
    msg = _errore(dp.workbook_kpi(foglio="Foglio1", altri_fogli=("CRM FORNITURE",)))
    assert "DASHBOARD" in msg and "Foglio1" in msg, "dice quali fogli ha trovato"
    msg = _errore(dp.workbook_kpi(togli=tuple(m.codice for m in kc.MISURE[:25])))
    assert "non sembra la Dashboard KPI" in msg
    # avvisi (non bloccanti): misure mancanti, formule in errore, celle vuote, titolo
    imp = ki.leggi_dashboard(dp.workbook_kpi(togli=("PFN",), errori={"CTS": "#DIV/0!"},
                                             vuoti=("SDD",), titolo="Report ottobre"), "x.xlsx")
    testo = " ".join(imp.avvisi)
    assert imp.valori["PFN"] is None and "PFN M -1" in testo
    assert imp.valori["CTS"] is None and "#DIV/0!" in testo
    assert imp.valori["SDD"] is None and "senza valore numerico" in testo
    assert imp.societa is None and "scegli tu società e mese" in testo
    print("OK - errori comprensibili: .xls/.csv/vuoto/protetto/danneggiato/senza DASHBOARD/"
          "foglio sbagliato; avvisi su mancanti, #DIV/0!, celle vuote, titolo")


def test_etichetta_vuota_non_ruba():
    """Una misura senza valore non prende il numero della misura sotto."""
    imp = ki.leggi_dashboard(dp.workbook_kpi(vuoti=("EBITDA",)), "x.xlsx")
    assert imp.valori["EBITDA"] is None and imp.valori["PFN"] is not None
    print("OK - etichetta senza valore: resta vuota, non ruba il numero della successiva")


def test_modello_riquadri():
    df = dp.valori_kpi_df()
    ott, sett = ui_kpi._mappa(df, 2026, 10), ui_kpi._mappa(df, 2026, 9)
    t = {x.codice: x for x in kc.TESSERE}
    ebitda = ui_kpi.modello(t["EBITDA"], ott, sett, [])
    v_ott, v_set = ott["EBITDA"][0], sett["EBITDA"][0]
    atteso = ui_kpi._testo_valore(v_ott - v_set, "€")
    assert any(f"Nel solo mese di settembre: {atteso}" == n for n in ebitda["note"]), ebitda["note"]
    assert ebitda["rif"].startswith("settembre 2026") and ebitda["stato"] == "bp"
    pfn = ui_kpi.modello(t["PFN"], ott, sett, [])
    assert pfn["delta"][0].startswith("▲") and "vs agosto" in pfn["delta"][0], pfn.get("delta")
    churn = ui_kpi.modello(t["CHURN"], ott, sett, [])
    assert set(churn["split"]) == {"Power", "Gas"} and churn["delta"][1] == "cattivo", \
        "churn in aumento: peggioramento"
    # slicer Commodity: la cifra diventa quella della commodity, una sola riga di dettaglio
    gas = ui_kpi.modello(t["PDP_ATTIVI"], ott, sett, [], commodity="Gas")
    assert list(gas["split"]) == ["Gas"] and "Solo gas naturale" in gas["note"]
    totale = ui_kpi.modello(t["PDP_ATTIVI"], ott, sett, [])
    assert totale["valore"] != gas["valore"], "punti attivi totali = POD + PDR"
    assert totale["affianco"][0] == "Churn progressivo" and "affianco" not in gas, \
        "churn progressivo (totale) accanto ai punti attivi, non sulla singola commodity"
    vuoto = ui_kpi.modello(t["EBITDA"], {}, {}, [])
    assert vuoto["stato"] == "pend" and vuoto["valore"] is None
    print("OK - riquadri: valore del solo mese dai YTD, delta vs report precedente con direzione, "
          "dettaglio luce/gas, slicer Commodity, dato mancante")


def test_registro_portale():
    assert registro_moduli.url_di(registro_moduli.PER_CODICE["G0"]) == "/"
    lettore = {m.codice for m in registro_moduli.moduli_visibili("lettore", ["gazel"])}
    assert lettore == {"G0", "GZ", "GZ2"}, "il lettore Gazel vede panoramica e i 2 livelli di Gazel"
    caric = {m.codice for m in registro_moduli.moduli_visibili("caricatore", kc.ORDINE_SOCIETA)}
    assert {"UP", "OB", "LG", "LG2", "GZ", "GZ2", "MG", "MG2"} <= caric and not any(m.startswith("V") for m in caric)
    admin = {m.codice for m in registro_moduli.moduli_visibili("admin", kc.ORDINE_SOCIETA)}
    assert {"V1", "V11", "CAT", "UP"} <= admin, "il BP Migliora è degli admin"
    assert all(m.url_path for m in registro_moduli.MODULI if not m.default)
    print("OK - registro: panoramica di atterraggio, società per perimetro, carica per "
          "admin/caricatori, BP Migliora solo admin")


def _portale(pagina: str, ruolo: str = "admin", perimetro=None, valori=None, stato=None,
             obiettivi=None) -> AppTest:
    import streamlit as st
    st.cache_data.clear()
    perimetro = perimetro if perimetro is not None else kc.ORDINE_SOCIETA
    df = valori if valori is not None else dp.valori_kpi_df()
    ob = obiettivi if obiettivi is not None else pd.DataFrame(columns=kpi_dati.COLONNE_OBIETTIVI)
    orig = (auth.require_login, auth.ruolo, auth.perimetro,
            kpi_dati.carica_valori, kpi_dati.carica_caricamenti, kpi_dati.carica_obiettivi)
    kpi_dati.carica_obiettivi = lambda s: ob[ob["societa"] == s]
    auth.require_login = lambda: "Tester"
    auth.ruolo = lambda u: ruolo
    auth.perimetro = lambda u: perimetro
    kpi_dati.carica_valori = lambda s: df[df["societa"] == s] if not df.empty else df
    kpi_dati.carica_caricamenti = lambda s=None: dp.caricamenti_prova()
    try:
        at = AppTest.from_file("app.py", default_timeout=120)
        at.session_state["authentication_status"] = True
        at.session_state["utente_autenticato"] = "Tester"
        for k, v in (stato or {}).items():
            at.session_state[k] = v
        at.run()
        at.switch_page(pagina)
        at.run()
        return at
    finally:
        (auth.require_login, auth.ruolo, auth.perimetro,
         kpi_dati.carica_valori, kpi_dati.carica_caricamenti, kpi_dati.carica_obiettivi) = orig


def _testo(at: AppTest) -> str:
    return " ".join(str(m.value) for m in at.markdown) + " " + " ".join(
        str(x.value) for x in [*at.caption, *at.info, *at.warning, *at.error])


def test_pagine_portale():
    at = _portale("moduli/kpi_gazel.py")
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    t = _testo(at)
    l1 = [x for x in kc.TESSERE if x.livello == 1]
    assert len(re.findall(r"class='mg-k[ ']", t)) == len(l1), "solo i riquadri di Livello I"
    assert "Cruscotto KPI · Gazel · Livello I" in t and "Logo_Gazel" not in t and "alt='Gazel'" in t, "logo Gazel"
    assert "--mg-top-bg:#FFFFFF" in t and "#FFAE00" in t, "tema Gazel applicato"
    assert t.count("class='mg-split'") >= 4
    assert "Nel solo mese di settembre" in t and f"Senza obiettivo · {len(l1)}" in t
    # Livello II: pagina separata con i soli riquadri del secondo livello
    at2 = _portale("moduli/kpi_gazel_l2.py")
    assert not at2.exception, [str(e.value)[:300] for e in at2.exception]
    t2 = _testo(at2)
    l2 = [x for x in kc.TESSERE if x.livello == 2]
    assert "Cruscotto KPI · Gazel · Livello II" in t2
    assert len(re.findall(r"class='mg-k[ ']", t2)) == len(l2) and f"Senza obiettivo · {len(l2)}" in t2
    # slicer Commodity sul gas
    tg = _testo(_portale("moduli/kpi_gazel.py", stato={"kpi_com_gazel": "Gas naturale"}))
    assert "Solo gas naturale" in tg and "non ripartito" not in tg
    # società senza dati: invito a caricare
    tl = _testo(_portale("moduli/kpi_lifegate.py"))
    assert "non è stato caricato nessun Excel" in tl and "--mg-top-accento:6px solid #006454" in tl,         "tema LifeGate (design NeWatt + accento verde)"
    # panoramica: una fascia per società del perimetro
    at = _portale("moduli/gruppo.py", perimetro=["gazel", "migliora"])
    tp = _testo(at)
    assert not at.exception and "Portale KPI · Gruppo NeWatt" in tp
    assert "report ottobre 2026" in tp and "nessun report caricato" in tp
    assert "COSTO PER CLIENTE" in tp.upper() and "Cost to serve" in tp and "Churn PdP" not in tp, \
        "panoramica: costo per cliente con il CtS accanto, al posto del churn"
    assert len(re.findall(r"class='mg-k[ ']", tp)) == 4 + 1, "4 KPI di Gazel + Migliora vuota"
    assert "LIFEGATE ENERGY" not in tp.upper().replace("LIFEGATE ENERGY · GAZEL", ""),         "LifeGate fuori perimetro: nessuna fascia"
    # carica KPI: pagina pronta, senza file
    at = _portale("moduli/carica_kpi.py", ruolo="caricatore")
    assert not at.exception and "Carica KPI" in _testo(at)
    print("OK - pagine: cruscotto Gazel (tema, logo, Livello I e Livello II separati), slicer gas, "
          "LifeGate senza dati, panoramica per perimetro, Carica KPI")


def test_obiettivi():
    # semaforo: direzione, soglia facoltativa, pro-rata dei flussi YTD
    assert ko.stato(0.80, 1, 0.75, 0.70) == "ok" and ko.stato(0.72, 1, 0.75, 0.70) == "warn"
    assert ko.stato(0.60, 1, 0.75, 0.70) == "crit" and ko.stato(0.60, 1, 0.75, None) == "crit"
    assert ko.stato(0.03, -1, 0.04, 0.05) == "ok" and ko.stato(0.045, -1, 0.04, 0.05) == "warn"
    assert ko.obiettivo_al_mese(1_200_000, "flusso", 10) == 1_000_000
    assert ko.obiettivo_al_mese(0.04, "rapporto", 10) == 0.04
    # validazione per chi compila la tabella
    err = ko.valida([{"codice": "CHURN", "nome": "Churn PdP", "direzione": -1, "obiettivo": 4.0, "soglia": 3.0},
                     {"codice": "SDD", "nome": "Clienti con SDD", "direzione": 1, "obiettivo": None, "soglia": 50.0},
                     {"codice": "EBITDA", "nome": "EBITDA", "direzione": 1, "obiettivo": 900.0, "soglia": 800.0}])
    assert len(err) == 2 and "sopra l'obiettivo" in err[0] and "manca l'obiettivo" in err[1]
    # solo le righe cambiate; obiettivo svuotato = riga da cancellare
    prima = {"EBITDA": (1, 900_000.0, 800_000.0), "CHURN": (-1, 0.04, None), "SDD": (1, 0.6, None)}
    dopo = {"EBITDA": (1, 900_000.0, 800_000.0), "CHURN": (-1, 0.035, 0.05), "SDD": (1, None, None),
            "LTV": (1, 15.0, None), "CTS": (-1, None, None)}
    scrivere, cancellare = ko.calcola_modifiche(prima, dopo)
    assert scrivere == [("CHURN", -1, 0.035, 0.05), ("LTV", 1, 15.0, None)] and cancellare == ["SDD"]
    # riquadro: semaforo e nota con l'obiettivo (pro-rata sul mese di competenza)
    t = {x.codice: x for x in kc.TESSERE}
    att = {"EBITDA": (300_000.0, "", 2026, 9), "CHURN": (0.036, "", 2026, 10)}
    vm = ui_kpi.modello(t["EBITDA"], att, {}, [], obiettivo=(1, 480_000.0, 300_000.0))
    assert vm["stato"] == "warn" and "a settembre: 360 k€" in " ".join(vm["note"]), vm["note"]
    vm = ui_kpi.modello(t["CHURN"], att, {}, [], obiettivo=(-1, 0.04, None))
    assert vm["stato"] == "ok" and "label_stato" not in vm
    assert ui_kpi.modello(t["CHURN"], att, {}, [], commodity="Gas", obiettivo=(-1, 0.04, None))["stato"] != "ok"
    # pagine: cruscotto con semaforo e tabella di configurazione
    ob = pd.DataFrame([{"societa": "gazel", "anno": 2026, "codice": "SALES_BP", "direzione": 1,
                        "obiettivo": 99.0, "soglia": None, "aggiornato_da": "Daniele",
                        "aggiornato_il": pd.Timestamp("2026-11-24 10:00", tz="UTC")}])
    tg = _testo(_portale("moduli/kpi_gazel.py", obiettivi=ob))
    assert "Critico · 1" in tg and "Obiettivo 2026: ≥" in tg
    at = _portale("moduli/obiettivi_kpi.py", ruolo="caricatore", obiettivi=ob,
                  stato={"ob_societa": "gazel"})
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert "Obiettivi KPI" in _testo(at) and "1 KPI con obiettivo per 2026" in _testo(at)
    print("OK - obiettivi: semaforo con direzione e soglia, pro-rata dei flussi YTD, validazione, "
          "solo righe cambiate, riquadri e pagina di configurazione")


def test_perimetro_e_ruoli_nella_shell():
    at = _portale("moduli/gruppo.py", ruolo="lettore", perimetro=["gazel"])
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    titoli = {m.titolo for m in registro_moduli.moduli_visibili("lettore", ["gazel"])}
    assert titoli == {"Panoramica gruppo", "Livello I", "Livello II"}, titoli
    assert len(re.findall(r"class='mg-k[ ']", _testo(at))) == 4, "solo la fascia Gazel"
    print("OK - shell: il lettore Gazel ha in menu solo panoramica e Gazel")


if __name__ == "__main__":
    test_lettura_dashboard()
    test_competenza_e_righe()
    test_errori_per_chi_carica()
    test_etichetta_vuota_non_ruba()
    test_modello_riquadri()
    test_registro_portale()
    test_pagine_portale()
    test_obiettivi()
    test_perimetro_e_ruoli_nella_shell()
    print("\nTutti i test del portale KPI OK.")
