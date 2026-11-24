"""
Utenti del Portale KPI NeWatt: creazione, profilo (ruolo + società visibili),
inviti di accesso via email.

Flusso: l'amministratore crea l'utente (pagina «Utenti e accessi») → l'utente
nasce SENZA password → riceve un'email con il suo username, le società che
vede e un link personale (…/?invito=<token>, monouso, 7 giorni) dove sceglie
la password. Nessuna password viaggia per email; nel DB c'è solo lo SHA-256
del token (tabella kpi_inviti, migrazione kpi004). Lo stesso link serve per
reimpostare una password dimenticata («Reinvia invito»).

Funzioni pure (validazioni, token, testo dell'email) testate offline in
test_utenti.py; IO su DB e SMTP qui sotto, mockati nei test.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import secrets
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from html import escape
from typing import Optional
from zoneinfo import ZoneInfo

import bcrypt

import config
import db
import kpi_catalogo as kc

BASE = "newatt"
RUOLI = ("lettore", "caricatore", "admin")
DESCRIZIONE_RUOLO = {
    "lettore": "Lettore — consulta i cruscotti delle società assegnate",
    "caricatore": "Caricatore — carica l'Excel mensile e imposta gli obiettivi",
    "admin": "Amministratore — tutto, compresi utenti e BP Migliora",
}
GIORNI_VALIDITA = 7
ROMA = ZoneInfo("Europe/Rome")
PWD_MIN = 10
_RE_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,29}$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class MailNonConfigurata(RuntimeError):
    """Mancano credenziali SMTP o mittente: l'invito si consegna a mano."""


# =============================================================================
# Funzioni pure
# =============================================================================

def testo_perimetro(societa) -> str:
    """Società visibili in parole (vuoto = tutto il gruppo)."""
    scelte = [s for s in kc.ORDINE_SOCIETA if s in (societa or [])]
    if not scelte or len(scelte) == len(kc.ORDINE_SOCIETA):
        return "Tutto il gruppo (" + ", ".join(kc.SOCIETA[s] for s in kc.ORDINE_SOCIETA) + ")"
    return ", ".join(kc.SOCIETA[s] for s in scelte)


def normalizza_societa(societa) -> list[str]:
    """Perimetro da salvare: [] se sono tutte (così una società futura entra
    da sola nel «tutto il gruppo»), altrimenti nell'ordine del portale."""
    scelte = [s for s in kc.ORDINE_SOCIETA if s in (societa or [])]
    return [] if len(scelte) == len(kc.ORDINE_SOCIETA) else scelte


def valida_nuovo(username: str, nome: str, email: str, ruolo: str, tutto_gruppo: bool,
                 societa, esistenti) -> list[str]:
    """Errori (in italiano, per chi compila il modulo) sul nuovo utente."""
    err = []
    u = (username or "").strip()
    if not _RE_USERNAME.match(u):
        err.append("Username: da 3 a 30 caratteri, inizia con una lettera; ammessi lettere, "
                   "numeri, punto, trattino e trattino basso (niente spazi).")
    elif u.lower() in {e.lower() for e in esistenti}:
        err.append(f"Lo username «{u}» esiste già.")
    if not (nome or "").strip():
        err.append("Scrivi nome e cognome.")
    if not _RE_EMAIL.match((email or "").strip()):
        err.append("Email non valida: serve per mandare il link di accesso.")
    if ruolo not in RUOLI:
        err.append("Scegli un ruolo.")
    if not tutto_gruppo and not [s for s in (societa or []) if s in kc.SOCIETA]:
        err.append("Scegli almeno una società (o «Tutto il gruppo»).")
    return err


def valida_password(pwd: str, conferma: str, username: str = "") -> list[str]:
    err = []
    if len(pwd or "") < PWD_MIN:
        err.append(f"La password deve avere almeno {PWD_MIN} caratteri.")
    elif not (re.search(r"[A-Za-z]", pwd) and re.search(r"[0-9]", pwd)):
        err.append("La password deve contenere almeno una lettera e un numero.")
    elif username and username.lower() in pwd.lower():
        err.append("La password non può contenere lo username.")
    if pwd != conferma:
        err.append("Le due password non coincidono.")
    return err


def nuovo_token() -> tuple[str, str]:
    """(token da mettere nel link, sha256 da salvare nel DB)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


def link_invito(token: str, base_url: Optional[str] = None) -> str:
    return f"{(base_url or config.portale_url()).rstrip('/')}/?invito={token}"


def email_invito(nome: str, username: str, ruolo: str, societa, link: str, scade: dt.datetime,
                 url_portale: str, reimpostazione: bool = False) -> tuple[str, str, str]:
    """(oggetto, testo semplice, html) dell'email di invito."""
    perim = testo_perimetro(societa)
    quando = scade.astimezone(ROMA) if scade.tzinfo else scade
    scadenza = f"{quando:%d/%m/%Y}"
    ruolo_t = DESCRIZIONE_RUOLO.get(ruolo, ruolo).split(" — ")[0]
    if reimpostazione:
        oggetto = "Portale KPI NeWatt — reimposta la tua password"
        apertura = "è stato richiesto un nuovo link per impostare la password del Portale KPI del gruppo NeWatt."
        azione = "Imposta la nuova password"
    else:
        oggetto = "Portale KPI NeWatt — il tuo accesso"
        apertura = "è stato creato il tuo accesso al Portale KPI del gruppo NeWatt."
        azione = "Scegli la password e accedi"
    saluto = f"Ciao {nome.split()[0] if nome.strip() else username},"
    testo = (
        f"{saluto}\n\n{apertura}\n\n"
        f"Username: {username}\nSocietà visibili: {perim}\nProfilo: {ruolo_t}\n\n"
        f"1. Apri questo link personale e scegli la tua password (almeno {PWD_MIN} caratteri, "
        f"lettere e numeri):\n{link}\n\n"
        f"Il link vale una sola volta ed è valido fino al {scadenza}.\n\n"
        f"2. Poi accedi al portale con username e password:\n{url_portale}\n\n"
        "Il link è personale: non inoltrarlo. Se non aspettavi questa email, ignorala.\n\n"
        "Portale KPI · Gruppo NeWatt\n")
    riga = ("<tr><td style='padding:4px 16px 4px 0;color:#656B82;font-size:13px'>{}</td>"
            "<td style='padding:4px 0;color:#14162B;font-size:14px;font-weight:600'>{}</td></tr>")
    html = f"""<!doctype html><html><body style="margin:0;background:#F4F6FB;font-family:Segoe UI,Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F4F6FB;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #E2E5EE;border-radius:18px;overflow:hidden">
<tr><td style="background:#0000FF;color:#ffffff;padding:20px 28px;font-size:20px;font-weight:700">Portale KPI · Gruppo NeWatt</td></tr>
<tr><td style="padding:26px 28px 8px;color:#14162B;font-size:15px;line-height:22px">
<p style="margin:0 0 12px">{escape(saluto)}</p>
<p style="margin:0 0 18px">{escape(apertura)}</p>
<table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 22px">
{riga.format("Username", escape(username))}
{riga.format("Società visibili", escape(perim))}
{riga.format("Profilo", escape(ruolo_t))}
</table>
<p style="margin:0 0 22px"><a href="{escape(link, quote=True)}" style="display:inline-block;background:#0000FF;color:#ffffff;text-decoration:none;font-weight:700;padding:12px 26px;border-radius:999px">{escape(azione)}</a></p>
<p style="margin:0 0 8px;font-size:13px;color:#434861">Il link è personale, vale una sola volta ed è valido fino al <b>{escape(scadenza)}</b>. La password deve avere almeno {PWD_MIN} caratteri, con lettere e numeri.</p>
<p style="margin:0 0 8px;font-size:13px;color:#434861">Dopo, entri sempre da <a href="{escape(url_portale, quote=True)}" style="color:#0000D6">{escape(url_portale)}</a> con username e password.</p>
<p style="margin:16px 0 22px;font-size:12px;color:#656B82">Se il pulsante non funziona copia questo indirizzo nel browser:<br><span style="word-break:break-all">{escape(link)}</span><br><br>Non inoltrare questa email. Se non la aspettavi, ignorala.</p>
</td></tr></table></td></tr></table></body></html>"""
    return oggetto, testo, html


def stato_accesso(ha_password: bool, invito: Optional[dict], adesso: Optional[dt.datetime] = None) -> str:
    """Testo della colonna «Accesso» per un utente."""
    adesso = adesso or dt.datetime.now(dt.timezone.utc)
    if invito and not invito.get("usato_il") and not invito.get("annullato"):
        scade = invito["scade_il"]
        if scade > adesso:
            inviata = "email inviata" if invito.get("email_inviata") else "link da consegnare"
            return f"Invito aperto fino al {scade.astimezone(ROMA):%d/%m} · {inviata}"
        if not ha_password:
            return "Invito scaduto: reinvialo"
    return "Password impostata" if ha_password else "Senza password: invia un invito"


# =============================================================================
# IO: database
# =============================================================================

def elenco() -> list[dict]:
    """Utenti con l'ultimo invito (dict per riga)."""
    return db.query_dict(
        "SELECT u.username, u.nome, u.email, u.ruolo, u.societa, u.attivo, "
        "u.password_hash IS NOT NULL AS ha_password, u.created_at, "
        "i.scade_il, i.usato_il, i.annullato, i.email_inviata, i.creato_il AS invito_il "
        "FROM public.kpi_utenti u LEFT JOIN LATERAL ("
        "  SELECT * FROM public.kpi_inviti x WHERE x.username = u.username "
        "  ORDER BY x.creato_il DESC LIMIT 1) i ON true "
        "ORDER BY u.created_at, u.username", base=BASE)


def _inserisci_invito(conn, username: str, creato_da: str) -> tuple[str, dt.datetime]:
    """Annulla gli inviti aperti dell'utente e ne crea uno nuovo."""
    token, h = nuovo_token()
    scade = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=GIORNI_VALIDITA)
    conn.execute("UPDATE public.kpi_inviti SET annullato = true "
                 "WHERE username = %s AND usato_il IS NULL AND NOT annullato", (username,))
    conn.execute("INSERT INTO public.kpi_inviti (username, token_hash, creato_da, scade_il) "
                 "VALUES (%s, %s, %s, %s)", (username, h, creato_da, scade))
    return token, scade


def crea_utente(username: str, nome: str, email: str, ruolo: str, societa, creato_da: str
                ) -> tuple[str, dt.datetime]:
    """Crea l'utente (senza password) e il suo invito, in una transazione.
    Ritorna (token, scadenza)."""
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            conn.execute(
                "INSERT INTO public.kpi_utenti (username, nome, email, ruolo, societa, attivo) "
                "VALUES (%s, %s, %s, %s, %s, true)",
                (username.strip(), nome.strip(), email.strip(), ruolo, normalizza_societa(societa)))
            return _inserisci_invito(conn, username.strip(), creato_da)


def nuovo_invito(username: str, creato_da: str) -> tuple[str, dt.datetime]:
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            return _inserisci_invito(conn, username, creato_da)


def segna_email_inviata(token: str) -> None:
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            conn.execute("UPDATE public.kpi_inviti SET email_inviata = true WHERE token_hash = %s",
                         (hash_token(token),))


def aggiorna_utenti(modifiche: list[dict]) -> None:
    """modifiche = [{username, nome, email, ruolo, societa, attivo}], una transazione."""
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            for m in modifiche:
                conn.execute(
                    "UPDATE public.kpi_utenti SET nome = %s, email = %s, ruolo = %s, societa = %s, "
                    "attivo = %s WHERE username = %s",
                    (m["nome"], m["email"], m["ruolo"], normalizza_societa(m["societa"]),
                     bool(m["attivo"]), m["username"]))


def invito_valido(token: str) -> Optional[dict]:
    """{username, nome, scade_il} se il token è aperto, non scaduto, di un
    utente attivo; None altrimenti."""
    if not token or len(token) > 200:
        return None
    righe = db.query_dict(
        "SELECT i.username, u.nome, i.scade_il FROM public.kpi_inviti i "
        "JOIN public.kpi_utenti u ON u.username = i.username "
        "WHERE i.token_hash = %s AND i.usato_il IS NULL AND NOT i.annullato "
        "AND i.scade_il > now() AND u.attivo", (hash_token(token),), base=BASE)
    return righe[0] if righe else None


def usa_invito(token: str, password: str) -> Optional[str]:
    """Imposta la password e chiude l'invito (ricontrolla il token nella
    stessa transazione). Ritorna lo username o None se il link non vale più."""
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with db.connect(base=BASE) as conn:
        with conn.transaction():
            riga = conn.execute(
                "SELECT i.id, i.username FROM public.kpi_inviti i "
                "JOIN public.kpi_utenti u ON u.username = i.username "
                "WHERE i.token_hash = %s AND i.usato_il IS NULL AND NOT i.annullato "
                "AND i.scade_il > now() AND u.attivo FOR UPDATE OF i",
                (hash_token(token),)).fetchone()
            if not riga:
                return None
            conn.execute("UPDATE public.kpi_utenti SET password_hash = %s WHERE username = %s",
                         (h, riga["username"]))
            conn.execute("UPDATE public.kpi_inviti SET usato_il = now() WHERE id = %s", (riga["id"],))
            return riga["username"]


# =============================================================================
# IO: email
# =============================================================================

def email_configurata() -> bool:
    return bool(config.smtp_login() and config.smtp_key() and config.mail_from())


def invia_email(destinatario: str, oggetto: str, testo: str, html: str) -> None:
    """Invio SMTP (Brevo, STARTTLS). MailNonConfigurata se mancano le
    credenziali; altre eccezioni = invio fallito."""
    if not email_configurata():
        raise MailNonConfigurata("Email non configurata (BREVO_LOGIN, BREVO_SMTP_KEY, MAIL_FROM).")
    nome_mitt, indirizzo = parseaddr(config.mail_from())
    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = formataddr((nome_mitt or "Portale KPI NeWatt", indirizzo))
    msg["To"] = destinatario
    msg.set_content(testo)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(config.smtp_host(), config.smtp_port(), timeout=30) as server:
        server.starttls()
        server.login(config.smtp_login(), config.smtp_key())
        server.send_message(msg)


def manda_invito(token: str, scade: dt.datetime, utente: dict, reimpostazione: bool = False
                 ) -> tuple[bool, str]:
    """Compone e invia l'email di invito. (inviata?, messaggio per l'admin)."""
    link = link_invito(token)
    oggetto, testo, html = email_invito(utente["nome"], utente["username"], utente["ruolo"],
                                        utente.get("societa"), link, scade, config.portale_url(),
                                        reimpostazione)
    try:
        invia_email(utente["email"], oggetto, testo, html)
    except MailNonConfigurata:
        return False, ("L'invio delle email non è ancora configurato: consegna tu il link "
                       "qui sotto all'utente (vale una volta, fino al "
                       f"{scade:%d/%m/%Y}).")
    except Exception as e:  # noqa: BLE001
        return False, (f"Email non partita ({type(e).__name__}: {e}). Consegna tu il link "
                       "qui sotto, oppure riprova con «Reinvia invito».")
    try:
        segna_email_inviata(token)
    except Exception:  # noqa: BLE001 — il flag è solo informativo
        pass
    return True, f"Email inviata a {utente['email']}."
