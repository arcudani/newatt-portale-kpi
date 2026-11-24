"""
AppTest di tutte le viste con dati FITTIZI (nessun DB, nessuna rete):
bp_dati e auth sono simulati. Due versioni: 1 approvata, 2 scenario (-7%).

Esecuzione (da dentro app\\):  .venv\\Scripts\\python.exe test_pagine.py
"""
from __future__ import annotations

from typing import Optional

from streamlit.testing.v1 import AppTest

import auth
import bp_dati
import bp_import as bi
import dati_prova as dp

_BP = bi.leggi_bp(dp.workbook_bp())
CE1, DRV1 = _BP.ce, _BP.driver
CE2 = CE1.assign(importo=CE1["importo"] * 0.93)
DRV2 = DRV1.assign(valore=DRV1["valore"] * 0.95)
CAT = dp.catalogo_seed()
PAGINE = ["moduli/cruscotto.py", "moduli/economico.py", "moduli/commerciale.py",
          "moduli/vas.py", "moduli/operations.py", "moduli/scostamenti.py",
          "moduli/cdv_agenti.py", "moduli/modulo_vas.py", "moduli/fte.py",
          "moduli/consuntivo.py", "moduli/versioni.py", "moduli/catalogo.py"]


def _apptest(pagina: str, ruolo: str = "admin", confronto: int = 0, versioni=None,
             versioni_fn=None, anno: int = 2028, stato: Optional[dict] = None) -> AppTest:
    """`stato` = valori di widget da impostare prima dell'esecuzione (i mock
    valgono solo dentro questa funzione: niente interazioni dopo il ritorno)."""
    import streamlit as st

    st.cache_data.clear()
    vers = dp.versioni_prova() if versioni is None else versioni
    orig_perimetro = auth.perimetro
    auth.perimetro = lambda u: ["lifegate", "gazel", "migliora"]
    orig = (auth.require_login, auth.ruolo, bp_dati.carica_versioni, bp_dati.carica_ce,
            bp_dati.carica_driver, bp_dati.carica_catalogo)
    auth.require_login = lambda: "TestUtente"
    auth.ruolo = lambda u: ruolo
    bp_dati.carica_versioni = versioni_fn or (lambda: vers)
    bp_dati.carica_ce = lambda vid: CE1 if int(vid) == 1 else CE2
    bp_dati.carica_driver = lambda vid: DRV1 if int(vid) == 1 else DRV2
    bp_dati.carica_catalogo = lambda: CAT
    try:
        at = AppTest.from_file("app.py", default_timeout=120)
        at.session_state["authentication_status"] = True
        at.session_state["utente_autenticato"] = "TestUtente"
        at.session_state["ruolo"] = ruolo
        at.session_state["f_versione"] = 1
        at.session_state["f_confronto"] = confronto
        at.session_state["f_anno"] = anno
        for chiave, valore in (stato or {}).items():
            at.session_state[chiave] = valore
        # Primo run: st.navigation registra le pagine. switch_page risolve il
        # file sull'elenco registrato, e senza questo giro le viste il cui
        # url_path differisce dal nome del file (cdv-agenti, modulo-vas)
        # ricadevano silenziosamente sulla pagina di atterraggio.
        at.run()
        at.switch_page(pagina)
        at.run()
        return at
    finally:
        (auth.require_login, auth.ruolo, bp_dati.carica_versioni, bp_dati.carica_ce,
         bp_dati.carica_driver, bp_dati.carica_catalogo) = orig
        auth.perimetro = orig_perimetro


def _testo(at: AppTest) -> str:
    return " ".join(str(m.value) for m in at.markdown) + " " + " ".join(
        str(c.value) for c in at.caption)


def _senza_eccezioni(at: AppTest, cosa: str) -> None:
    assert not at.exception, f"{cosa}: {[str(e.value)[:300] for e in at.exception]}"


def test_tutte_le_viste_admin():
    for confronto in (0, 2):
        for pagina in PAGINE:
            _senza_eccezioni(_apptest(pagina, "admin", confronto), f"{pagina} conf={confronto}")
    print(f"OK - {len(PAGINE)} viste x 2 scenari (admin): nessuna eccezione")



def test_tessere_dal_catalogo():
    """Ambiti, benchmark e segnaposto arrivano dal catalogo, non dal codice."""
    t = _testo(_apptest("moduli/operations.py"))
    assert "COSTO DEL SERVIZIO" in t.upper(), "fascia per ambito dal catalogo"
    assert "benchmark" in t.lower(), "avviso/insight dal benchmark del catalogo"
    assert "mg-amb-title" in t and "FTE" in t
    print("OK - tessere generate dal catalogo: ambiti, benchmark")


# vista -> file: ogni vista che ha KPI segnaposto nel catalogo DEVE mostrarli
VISTE_CON_SEGNAPOSTO = {"V1": "moduli/cruscotto.py",
                        "V4": "moduli/vas.py", "V5": "moduli/operations.py",
                        "V7": "moduli/cdv_agenti.py", "V9": "moduli/fte.py"}


def test_segnaposto_ded_sempre_visibili():
    """I segnaposto DeD sono la promessa «la struttura non cambia in fase 2»:
    se una vista li perde nel ridisegno, la struttura si è già rotta."""
    attesi = {v for v in CAT[CAT["stato"] == "segnaposto"]["vista"]} & set(VISTE_CON_SEGNAPOSTO)
    assert attesi, "il catalogo di prova non ha segnaposto: test inutile"
    for vista in sorted(attesi):
        pagina = VISTE_CON_SEGNAPOSTO[vista]
        t = _testo(_apptest(pagina))
        quanti = len(CAT[(CAT["vista"] == vista) & (CAT["stato"] == "segnaposto")])
        assert "in attesa dati" in t.lower(), f"{pagina}: persi i {quanti} segnaposto di {vista}"
    print(f"OK - segnaposto DeD presenti in tutte le viste che li hanno "
          f"({', '.join(sorted(attesi))})")


def test_avviamento_2026():
    """Anno di avviamento (tutto a zero): nessuna vista deve rompersi."""
    for confronto in (0, 2):
        for pagina in PAGINE:
            _senza_eccezioni(_apptest(pagina, "admin", confronto, anno=2026),
                             f"{pagina} 2026 conf={confronto}")
    t = _testo(_apptest("moduli/cruscotto.py", anno=2026))
    assert "avviamento" in t, "rapporti n.d. con motivo nel 2026"
    print("OK - anno 2026 (avviamento): nessuna eccezione, rapporti n.d. — avviamento")


def test_cruscotto_con_confronto():
    import re
    at = _apptest("moduli/cruscotto.py", "admin", 2)
    t = _testo(at)
    assert len(re.findall(r"class='mg-k[ ']", t)) == 9, "il Cruscotto ha 9 riquadri"
    assert "mg-delta" in t, "con il confronto i riquadri mostrano il Δ"
    assert "Rif. <b>Scenario prova:" in t, "con il confronto il Rif. è la versione B"
    assert "mg-amb-title" in t, "riquadri raggruppati per ambito (fasce dell'handoff)"
    for ambito in ("Economico-finanziario", "Commerciale", "Cliente e servizio"):
        assert ambito.upper() in t.upper(), f"fascia {ambito}"
    assert "obiettivo BP" in t and "contratti" in t, "sales plan: obiettivo del BP nel Rif."
    assert t.count("In attesa dati") >= 5, "PFN, insoluto, NPS, CLT e sales plan in attesa dati"
    # sales plan, churn e CLT: dettaglio per commodity con lampadina (EE) e fiamma (gas)
    assert t.count("class='mg-split'") == 3, "dettaglio per commodity su sales plan, churn e CLT"
    assert t.count("fill='#f5c400'") == 3 and t.count("fill='#97c7ec'") == 3, \
        "un'icona per commodity in ognuno dei 3 dettagli"
    assert " POD</b>" in t and " PDR</b>" in t, "obiettivi di attivazione per commodity"
    assert "Cruscotto KPI · DeD" in t and "Tutto cambia, tu decidi." in t, "testata e claim"
    assert t.count("class='mg-amb-ico'") == 3, "un'icona per ambito nella colonna della fascia"
    assert "Consuntivo <b>non caricato" in t, "badge stato dati"
    assert "Scenario prova" in t
    print("OK - Cruscotto: 9 riquadri in 3 fasce (sales plan, churn e CLT con dettaglio per "
          "commodity e icone), Rif. dal confronto, testata con claim, badge stato dati")


def test_cruscotto_stati_e_filtri():
    """Stati dell'handoff: il semaforo solo contro un riferimento reale;
    contatori per stato; slicer Commodity che ripartisce i KPI con dettaglio."""
    import re
    t = _testo(_apptest("moduli/cruscotto.py"))
    stati = re.findall(r"class='mg-st (\w+)'", t)
    # ordine del catalogo: EBITDA, PFN, Insoluto | Sales plan, Churn | NPS, Costo
    # per cliente, Cost-to-Serve, CLT
    assert len(stati) == 9
    assert stati[0] == "bp" and stati[6] == "bp", \
        "EBITDA e costo per cliente senza riferimento: «Valore BP», non «In target»"
    assert stati[4] == "bp" and "Ipotesi BP" in t, "churn: ipotesi del BP"
    assert stati[7] in ("ok", "warn", "crit"), "Cost-to-Serve: semaforo dal benchmark del catalogo"
    assert "Rif. <b>benchmark 10–15 €" in t
    assert stati.count("pend") == 5, "PFN, insoluto, sales plan, NPS, CLT in attesa"
    conta = dict(re.findall(r"class='c (\w+)'><i></i>[^·]+· (\d+)", t))
    assert conta == {s: str(stati.count(s)) for s in ("ok", "warn", "crit", "bp", "pend")
                     if stati.count(s)}, conta   # solo gli stati presenti
    # slicer Commodity = Gas: il churn diventa quello del gas, gli altri KPI lo dicono
    at = _apptest("moduli/cruscotto.py", stato={"f_commodity": "Gas naturale"})
    _senza_eccezioni(at, "slicer commodity")
    assert at.selectbox(key="f_commodity").value == "Gas naturale"
    tg = _testo(at)
    assert "Solo gas naturale" in tg and "non ripartito per commodity" in tg
    assert tg.count("class='mg-split-r'") == 3, "una sola riga di dettaglio (gas) per KPI"
    print("OK - Cruscotto: semaforo solo con riferimento, contatori per stato, slicer Commodity")



def test_versioni_per_ruolo():
    t_admin = _testo(_apptest("moduli/versioni.py", "admin"))
    assert "Stato della versione" in t_admin and "Importa un BP Excel" in t_admin
    print("OK - Versioni: approvazione e import per l'admin (il BP Migliora nel portale è "
          "riservato agli admin: vedi test_kpi.test_registro_portale)")


def test_rilievi_del_bp_segnalati():
    assert "Rinnovi positivi" in _testo(_apptest("moduli/commerciale.py"))
    assert "canale di vendita autonomo" in _testo(_apptest("moduli/vas.py"))
    assert "Doppio conteggio" in _testo(_apptest("moduli/fte.py"))
    print("OK - rilievi del BP in evidenza (rinnovi positivi, VAS autonomo, doppio conteggio FTE)")


def test_db_non_raggiungibile():
    def giu():
        raise RuntimeError("pooler non raggiungibile")
    at = _apptest("moduli/cruscotto.py", versioni_fn=giu)
    _senza_eccezioni(at, "DB giù")
    assert any("Impossibile leggere" in str(e.value) for e in at.error)
    print("OK - DB non raggiungibile: messaggio + Riprova, nessuna eccezione")


if __name__ == "__main__":
    test_tutte_le_viste_admin()
    test_tessere_dal_catalogo()
    test_segnaposto_ded_sempre_visibili()
    test_avviamento_2026()
    test_cruscotto_con_confronto()
    test_cruscotto_stati_e_filtri()
    test_versioni_per_ruolo()
    test_rilievi_del_bp_segnalati()
    test_db_non_raggiungibile()
    print("\nTutti i test pagine OK.")
