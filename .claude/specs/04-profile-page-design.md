# Spec: Profile Page Design

## Overview

The profile page is where a signed-in user lands after login and can check
their account details and spending at a glance. Right now `GET /profile` is a
raw string stub (`"Profile page — coming in Step 4"`), which also breaks the
"never use raw string returns for stub routes once implemented" rule the
moment this step lands. This feature turns it into a real page: it gates
access to logged-in users, shows the user's name/email/member-since date, and
surfaces a simple read-only spending summary (total spent, expense count, and
a per-category breakdown) built from the expenses the demo seed data already
provides. It does not add any way to create, edit, or delete expenses — that
is explicitly Steps 7–9.

## Depends on

- **Step 1 — Database setup**: `users` and `expenses` tables, `get_db()`.
- **Step 2 — Registration**: `create_user()`, account creation flow.
- **Step 3 — Login and Logout**: `session["user_id"]` / `session["user_name"]`
  set on login, cleared on logout, and the session-aware nav in `base.html`.

## Routes

- `GET /profile` — if no `session["user_id"]`, flash a message and redirect to
  `login`; otherwise fetch the user and their expense summary and render
  `profile.html` — **logged-in**.

No other new routes. `expenses/add`, `expenses/<id>/edit`, and
`expenses/<id>/delete` remain untouched stubs (Steps 7–9).

## Database changes

No schema changes — `users` and `expenses` already have everything needed.
Two new **read-only** helper functions in `database/db.py` (parameterized,
following the existing style of `get_user_by_email`):

- `get_user_by_id(user_id)` — `SELECT * FROM users WHERE id = ?`, returns the
  row or `None`.
- `get_expense_summary(user_id)` — runs parameterized queries against
  `expenses` for the given `user_id` and returns a dict with:
  - `total` — `SUM(amount)` (0 if the user has no expenses)
  - `count` — `COUNT(*)`
  - `by_category` — list of `{category, total}` rows via
    `GROUP BY category ORDER BY total DESC`

## Templates

- **Create:** `templates/profile.html` — extends `base.html`. Sections:
  - Account card: user's name, email, and "Member since" (formatted from
    `created_at`).
  - Summary card: total spent and expense count.
  - Category breakdown: simple list/bars of `by_category`, each row showing
    category name and its total. If `count == 0`, show an empty-state message
    instead (e.g. "No expenses yet") rather than an empty list.
- **Modify:** None.

## Files to change

- `app.py`
  - Extend the `database.db` import to include `get_user_by_id` and
    `get_expense_summary`.
  - Replace the `profile` stub: check `session.get("user_id")`; if missing,
    `flash(gettext("Please sign in to view your profile."), "error")` and
    `redirect(url_for("login"))`; otherwise call `get_user_by_id` and
    `get_expense_summary` and `render_template("profile.html", user=..., summary=...)`.
- `database/db.py` — add `get_user_by_id()` and `get_expense_summary()`.

## Files to create

- `templates/profile.html`
- `static/css/profile.css` — page-specific styles for the account/summary/
  category cards (per architecture rule: page-specific styles get their own
  file, no inline `<style>`).
- This spec document.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only; all new queries
  live in `database/db.py`, never inline in `app.py`.
- Parameterised queries only — never build SQL with f-strings.
- Passwords are never touched by this feature; do not select or render
  `password_hash` anywhere in `profile.html`.
- Use `url_for()` for every internal link — never hardcode URLs.
- Use CSS variables from `style.css` (`--ink`, `--paper-card`, `--accent`,
  `--border`, `--radius-md`, etc.) in `profile.css` — never hardcode hex
  values.
- `profile.html` must extend `base.html`.
- Wrap every user-facing string in `gettext`/`_()`, including the new flash
  message and category names where applicable, to keep EN/AR i18n working.
- `GET /profile` must be unreachable without a session — no data for another
  user's `user_id` should ever be requested or guessable from the URL (no
  `<id>` in the route; it always uses `session["user_id"]`).

## Definition of done

Verified by running the app (`python app.py`, port 5001):

1. Visiting `/profile` while logged out redirects to `/login` and shows the
   "Please sign in to view your profile." flash message.
2. Logging in with the seeded `demo@spendly.com` / `demo123` and visiting
   `/profile` shows the account card (name, email, member-since date) and a
   summary card with the correct total and count matching the 8 seeded
   expenses.
3. The category breakdown lists each seeded category (Food, Transport, Bills,
   Health, Entertainment, Shopping, Other) with the right per-category total,
   ordered highest-to-lowest.
4. A freshly registered user with zero expenses sees the empty-state message
   in the category section instead of a blank or broken layout.
5. The page renders correctly in both EN and AR (`?lang=ar`), including RTL
   layout inherited from `base.html`.
6. No raw string response remains for `/profile` — it always renders
   `profile.html`.
