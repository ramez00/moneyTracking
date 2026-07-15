# CLAUDE.md

## Project overview

Spendly is a lightweight personal expense tracker built with Flask and SQLite.

---

## Architecture

```
spendly/
├── app.py              # All routes — single file, no blueprints
├── alerts.py            # Visitor-alert emails (IP + geolocation) via Brevo HTTP API
├── database/
│   └── db.py           # SQLite helpers: get_db(), init_db(), seed_db(), user/expense queries
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page (landing, register, login, profile, terms, privacy)
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles (includes landing-page styles — no separate landing.css)
│   │   └── profile.css     # Profile-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
├── translations/        # Flask-Babel catalogs (en, ar) — run pybabel to update
└── requirements.txt
```

**Where things belong:**

- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and `match` statements are fine

---

## Subagent Policy

- Always use a builtin explore subagent for codebase exploration
  before implementing any new feature
- Always use a subagent to verify test results
  after any implementation
- When asked to plan, delegate codebase research
  to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

---

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run dev server (port 5001)
python app.py

# Run all tests
pytest

# Run a specific test file
pytest tests/test_foo.py

# Run a specific test by name
pytest -k "test_name"

# Run tests with output visible
pytest -s
```

---

## Implemented vs stub routes

| Route                       | Status                                                            |
| --------------------------- | ----------------------------------------------------------------- |
| `GET /`                     | Implemented — renders `landing.html`, fires a visitor alert email |
| `GET, POST /register`       | Implemented — Step 2                                              |
| `GET /terms`                | Implemented — renders `terms.html`                                |
| `GET /privacy`              | Implemented — renders `privacy.html`                              |
| `GET, POST /login`          | Implemented — Step 3                                              |
| `GET /logout`               | Implemented — Step 3                                              |
| `GET /profile`              | Implemented — Step 4, spending summary dashboard                  |
| `GET /expenses/add`         | Stub — Step 7                                                     |
| `GET /expenses/<id>/edit`   | Stub — Step 8                                                     |
| `GET /expenses/<id>/delete` | Stub — Step 9                                                     |

**Do not implement a stub route unless the active task explicitly targets that step.**

Note: a base-color theme-picker feature (DB table, `/api/generate-palette`, `/api/save-theme`,
`/api/theme`, `/api/reset-theme`, and a `palette.py` module) was built but never wired to any
template markup, and has since been **removed entirely** — do not reintroduce it unless
explicitly requested again.

---

## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **`database/db.py` is fully implemented** — `get_db()`, `init_db()`, `seed_db()`, plus user/expense query helpers already exist; check it before adding a new helper so you don't duplicate one
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection (already done)
- The app runs on **port 5001**, not the Flask default 5000 — don't change this
- **No tests exist yet** — `pytest`/`pytest-flask` are declared in `requirements.txt` and documented under Commands, but there is no `tests/` directory yet
- `base.html`'s footer currently hardcodes `/terms` and `/privacy` instead of using `url_for()` — a known violation of the URL rule above, left as-is until addressed
- The theme-picker feature (see note under "Implemented vs stub routes") was removed — don't re-add a `theme` table, `palette.py`, or `/api/theme*` routes unless explicitly asked
