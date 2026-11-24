"""
Test della gestione utenti del Portale KPI NeWatt (nessun DB, nessuna email
vera): validazioni, perimetro di società, token e testo dell'invito, pagina
«Utenti e accessi» (creazione con invio email) e pagina pubblica del link.

Esecuzione (da dentro app\\):  .venv\\Scripts\\python.exe test_utenti.py
"""
from __future__ import annotations

import datetime as dt

from streamlit.testing.v1 import AppTest

import auth
import config
import utenti

UTC = dt.timezone.utc
SCADE = dt.datetime(2026, 12, 1, 10, 0, tzinfo=UTC)


def test_validazioni_e_perimetro():
    ok = utenti.valida_nuovo("MarioRossi", "Mario Rossi", "mario@gazel.it", "lettore", False,
                             ["gazel"], ["Daniele"])
    assert ok == []
    err = utenti.valida_nuovo("mario rossi", "", "mario@", "boh", False, [], [])
    assert len(err) == 5, err
    assert "esiste già" in utenti.valida_nuovo("daniele", "D", "d@x.it", "admin", True, [], ["Daniele"])[0]
    # perimetro: tutte le società = vuoto in DB (tutto il gruppo, anche future)
    assert utenti.normalizza_societa(["migliora", "gazel", "lifegate"]) == []
    assert utenti.normalizza_societa(["migliora", "gazel"]) == ["gazel", "migliora"]
    assert utenti.testo_perimetro(["gazel"]) == "Gazel"
    assert utenti.testo_perimetro([]).startswith("Tutto il gruppo")
    # password
    assert utenti.valida_password("abc", "abc")[0].startswith("La password deve avere")
    assert "lettera e un numero" in utenti.valida_password("soloLettereQui", "soloLettereQui")[0]
    assert "username" in utenti.valida_password("mario12345x", "mario12345x", "Mario")[0]
    assert utenti.valida_password("Primavera2026", "Primavera2027") == ["Le due password non coincidono."]
    assert utenti.valida_password("Primavera2026", "Primavera2026") == []
    print("OK - validazioni utente e password, perimetro (tutte = tutto il gruppo)")


def test_token_ed_email():
    t1, h1 = utenti.nuovo_token()
    t2, _ = utenti.nuovo_token()
    assert t1 != t2 and len(t1) >= 40 and h1 == utenti.hash_token(t1) and t1 not in h1
    link = utenti.link_invito(t1, "https://portale.example/")
    assert link == f"https://portale.example/?invito={t1}"
    oggetto, testo, html = utenti.email_invito("Mario Rossi", "MarioRossi", "lettore", ["gazel"],
                                               link, SCADE, "https://portale.example")
    assert "il tuo accesso" in oggetto
    for x in ("Ciao Mario", "Username: MarioRossi", "Società visibili: Gazel", "Lettore", link,
              "01/12/2026", "https://portale.example"):
        assert x in testo, x
    assert "password" in testo.lower() and "Primavera" not in testo   # nessuna password nell'email
    assert link in html and "Scegli la password" in html
    assert "reimposta" in utenti.email_invito("M", "M", "admin", [], link, SCADE, "u", True)[0]
    # stato dell'accesso
    adesso = dt.datetime(2026, 11, 25, tzinfo=UTC)
    aperto = {"scade_il": SCADE, "usato_il": None, "annullato": False, "email_inviata": True}
    assert utenti.stato_accesso(False, aperto, adesso).startswith("Invito aperto fino al 01/12")
    assert utenti.stato_accesso(False, {**aperto, "scade_il": adesso - dt.timedelta(days=1)},
                                adesso) == "Invito scaduto: reinvialo"
    assert utenti.stato_accesso(True, None, adesso) == "Password impostata"
    print("OK - token monouso (solo hash in DB), email con username/società/link e senza password, "
          "stato dell'invito")


def _righe():
    return [{"username": "Daniele", "nome": "Daniele Arculeo", "email": "", "ruolo": "admin",
             "societa": [], "attivo": True, "ha_password": True, "created_at": None,
             "scade_il": None, "usato_il": None, "annullato": None, "email_inviata": None,
             "invito_il": None},
            {"username": "Lucia", "nome": "Lucia Bianchi", "email": "lucia@gazel.it", "ruolo": "lettore",
             "societa": ["gazel"], "attivo": True, "ha_password": False, "created_at": None,
             "scade_il": SCADE, "usato_il": None, "annullato": False, "email_inviata": True,
             "invito_il": None}]


def _pagina_utenti(ruolo: str = "admin", azioni=None):
    """Pagina «Utenti e accessi» con DB e SMTP finti; azioni(at) prima dell'ultimo run."""
    import streamlit as st
    st.cache_data.clear()
    creati, inviati = [], []
    orig = (auth.require_login, auth.ruolo, auth.perimetro, utenti.elenco, utenti.crea_utente,
            utenti.invia_email, utenti.segna_email_inviata, config.mail_from, config.smtp_login,
            config.smtp_key)
    auth.require_login = lambda: "Daniele"
    auth.ruolo = lambda u: ruolo
    auth.perimetro = lambda u: ["lifegate", "gazel", "migliora"]
    utenti.elenco = _righe
    utenti.crea_utente = lambda *a: (creati.append(a), ("tok123", SCADE))[1]
    utenti.invia_email = lambda *a: inviati.append(a)
    utenti.segna_email_inviata = lambda t: None
    config.mail_from = lambda: "Portale KPI <analisi@example.it>"
    config.smtp_login = lambda: "x"
    config.smtp_key = lambda: "y"
    try:
        at = AppTest.from_file("app.py", default_timeout=120)
        at.session_state["authentication_status"] = True
        at.session_state["utente_autenticato"] = "Daniele"
        at.run()
        if ruolo != "admin":
            return at, creati, inviati
        at.switch_page("moduli/utenti_accessi.py")
        at.run()
        if azioni:
            azioni(at)
            at.run()
        return at, creati, inviati
    finally:
        (auth.require_login, auth.ruolo, auth.perimetro, utenti.elenco, utenti.crea_utente,
         utenti.invia_email, utenti.segna_email_inviata, config.mail_from, config.smtp_login,
         config.smtp_key) = orig


def test_pagina_utenti():
    at, _, _ = _pagina_utenti()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    testo = " ".join(str(m.value) for m in at.markdown)
    assert "Utenti e accessi" in testo and "Nuovo utente" in testo and "Nuovo link di accesso" in testo

    def crea(at):
        at.text_input(key="ut_nome").set_value("Mario Rossi")
        at.text_input(key="ut_username").set_value("MarioRossi")
        at.text_input(key="ut_email").set_value("mario@gazel.it")
        at.toggle(key="ut_tutto").set_value(False)
        at.run()
        at.multiselect(key="ut_societa").set_value(["gazel"])
        at.run()
        at.button(key="ut_crea").click()

    at, creati, inviati = _pagina_utenti(azioni=crea)
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert creati and creati[0][:5] == ("MarioRossi", "Mario Rossi", "mario@gazel.it", "lettore", ["gazel"])
    assert inviati and inviati[0][0] == "mario@gazel.it" and "?invito=tok123" in inviati[0][2]
    assert "Società visibili: Gazel" in inviati[0][2]
    assert any("creato" in str(s.value) and "Email inviata" in str(s.value) for s in at.success)

    # solo gli amministratori vedono la pagina
    import registro_moduli
    for r, vede in (("admin", True), ("caricatore", False), ("lettore", False)):
        assert ("US" in {m.codice for m in registro_moduli.moduli_visibili(r, ["gazel"])}) is vede
    print("OK - pagina Utenti e accessi: creazione con perimetro Gazel e invio dell'email con il link")


def test_link_invito():
    orig = (utenti.invito_valido, utenti.usa_invito, auth.load_credentials)
    usati = []
    utenti.invito_valido = lambda t: ({"username": "MarioRossi", "nome": "Mario Rossi", "scade_il": SCADE}
                                      if t == "buono" else None)
    utenti.usa_invito = lambda t, p: (usati.append((t, p)), "MarioRossi")[1]
    try:
        at = AppTest.from_file("app.py", default_timeout=120)
        at.query_params["invito"] = "scaduto"
        at.run()
        assert not at.exception and "Link non più valido" in " ".join(str(m.value) for m in at.markdown)
        at = AppTest.from_file("app.py", default_timeout=120)
        at.query_params["invito"] = "buono"
        at.run()
        assert "scegli la tua password" in " ".join(str(m.value) for m in at.markdown)
        at.text_input(key="invito_p1").set_value("corta")
        at.text_input(key="invito_p2").set_value("corta")
        at.button[0].click()
        at.run()
        assert at.error and not usati
        at.text_input(key="invito_p1").set_value("Primavera2026")
        at.text_input(key="invito_p2").set_value("Primavera2026")
        at.button[0].click()
        at.run()
        assert usati == [("buono", "Primavera2026")], usati
        assert any("Password impostata" in str(s.value) for s in at.success)
    finally:
        utenti.invito_valido, utenti.usa_invito, auth.load_credentials = orig
    print("OK - link di invito: scaduto = messaggio, password debole rifiutata, password impostata")


if __name__ == "__main__":
    test_validazioni_e_perimetro()
    test_token_ed_email()
    test_pagina_utenti()
    test_link_invito()
    print("\nTutti i test utenti OK")
