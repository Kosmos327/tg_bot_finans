# Deployment-Path Audit

> Generated: 2026-03-17  
> Repository: Kosmos327/tg_bot_finans  
> Branch audited: `copilot/deployment-path-audit` (HEAD of `main` after PR #60)

---

## 1. Real Deployment Entrypoint

### Dockerfile (authoritative)

```dockerfile
# Dockerfile (root)
FROM python:3.12-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Conclusion**: The Dockerfile is correct and unambiguous:

| Property | Value |
|---|---|
| Python module launched | `backend.main` |
| ASGI app object | `app` (FastAPI instance in `backend/main.py`) |
| Port | `8000` |
| Frontend served | `miniapp/` directory mounted at `/miniapp` |

### What `backend/main.py` mounts

```python
# backend/main.py  lines 122-125
_miniapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "miniapp")
if os.path.isdir(_miniapp_dir):
    app.mount("/miniapp", StaticFiles(directory=_miniapp_dir, html=True), name="miniapp")
```

**Only `miniapp/`** is mounted; `static/` and `frontend/` are **not** mounted by the FastAPI app.

### Expected files included in deployment

All files **not** excluded by `.dockerignore` (which only excludes `.git`, `.gitignore`, `.env`, `*.pyc`, `__pycache__/`, pytest/cache dirs, `node_modules/`, IDE dirs, credentials).  
In practice **all of** `backend/`, `miniapp/`, `config/`, `app/`, `bot/`, `static/`, `frontend/`, `app.py`, `requirements.txt`, etc. are copied into the Docker image.

---

## 2. Wrong-Frontend Risks

### Three `index.html` files exist in the repo

| Path | Framework | Served by | State |
|---|---|---|---|
| `miniapp/index.html` | Telegram Mini App (FastAPI backend) | `backend/main.py` → `/miniapp/` | **CORRECT – active** |
| `frontend/index.html` | Older Mini App rewrite (3 JS files: `permissions.js`, `api.js`, `app.js`) | **Not mounted** by any current server | Legacy, orphaned |
| `static/index.html` | Monolithic inline JS SPA | `app.py` (Flask) → `/` | **Legacy Flask app** |

### Two `app.js` files exist

| Path | Size | Role |
|---|---|---|
| `miniapp/app.js` | 3 506 lines | **Current** – dual-mode Telegram+web, uses `/deals/create`, `/auth/miniapp-login`, etc. |
| `frontend/js/app.js` | 572 lines | **Old** – smaller, different UI structure, no `/deals/create` endpoint calls |

### Wrong-frontend risk: `static/` served instead of `miniapp/`

The old `app.py` (Flask) has:
```python
app = Flask(__name__, static_folder="static")

@app.route("/")
def index():
    return send_from_directory("static", "index.html")
```

If the deployment platform runs `python app.py` (or `flask run`) instead of the Dockerfile command, it will serve `static/index.html` via Flask on port **5000** — completely bypassing FastAPI and `miniapp/`.

### Wrong-frontend risk: `frontend/` deployed separately

`frontend/index.html` references `js/app.js`, `js/api.js`, `js/permissions.js`. If a CI pipeline or CDN is configured to deploy the `frontend/` directory as the web app root, users would see the old `frontend/` UI regardless of backend changes.

---

## 3. Wrong-Backend Risks

### Three Python `main.py` / server entrypoints exist

| File | Framework | Serves frontend? | Status |
|---|---|---|---|
| `backend/main.py` | FastAPI (uvicorn) | Yes — `miniapp/` at `/miniapp` | **CORRECT** |
| `app/main.py` | FastAPI (uvicorn) | No static mount | Alternative PG-only API |
| `app.py` | **Flask** (werkzeug) | Yes — `static/` at `/` | **OLD legacy app** |
| `bot.py` | aiogram bot runner | No web server | Telegram bot only |

### Risk: `app.py` running instead of `backend/main.py`

`app.py` is a **complete standalone Flask application** that:
- Serves `static/index.html` (old UI) at `/`
- Exposes `/api/deals`, `/api/user-role`, `/api/dashboard` etc. — **completely different API surface**
- Has no authentication checks → always allows deal creation (returns `{"success": true}`)
- Does **not** check `X-Telegram-Id` headers

If `app.py` is running on the production host (e.g. from a `python app.py` or `gunicorn app:app` process), users would see `static/index.html` and deal creation would always succeed — **but that is also not what is reported**. The reported error "Access denied: please login first" is a FastAPI/backend response, confirming FastAPI *is* running, but with old frontend code.

### Risk: `app/main.py` running

`app/main.py` is a different FastAPI app focused on PostgreSQL CRUD only; it has **no static file mount**, so the frontend would not be served from it. Unlikely to be the issue.

---

## 4. Docker/Start Command

| Question | Answer |
|---|---|
| Command that starts the server | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` |
| Python module launched | `backend.main` |
| Whether it launches `backend.main` | **Yes** (Dockerfile line 25) |
| Whether it serves `/miniapp` | Yes — `backend/main.py` mounts `miniapp/` at `/miniapp` (lines 122-125) |
| Whether `static/` is served | **No** — `static/` is copied into the image but never mounted by FastAPI |
| Whether `frontend/` is served | **No** — `frontend/` is copied but never mounted |

### No secondary Procfile / Railway / Render config

There is no `Procfile`, `railway.toml`, `render.yaml`, `fly.toml`, or `nixpacks.toml` in the repository root. Deployment relies solely on the `Dockerfile`.

---

## 5. Visible Deployment Markers

The following strings prove **definitively** that the latest code (post PR #60) is deployed.

### Marker 1 — Telegram Auth connected label

| Property | Value |
|---|---|
| File | `miniapp/app.js` line 1240 |
| Old text (pre PR #60) | `'Открыто вне Telegram'` |
| New text (post PR #60) | `'Telegram Auth — Подключено'` |
| Trigger | Visible in Settings tab when app is opened inside Telegram |
| Why it proves new code | Old string is gone from the repo; the live app shows old string → old code running |

### Marker 2 — Web auth label (browser mode)

| Property | Value |
|---|---|
| File | `miniapp/app.js` line 1243 |
| Old text (pre PR #60) | `'Открыто вне Telegram'` (pre-PR #60 code used this single fallback for **both** Telegram-SDK-available-but-no-initData and plain-browser cases) |
| New text (post PR #60) | `'Web Auth — Активно'` |
| Trigger | Visible in Settings tab when app is opened in a browser AND user has logged in with a password |
| Why it proves new code | Old code had one fallback label; new code distinguishes web-auth vs. no-auth |

### Marker 3 — No-auth label

| Property | Value |
|---|---|
| File | `miniapp/app.js` line 1246 |
| Old text (pre PR #60) | `'Открыто вне Telegram'` |
| New text (post PR #60) | `'Авторизация не выполнена'` |
| Trigger | Visible in Settings tab when app is opened in a browser with no stored auth |
| Why it proves new code | This is the "neutral" label for unauthenticated state — completely absent in old code |

### Marker 4 — Deal creation endpoint

| Property | Value |
|---|---|
| File | `miniapp/app.js` line 607 |
| Old endpoint | N/A (old `frontend/js/app.js` used a different mechanism) |
| New endpoint | `POST /deals/create` (SQL-function endpoint) |
| Why it proves new code | Old `frontend/js/app.js` does not call `/deals/create`; this call only exists in the new app |

---

## 6. Final Diagnosis

### A. Most likely reason the live app still shows old behaviour

**The deployment platform has not rebuilt/redeployed the Docker image since PR #60 was merged.**

Evidence:
1. `'Открыто вне Telegram'` was **removed** from `miniapp/app.js` in PR #60  
   (git history confirms: `-    tgStatus = 'Открыто вне Telegram';` → `+    tgStatus = 'Авторизация не выполнена';`).
2. The string `'Открыто вне Telegram'` **does not exist anywhere** in the current repo code.
3. The live app shows `'Открыто вне Telegram'` → it is serving a pre-PR-#60 version of `miniapp/app.js`.

The Docker image (or whichever artifact is deployed) was last built from an older commit and was not re-triggered after the merge.

### B. Does the repo have the right code but the deployment target is wrong?

**Yes.** The repository code is correct:
- `Dockerfile` correctly specifies `backend.main:app`
- `backend/main.py` correctly mounts `miniapp/` at `/miniapp`
- `miniapp/app.js` contains the new connection-status strings
- No wrong entrypoint is referenced in the Dockerfile

The mismatch is entirely between the **current repo state** and the **currently running deployment**.

### C. Exact entrypoint/file/path to verify next

In order of priority:

1. **Deployment platform build trigger** — Confirm that the CD pipeline re-ran after the merge of PR #60. Check the deployment dashboard (Railway / Render / Fly / VPS) for the last build timestamp and the commit SHA it was built from. It must be ≥ commit `2329e3d` (the PR #60 merge commit).

2. **Running Docker image tag** — On the production host, run:
   ```bash
   docker ps --format "table {{.Image}}\t{{.CreatedAt}}\t{{.Command}}"
   ```
   Verify the image was built **after** the PR #60 merge date.

3. **Live `/miniapp/app.js` content** — Fetch the live file and grep for the marker:
   ```bash
   curl -s https://<your-domain>/miniapp/app.js | grep "tgStatus ="
   ```
   If it returns `'Открыто вне Telegram'` → old image is still running.  
   If it returns `'Telegram Auth — Подключено'` / `'Web Auth — Активно'` / `'Авторизация не выполнена'` → new image is deployed.

4. **"Access denied: please login first" on deal creation (secondary issue)** — Even after the correct code is deployed, web-authenticated users (password login, no Telegram) will receive this error from `POST /deals/create` because `backend/routers/deals_sql.py` only resolves users via `X-Telegram-Id` / `X-Telegram-Init-Data` headers. The `X-User-Role` header sent by web-auth users is **not checked** by `_resolve_user()` in `deals_sql.py`. This is a **code-level gap** separate from the deployment problem — it will persist even after redeployment and requires adding `X-User-Role` / `X-Web-User-Id` support to `_resolve_user()`.
