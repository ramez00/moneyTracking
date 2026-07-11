# Spec: Login and Logout

## Overview

Login and logout complete Spendly's authentication loop. Step 2 added account
creation; the `GET /login` route and `login.html` form already exist, but the
form submission is not handled and there is no way to end a session. This feature
adds `POST /login` — reading the submitted email and password, looking the user
up with the existing `get_user_by_email()` helper, verifying the stored hash with
werkzeug's `check_password_hash`, and, on success, storing the user in the Flask
`session` and redirecting to the profile page. It also implements `GET /logout`
to clear the auth session, and makes `base.html` session-aware so the nav shows a
Logout link when signed in and the Sign in / Get started links otherwise. This
unblocks Step 4 (profile) and every authenticated feature that follows.

## Depends on

- **Step 1 — Database setup**: the `users` table and `get_db()`.
- **Step 2 — Registration**: `create_user()` and, critically, `get_user_by_email()`
  in `database/db.py`, plus werkzeug password hashing (both already on `main`).

## Routes

- `POST /login` — validate the submitted email/password, verify the hash, set the
  session, and redirect to `profile`; re-render `login.html` with an error on
  failure — **public**.
- `GET /logout` — clear the auth session and redirect to the landing page —
  **logged-in** (harmless if hit while logged out).

`GET /login` already renders `login.html` and is merged into the same view with
`methods=["GET", "POST"]`. No other new routes.

## Database changes

No schema changes. No new DB helpers — login reuses the existing
`get_user_by_email(email)` (parameterised query, returns the row or `None`).
Password verification uses `werkzeug.security.check_password_hash` in the route
against the stored `password_hash`; no plaintext is ever stored or logged.

## Templates

- **Create:** None.
- **Modify:**
  - `templates/base.html` — wrap the nav auth links in a
    `{% if session.user_id %}` conditional: when logged in, show the user's name
    (links to `profile`) and a `Logout` link styled with the existing `nav-cta`
    class; otherwise show the current `Sign in` / `Get started` links. Reuse
    existing CSS classes only — no new styles.
  - `templates/login.html` — change the hardcoded `action="/login"` to
    `action="{{ url_for('login') }}"` (project rule: never hardcode URLs). The
    existing `{% if error %}` → `.auth-error` block already renders the error the
    route passes; no other markup changes.

## Files to change

- `app.py`
  - Extend the werkzeug import to include `check_password_hash`.
  - Replace the GET-only `login` view with `methods=["GET", "POST"]`: on POST read
    `email` (`.strip().lower()`, matching how register stores it) and `password`
    from `request.form`; if either is blank, re-render with a `gettext` error; look
    up the user and verify the hash; on failure re-render `login.html` with a
    **single generic** `gettext("Invalid email or password.")` (no email
    enumeration); on success set `session["user_id"]` and `session["user_name"]`
    and `redirect(url_for("profile"))`.
  - Replace the `logout` stub: `session.pop("user_id", None)` and
    `session.pop("user_name", None)` (targeted pops, so the Babel `language` key
    survives), `flash(gettext("You've been signed out."), "success")`, then
    `redirect(url_for("landing"))`.
- `templates/base.html` — nav conditional (above).
- `templates/login.html` — `url_for('login')` form action.

## Files to create

- None (aside from this spec document).

## New dependencies

No new dependencies — `werkzeug` (`check_password_hash`) and Flask `session` are
already available; `app.secret_key` is already set.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only; reuse
  `get_user_by_email()`, keep DB logic out of the route.
- Parameterised queries only — never build SQL with f-strings.
- Passwords verified with werkzeug (`check_password_hash`); never store or log the
  plaintext password.
- Use `url_for()` for every internal link and form action — never hardcode URLs.
- Use CSS variables — never hardcode hex values (no new styles are expected).
- All templates extend `base.html`.
- Wrap user-facing strings in `gettext`/`_()` so they stay translatable
  (Arabic/RTL is supported); the `language` session key must survive logout.
- Login failure must re-render the form with one generic error — never reveal
  whether the email or the password was wrong, and never echo the password back.
- Logout is a plain `GET` route matching the nav link and the CLAUDE.md route table.

## Definition of done

Verified by running the app (`python app.py`, port 5001):

1. `GET /login` still renders the form with no error shown, and its `action`
   resolves via `url_for('login')`.
2. Submitting valid credentials for an existing user (e.g. the seeded
   `demo@spendly.com` / `demo123`) sets the session and redirects to `/profile`;
   the nav then shows the user's name and a Logout link instead of Sign in /
   Get started.
3. Submitting a wrong password, or an email with no account, re-renders
   `login.html` with the single generic "Invalid email or password." error and
   sets no session.
4. Submitting with a blank email or password (bypassing the HTML `required`
   attribute) re-renders the form with an error rather than raising a 500.
5. `GET /logout` clears the auth session, shows the "You've been signed out."
   flash, and redirects to the landing page; the nav returns to Sign in /
   Get started while the selected UI language (EN/AR) is preserved.
6. Email matching is case-insensitive (login lowercases input to match how
   registration stores the address).
