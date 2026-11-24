"""
Utenti e accessi — solo amministratori.

* Nuovo utente: nome, username, email, profilo (lettore / caricatore /
  amministratore) e società visibili (tutto il gruppo o solo alcune). Alla
  creazione parte l'email con username, società, profilo e il link personale
  per scegliere la password (utenti.py; nessuna password per email).
* Utenti: tabella modificabile (nome, email, profilo, società, attivo) con
  salvataggio delle sole righe cambiate; colonna «Accesso» con lo stato
  dell'invito.
* Nuovo link: reinvia l'invito o fa reimpostare una password dimenticata.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import auth
import branding
import kpi_catalogo as kc
import utenti

io = st.session_state.get("utente_autenticato", "")

st.markdown(branding.testata("Utenti e accessi", "Chi entra nel portale e quali società vede", "",
                             tema="newatt"), unsafe_allow_html=True)
st.markdown(
    "<div class='mg-dom'>Crea un utente, scegli il <b>profilo</b> e le <b>società</b> che può vedere "
    "(per esempio solo Gazel, oppure tutto il gruppo). Alla creazione l'utente riceve un'email con "
    "username, società visibili e un <b>link personale</b> per scegliere la password: vale una sola "
    f"volta, per {utenti.GIORNI_VALIDITA} giorni. Nessuna password viaggia per email.</div>",
    unsafe_allow_html=True)

if not utenti.email_configurata():
    st.warning("L'invio delle email non è ancora configurato (BREVO_LOGIN, BREVO_SMTP_KEY, MAIL_FROM "
               "nei segreti): gli utenti si creano lo stesso e il link di accesso compare qui, da "
               "consegnare a mano.")


def _svuota_cache_auth() -> None:
    for f in (auth.load_credentials, auth._profilo, auth._canonical_username):
        f.clear()


def _esito(chiave: str) -> None:
    """Mostra (una volta) l'esito salvato prima del rerun."""
    es = st.session_state.pop(chiave, None)
    if not es:
        return
    (st.success if es["ok"] else st.warning)(es["msg"])
    if es.get("link"):
        st.code(es["link"], language=None)


try:
    righe = utenti.elenco()
except Exception as e:  # noqa: BLE001
    st.error(f"📡 Impossibile leggere gli utenti dal database: {e}")
    st.stop()
per_username = {r["username"]: r for r in righe}
NOMI_SOCIETA = {s: kc.SOCIETA[s] for s in kc.ORDINE_SOCIETA}
NOMI_BREVI = {"lifegate": "LifeGate", "gazel": "Gazel", "migliora": "Migliora"}   # tabella compatta

# ---------------------------------------------------------------- nuovo utente
with st.container(key="panel_nuovo_utente"):
    st.markdown("<div class='mg-panel-title'>Nuovo utente</div>", unsafe_allow_html=True)
    _esito("ut_esito_nuovo")
    c1, c2, c3 = st.columns(3)
    nome = c1.text_input("Nome e cognome", key="ut_nome", placeholder="Mario Rossi")
    username = c2.text_input("Username", key="ut_username", placeholder="MarioRossi",
                             help="Con questo nome entra nel portale (maiuscole e minuscole indifferenti).")
    email = c3.text_input("Email", key="ut_email", placeholder="mario.rossi@azienda.it")
    c4, c5 = st.columns([1, 2])
    ruolo = c4.selectbox("Profilo", utenti.RUOLI, key="ut_ruolo",
                         format_func=lambda r: utenti.DESCRIZIONE_RUOLO[r].split(" — ")[0],
                         help="\n\n".join(utenti.DESCRIZIONE_RUOLO[r] for r in utenti.RUOLI))
    with c5:
        tutto = st.toggle("Tutto il gruppo", value=True, key="ut_tutto",
                          help="Vede tutte le società, anche quelle che entreranno in futuro.")
        societa = st.multiselect("Società visibili", list(NOMI_SOCIETA), key="ut_societa",
                                 format_func=NOMI_SOCIETA.get, disabled=tutto,
                                 placeholder="Scegli una o più società")
    st.caption(utenti.DESCRIZIONE_RUOLO[ruolo] + " · vede: "
               + (utenti.testo_perimetro([]) if tutto else (utenti.testo_perimetro(societa)
                                                            if societa else "—")))
    if st.button("Crea utente e invia l'email", type="primary", key="ut_crea"):
        errori = utenti.valida_nuovo(username, nome, email, ruolo, tutto, societa, per_username)
        for err in errori:
            st.error(err)
        if not errori:
            perim = [] if tutto else societa
            try:
                token, scade = utenti.crea_utente(username, nome, email, ruolo, perim, io)
            except Exception as e:  # noqa: BLE001
                st.error(f"**Utente non creato**, nessuna modifica salvata: {e}")
            else:
                nuovo = {"username": username.strip(), "nome": nome.strip(), "email": email.strip(),
                         "ruolo": ruolo, "societa": utenti.normalizza_societa(perim)}
                inviata, msg = utenti.manda_invito(token, scade, nuovo)
                st.session_state["ut_esito_nuovo"] = {
                    "ok": inviata, "msg": f"Utente **{nuovo['username']}** creato. {msg}",
                    "link": None if inviata else utenti.link_invito(token)}
                for k in ("ut_nome", "ut_username", "ut_email", "ut_societa", "ut_ruolo", "ut_tutto"):
                    st.session_state.pop(k, None)
                _svuota_cache_auth()
                st.rerun()

# ---------------------------------------------------------------- elenco
with st.container(key="panel_utenti"):
    st.markdown("<div class='mg-panel-title'>Utenti</div>", unsafe_allow_html=True)
    _esito("ut_esito_elenco")
    tabella = pd.DataFrame([{
        "username": r["username"], "Nome": r["nome"], "Email": r["email"], "Profilo": r["ruolo"],
        # «tutto il gruppo» (vuoto in DB) si vede con tutte le società spuntate
        "Società": [s for s in kc.ORDINE_SOCIETA if not r["societa"] or s in r["societa"]],
        "Attivo": bool(r["attivo"]),
        "Accesso": utenti.stato_accesso(bool(r["ha_password"]), r if r.get("scade_il") else None),
    } for r in righe]).set_index("username")
    # colonne strette e l'email per ultima: con lo zoom del browser le colonne
    # che contano (società, attivo, accesso) restano visibili
    modificata = st.data_editor(
        tabella, key="ut_editor", num_rows="fixed", width="stretch", disabled=["Accesso"],
        column_order=["Nome", "Profilo", "Società", "Attivo", "Accesso", "Email"],
        column_config={
            "_index": st.column_config.TextColumn("Username", width=90),
            "Nome": st.column_config.TextColumn("Nome", width=115, required=True),
            "Email": st.column_config.TextColumn("Email", width=200),
            "Profilo": st.column_config.SelectboxColumn(
                "Profilo", options=list(utenti.RUOLI), required=True, width=85,
                help="lettore = consulta · caricatore = carica Excel e obiettivi · admin = tutto"),
            "Società": st.column_config.MultiselectColumn(
                "Società", options=list(NOMI_SOCIETA), format_func=NOMI_BREVI.get, width=185,
                help="Tutte spuntate = tutto il gruppo"),
            "Attivo": st.column_config.CheckboxColumn("Attivo", width=52,
                                                      help="Disattivo = non può più entrare"),
            "Accesso": st.column_config.TextColumn("Accesso", width=150),
        })

    modifiche, errori = [], []
    for username_, r in modificata.iterrows():
        prima = tabella.loc[username_]
        societa_r = list(r["Società"] or [])
        cambiata = (r["Nome"] != prima["Nome"] or r["Email"] != prima["Email"]
                    or r["Profilo"] != prima["Profilo"] or bool(r["Attivo"]) != bool(prima["Attivo"])
                    or sorted(societa_r) != sorted(prima["Società"]))
        if not cambiata:
            continue
        if not str(r["Nome"] or "").strip():
            errori.append(f"{username_}: il nome non può essere vuoto.")
        if r["Email"] and not utenti._RE_EMAIL.match(str(r["Email"]).strip()):
            errori.append(f"{username_}: email non valida.")
        if not societa_r:
            errori.append(f"{username_}: scegli almeno una società.")
        if username_.lower() == io.lower() and (r["Profilo"] != "admin" or not r["Attivo"]):
            errori.append("Non puoi toglierti da solo il profilo di amministratore o disattivarti.")
        modifiche.append({"username": username_, "nome": str(r["Nome"]).strip(),
                          "email": str(r["Email"] or "").strip(), "ruolo": r["Profilo"],
                          "societa": societa_r, "attivo": bool(r["Attivo"])})
    for err in errori:
        st.error(err)
    c_info, c_btn = st.columns([3, 1], vertical_alignment="center")
    c_info.caption(f"{len(righe)} utenti · " + (f"{len(modifiche)} da salvare" if modifiche
                                                 else "nessuna modifica"))
    if c_btn.button("Salva modifiche", type="primary", key="ut_salva", width="stretch",
                    disabled=bool(errori) or not modifiche):
        try:
            utenti.aggiorna_utenti(modifiche)
        except Exception as e:  # noqa: BLE001
            st.error(f"**Salvataggio non riuscito**, nessuna modifica applicata: {e}")
        else:
            _svuota_cache_auth()
            st.session_state["ut_esito_elenco"] = {
                "ok": True, "msg": f"Salvate le modifiche a {len(modifiche)} utenti. Profilo e società "
                                   "valgono dal prossimo accesso dell'utente."}
            st.session_state.pop("ut_editor", None)
            st.rerun()

# ---------------------------------------------------------------- nuovo link
with st.container(key="panel_link"):
    st.markdown("<div class='mg-panel-title'>Nuovo link di accesso</div>", unsafe_allow_html=True)
    st.markdown("<div class='mg-dom' style='margin:0 0 10px'>Per chi non ha ricevuto l'email, ha il link "
                "scaduto o ha dimenticato la password: il nuovo link sostituisce i precedenti.</div>",
                unsafe_allow_html=True)
    _esito("ut_esito_link")
    attivi = [r for r in righe if r["attivo"]]
    if modifiche:
        st.info("Prima salva le modifiche della tabella «Utenti» (per esempio un'email appena "
                "scritta): il link usa i dati salvati.")
    if attivi:
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        scelto = c1.selectbox("Utente", [r["username"] for r in attivi], key="ut_link_utente",
                              format_func=lambda u: f"{per_username[u]['nome'] or u} ({u})"
                                                    + ("" if per_username[u]["email"] else " · senza email"))
        if c2.button("Invia nuovo link", key="ut_link_btn", width="stretch", disabled=bool(modifiche)):
            r = per_username[scelto]
            try:
                token, scade = utenti.nuovo_invito(scelto, io)
            except Exception as e:  # noqa: BLE001
                st.error(f"Link non creato: {e}")
            else:
                if r["email"]:
                    inviata, msg = utenti.manda_invito(token, scade, dict(r),
                                                       reimpostazione=bool(r["ha_password"]))
                else:
                    inviata, msg = False, "L'utente non ha un'email: consegna tu il link qui sotto."
                st.session_state["ut_esito_link"] = {
                    "ok": inviata, "msg": msg, "link": None if inviata else utenti.link_invito(token)}
                st.rerun()
