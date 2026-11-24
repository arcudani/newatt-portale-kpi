# Deploy — Controllo BP Migliora su Streamlit Community Cloud

Da fare **solo dopo conferma** (ogni push su `main` rideploya).

## 0. Decisione preliminare: repo privato o pubblico

Community Cloud (piano gratuito) consente **una sola app da repo privato**, già usata da `bros-erp`
(per questo `gas-monitor` è pubblico). Opzioni:

- **Repo pubblico** `arcudani/migliora-bp`: il codice non contiene numeri del BP (stanno su
  Supabase, test su dati fittizi), ma sono visibili struttura delle voci e catalogo KPI;
- **Workspace/piano che ammette più app private**, oppure un altro hosting.

## 1. Repository GitHub

```powershell
cd C:\Code\Migliora_BP
git status          # verificare che .env, .venv, *.xlsx NON siano tracciati
git add -A
git commit -m "Controllo BP Migliora: fase 1 (lettura)"
gh repo create arcudani/migliora-bp --private --source . --push    # o --public (vedi §0)
```

## 2. App su share.streamlit.io

- New app → repo `arcudani/migliora-bp`, branch `main`, main file **`app/app.py`**, Python 3.12.
- Settings → Secrets (TOML):

| Chiave | Note |
|---|---|
| `SUPABASE_DB_URL` | stessa delle altre app (Transaction pooler) |
| `AUTH_COOKIE_KEY` | chiave NUOVA e propria (`python -c "import secrets;print(secrets.token_hex(32))"`) |

## 3. Utenti e prima versione

1. `python imposta_pwd.py <Nome> --ruolo admin --societa Bros` (password digitata dall'utente, mai in chat).
2. Login → **Versioni** → controllare la quadratura di "BP v5 FTE" → **Approva** (solo dopo, il viewer
   NeWatt vede la dashboard).
3. Utenti NeWatt: `python imposta_pwd.py <Nome> --ruolo viewer --societa NeWatt`.

## 4. Collegamento dall'ERP

Nei secrets dell'ERP aggiungere `MIGLIORA_APP_URL = "<url SCC>"`: la tile Migliora (solo admin)
mostra il pulsante di apertura.

## 5. Verifiche post-deploy

1. URL → form di login con titolo "Controllo BP Migliora".
2. Login admin → Cruscotto con badge stato dati (quadratura OK 95/95).
3. Login viewer → solo versioni approvate, niente Consuntivo né KPI riservati (contratto NeWatt).
4. Logout e re-login (cookie `bros_migliora_auth`).
