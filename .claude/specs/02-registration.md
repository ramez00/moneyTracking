# Spec: Registration

## Overview

Registration lets a new visitor create a Spendly account by submitting
their name, email, and password. This is Step 2 of the roadmap: the
`GET /register` route and `register.html` form already exist, but the
form submission is not yet handled. This feature adds `POST /register`
processing — server-side validation, a uniqueness check on email,
password hashing with werkzeug, insertion into the existing `users`
table, and a redirect to the login page on success. It turns the static
registration form into a working sign-up flow, unblocking login (Step 3)
and every authenticated feature that follows.

## Depends on

- **Step 1 — Database setup**: requires the `users` table and the
  `get_db()` helper in `database/db.py` (both already present on `main`).

## Routes

- `POST /register` — validate the submitted form, create the user, and
  redirect to login on success; re-render `register.html` with an error
  message on failure — **public**

`GET /register` is already implemented (renders `register.html`) and
does not change. No other new routes.

## Database changes

No schema changes — the `users` table already exists with the required
columns (`name`, `email UNIQUE`, `password_hash`, `created_at`).

Two new helper functions are added to `database/db.py` (DB logic must
never live in the route):

- `get_user_by_email(email)` — return the matching user row or `None`.
- `create_user(name, email, password_hash)` — insert a new user and
  return the new `id`.

Both must use parameterised (`?`) queries.

## Templates

- **Create:** None.
- **Modify:** `templates/register.html`
  - Change the hardcoded `action="/register"` to
    `action="{{ url_for('register') }}"` (project rule: never hardcode
    URLs). The existing `{% if error %}` block already renders the error
    passed from the route — no other markup changes needed.

## Files to change

- `app.py` — extend the `register` view to accept `POST`
  (`methods=["GET", "POST"]`); on POST, read `name`, `email`, `password`
  from `request.form`, validate, call the new DB helpers, and either
  redirect to `login` or re-render `register.html` with an `error`.
- `database/db.py` — add `get_user_by_email()` and `create_user()`.
- `templates/register.html` — use `url_for('register')` for the form
  action.

## Files to create

- None (aside from this spec document).

## New dependencies

No new dependencies — `werkzeug` (for `generate_password_hash`) is
already in `requirements.txt` and already imported in `database/db.py`.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only — never build SQL with f-strings.
- Passwords hashed with werkzeug (`generate_password_hash`); never store
  or log the plaintext password.
- DB logic lives in `database/db.py`, never inline in the route.
- Use `url_for()` for every internal link and form action — never
  hardcode URLs.
- Use CSS variables — never hardcode hex values (no new styles are
  expected, but if any are added they follow this rule).
- All templates extend `base.html`.
- Wrap error messages in `gettext`/`_()` so they stay translatable, and
  never echo the raw password back to the template.
- On duplicate email, re-render the form with a friendly error — do not
  let the `UNIQUE` constraint raise a 500.

## Definition of done

Verified by running the app (`python app.py`, port 5001):

1. `GET /register` still renders the registration form with no error
   shown.
2. Submitting the form with a new name/email/password creates exactly
   one row in the `users` table with a hashed `password_hash` (not
   plaintext) and redirects to `GET /login`.
3. Submitting with an email that already exists re-renders
   `register.html` with a visible error and creates no new row.
4. Submitting with a missing/blank field (bypassing the browser
   `required` attribute) re-renders the form with an error rather than
   raising a 500.
5. Submitting a password shorter than the stated minimum (8 characters)
   is rejected with a visible error and creates no user.
6. The registration form's `action` resolves via `url_for('register')`
   and posts successfully.
