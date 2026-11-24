# Deploy — Portale KPI NeWatt su Streamlit Community Cloud

Repo **privato** `arcudani/newatt-portale-kpi`, app **pubblica** su Community Cloud (il piano
gratuito ammette una sola app privata, già usata da `bros-erp`; un'app pubblica da repo privato
non la occupa). «Pubblica» vuol dire solo che l'URL è raggiungibile: senza username e password
non si vede nulla (login su `kpi_utenti`).

Ogni push su `main` rideploya l'app: **mai push senza conferma**.

## 1. Segreti

Da `app\`:

```powershell
.venv\Scripts\python.exe _logs\genera_secrets_scc.py
```

Scrive `app\_logs\secrets_scc.toml` (gitignored) dal `.env` locale con python-dotenv:

| Chiave | Note |
|---|---|
| `NEWATT_DB_URL` | utente `kpi_portale` sul Transaction pooler di cte-newatt (solo tabelle `kpi_*`) |
| `SUPABASE_DB_URL` | DB bros-consulenza, solo per la sezione BP Migliora (admin) |
| `AUTH_COOKIE_KEY` | **nuova** a ogni generazione (cookie di produzione separato dal locale) |
| `BREVO_LOGIN`, `BREVO_SMTP_KEY` | SMTP Brevo, le stesse di Bros_ERP |
| `MAIL_FROM` | `Portale KPI NeWatt <energia@brosconsulenza.com>` (mittente verificato su Brevo) |
| `PORTALE_URL` | `https://newatt-kpi.streamlit.app` (link nelle email di invito) |

Incollare il TOML in SCC e poi **cancellare il file locale**.

## 2. App su share.streamlit.io

Create app → *Deploy a public app from GitHub*:

- Repository `arcudani/newatt-portale-kpi`, branch `main`, main file **`app/app.py`**;
- App URL: `newatt-kpi` (deve combaciare con `PORTALE_URL`; Streamlit vieta la parola «portal» nei sottodomini);
- Advanced settings → Python **3.12**, Secrets = contenuto di `secrets_scc.toml`.

Le dipendenze si installano da `requirements.txt` in radice (delega a `app/requirements.txt`).

## 3. Verifiche post-deploy

1. URL → schermata di login NeWatt con i tre loghi.
2. Login admin → Panoramica gruppo; Gazel → Livello I e II con i dati caricati.
3. Amministrazione → Utenti e accessi: creare un utente di prova con la propria email → arriva
   l'email da energia@ con il link `https://newatt-kpi.streamlit.app/?invito=…` → scegliere
   la password → login con il perimetro giusto (es. solo Gazel) → disattivare l'utente di prova.
4. Logout e re-login (cookie `newatt_kpi_auth`).
