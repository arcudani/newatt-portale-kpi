"""
Smoke test della shell (headless, streamlit.testing.v1.AppTest).

Come negli altri repo Bros: script con runner __main__, righe "OK - ...".
Va seminato session_state (authentication_status + utente + ruolo) o la
shell cicla sul login. Il gate di login reale richiede SUPABASE_DB_URL e
si salta se manca.

Esecuzione (da dentro app\\):  .venv\\Scripts\\python.exe test_shell_smoke.py
"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

import auth
import bp_dati
import config
import dati_prova as dp
import registro_moduli


def test_registro():
    codici = set(registro_moduli.PER_CODICE)
    portale = {"G0", "LG", "LG2", "GZ", "GZ2", "MG", "MG2", "UP", "OB"}
    assert {f"V{i}" for i in range(1, 12)} | {"CAT"} | portale == codici
    assert registro_moduli.url_di(registro_moduli.PER_CODICE["G0"]) == "/"
    assert sum(m.default for m in registro_moduli.MODULI) == 1
    assert all(m.url_path for m in registro_moduli.MODULI if not m.default)
    # etichetta WIP sulle viste del BP Migliora, non sul portale
    css = registro_moduli.css_wip()
    wip = {m.codice for m in registro_moduli.MODULI if m.wip}
    assert wip == codici - portale
    in_arrivo = {m.codice for m in registro_moduli.MODULI if not m.attivo}   # hanno già «· in arrivo»
    assert all(f'a[href$="/{registro_moduli.PER_CODICE[c].url_path}"]::after' in css for c in wip - in_arrivo)
    assert not any(f'a[href$="/{registro_moduli.PER_CODICE[c].url_path}"]::after' in css for c in in_arrivo)
    print("OK - registro: portale (panoramica di atterraggio, 3 società, carica) + BP Migliora "
          "V1..V11 e Catalogo con WIP")


def test_shell_login_simulato():
    import bp_import as bi
    bp = bi.leggi_bp(dp.workbook_bp())
    orig = (auth.require_login, auth.ruolo, bp_dati.carica_versioni, bp_dati.carica_ce,
            bp_dati.carica_driver, bp_dati.carica_catalogo)
    import kpi_dati
    orig_kpi = (auth.perimetro, kpi_dati.carica_valori, kpi_dati.carica_caricamenti)
    auth.require_login = lambda: "TestAdmin"
    auth.ruolo = lambda u: "admin"
    auth.perimetro = lambda u: ["lifegate", "gazel", "migliora"]
    kpi_dati.carica_valori = lambda s: dp.valori_kpi_df(s)
    kpi_dati.carica_caricamenti = lambda s=None: dp.caricamenti_prova()
    bp_dati.carica_versioni = dp.versioni_prova
    bp_dati.carica_ce = lambda vid: bp.ce
    bp_dati.carica_driver = lambda vid: bp.driver
    bp_dati.carica_catalogo = dp.catalogo_seed
    try:
        at = AppTest.from_file("app.py", default_timeout=60)
        at.session_state["authentication_status"] = True
        at.session_state["utente_autenticato"] = "TestAdmin"
        at.run()
        assert not at.exception, [str(e.value) for e in at.exception]
        # atterraggio sulla panoramica di gruppo (testata NeWatt)
        assert any("Portale KPI · Gruppo NeWatt" in str(m.value) for m in at.markdown)
        assert at.session_state["ruolo"] == "admin"
        assert at.session_state["perimetro"] == ["lifegate", "gazel", "migliora"]
    finally:
        (auth.require_login, auth.ruolo, bp_dati.carica_versioni, bp_dati.carica_ce,
         bp_dati.carica_driver, bp_dati.carica_catalogo) = orig
        (auth.perimetro, kpi_dati.carica_valori, kpi_dati.carica_caricamenti) = orig_kpi
    print("OK - shell con login simulato: atterraggio sulla panoramica NeWatt, 0 eccezioni")


def test_gate_login_reale():
    if not config.newatt_db_url():
        print("SKIP - gate login reale (NEWATT_DB_URL non configurata)")
        return
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    testo = " ".join(str(m.value) for m in at.markdown)
    assert "Portale KPI del gruppo" in testo, "schermata di login NeWatt"
    assert "Portale KPI · Gruppo NeWatt" not in testo and "class='mg-k" not in testo, \
        "senza login nessuna vista deve essere renderizzata"
    print("OK - gate login reale: si ferma al login, 0 eccezioni, DB raggiungibile")


if __name__ == "__main__":
    test_registro()
    test_shell_login_simulato()
    test_gate_login_reale()
    print("\nSmoke test shell: TUTTO OK")
