"""Tests for the delete-expense confirm/delete flow.

Spec: .claude/specs/08-delete-expense.md

Assertions are derived from the spec's Routes, Database changes, Rules for
implementation, and Definition of done sections -- not from reading app.py's
delete_expense implementation.
"""
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

TODAY = date.today().isoformat()


def _create_user(db_module, name, email, password="testpass123"):
    return db_module.create_user(name, email, generate_password_hash(password))


def _login(client, user_id, user_name="Test User"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


def _get_expense_row(db_module, expense_id):
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return row


def _count_expenses(db_module, user_id=None):
    conn = db_module.get_db()
    if user_id is None:
        row = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
    conn.close()
    return row["n"]


def _delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


# ---------------------------------------------------------------------------
# Route-level tests: auth guards
# ---------------------------------------------------------------------------

def test_delete_expense_get_requires_login_redirects(client):
    response = client.get(_delete_url(1), follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_delete_expense_get_requires_login_flash_message(client):
    response = client.get(_delete_url(1), follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "sign in" in html.lower()


def test_delete_expense_post_requires_login_redirects_and_deletes_nothing(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Owner", "owner@example.com")
    expense_id = db_module.create_expense(
        owner_id, 20.0, "Food", TODAY, "original"
    )

    response = client.post(_delete_url(expense_id), follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    row = _get_expense_row(db_module, expense_id)
    assert row is not None
    assert row["amount"] == 20.0


# ---------------------------------------------------------------------------
# Route-level tests: ownership / 404s
# ---------------------------------------------------------------------------

def test_delete_expense_get_nonexistent_id_returns_404(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Alice", "alice@example.com")
    _login(client, user_id)

    response = client.get(_delete_url(999999))

    assert response.status_code == 404


def test_delete_expense_post_nonexistent_id_returns_404(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Alice2", "alice2@example.com")
    _login(client, user_id)

    response = client.post(_delete_url(999999))

    assert response.status_code == 404


def test_delete_expense_get_other_users_expense_returns_404(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Bob", "bob@example.com")
    other_id = _create_user(db_module, "Carl", "carl@example.com")
    expense_id = db_module.create_expense(
        owner_id, 15.0, "Food", TODAY, "bob's lunch"
    )
    _login(client, other_id)

    response = client.get(_delete_url(expense_id))

    assert response.status_code == 404


def test_delete_expense_post_other_users_expense_returns_404_and_does_not_delete(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Dana", "dana@example.com")
    other_id = _create_user(db_module, "Evan", "evan@example.com")
    expense_id = db_module.create_expense(
        owner_id, 15.0, "Food", TODAY, "dana's lunch"
    )
    _login(client, other_id)

    response = client.post(_delete_url(expense_id))

    assert response.status_code == 404

    row = _get_expense_row(db_module, expense_id)
    assert row is not None
    assert row["amount"] == 15.0
    assert row["description"] == "dana's lunch"


# ---------------------------------------------------------------------------
# Route-level tests: GET confirmation page (happy path + "GET never deletes")
# ---------------------------------------------------------------------------

def test_delete_expense_get_own_expense_renders_confirmation_details(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Faye", "faye@example.com")
    expense_id = db_module.create_expense(
        user_id, 42.50, "Health", TODAY, "pharmacy run"
    )
    _login(client, user_id)

    response = client.get(_delete_url(expense_id))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert TODAY in html
    assert "pharmacy run" in html
    assert "42.50" in html
    # confirmation page must offer a way back to /profile (Cancel link)
    assert "/profile" in html


def test_delete_expense_get_does_not_delete_the_row(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Gus", "gus@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "still here"
    )
    _login(client, user_id)

    client.get(_delete_url(expense_id))

    row = _get_expense_row(db_module, expense_id)
    assert row is not None


def test_delete_expense_repeated_get_never_deletes(client):
    """GET is idempotent and non-destructive, even across multiple visits
    (guards against a bare link, browser prefetch, or crawler triggering a
    delete)."""
    from database import db as db_module

    user_id = _create_user(db_module, "Hana", "hana@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "still here"
    )
    _login(client, user_id)

    for _ in range(5):
        response = client.get(_delete_url(expense_id))
        assert response.status_code == 200

    row = _get_expense_row(db_module, expense_id)
    assert row is not None
    assert _count_expenses(db_module, user_id) == 1


# ---------------------------------------------------------------------------
# Route-level tests: POST deletes (happy path)
# ---------------------------------------------------------------------------

def test_delete_expense_post_removes_row_from_db(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Ivan", "ivan@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "to be deleted"
    )
    baseline_count = _count_expenses(db_module, user_id)
    _login(client, user_id)

    client.post(_delete_url(expense_id))

    assert _count_expenses(db_module, user_id) == baseline_count - 1
    assert _get_expense_row(db_module, expense_id) is None


def test_delete_expense_post_redirects_to_profile(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Jill", "jill@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "to be deleted"
    )
    _login(client, user_id)

    response = client.post(_delete_url(expense_id), follow_redirects=False)

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]


def test_delete_expense_post_flashes_confirmation_message(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Kai", "kai@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "to be deleted"
    )
    _login(client, user_id)

    response = client.post(_delete_url(expense_id), follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "deleted" in html.lower()


def test_delete_expense_post_removes_from_profile_expense_list(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Lena", "lena@example.com")
    keep_id = db_module.create_expense(
        user_id, 5.0, "Food", TODAY, "keep me around"
    )
    delete_id = db_module.create_expense(
        user_id, 10.0, "Shopping", TODAY, "delete me please"
    )
    _login(client, user_id)

    client.post(_delete_url(delete_id))

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "keep me around" in html
    assert "delete me please" not in html


def test_delete_expense_post_updates_summary_total(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Milo", "milo@example.com")
    db_module.create_expense(user_id, 5.0, "Food", TODAY, "keep")
    delete_id = db_module.create_expense(
        user_id, 10.0, "Shopping", TODAY, "delete"
    )
    _login(client, user_id)

    before = db_module.get_expense_summary(user_id)
    assert before["total"] == 15.0
    assert before["count"] == 2

    client.post(_delete_url(delete_id))

    after = db_module.get_expense_summary(user_id)
    assert after["total"] == 5.0
    assert after["count"] == 1

    response = client.get("/profile")
    html = response.get_data(as_text=True)
    assert "5.00" in html
    assert "15.00" not in html


# ---------------------------------------------------------------------------
# Template test: profile page exposes a delete link per expense, plus the
# existing edit link
# ---------------------------------------------------------------------------

def test_profile_page_shows_delete_link_for_each_expense(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Nina", "nina@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    _login(client, user_id)

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f"/expenses/{expense_id}/delete" in html
    assert f"/expenses/{expense_id}/edit" in html


def test_delete_expense_cancel_link_points_to_profile_without_deleting(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Omar", "omar@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "still here"
    )
    _login(client, user_id)

    # Simulate "clicking Cancel": GET the confirm page, then GET /profile,
    # without ever POSTing to the delete route.
    client.get(_delete_url(expense_id))
    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "still here" in html
    assert _get_expense_row(db_module, expense_id) is not None


# ---------------------------------------------------------------------------
# Database-helper tests: database/db.py
# ---------------------------------------------------------------------------

def test_delete_expense_helper_removes_row(db):
    user_id = db.create_user(
        "Priya", "priya@example.com", generate_password_hash("testpass123")
    )
    expense_id = db.create_expense(user_id, 5.5, "Other", TODAY, "snack")

    db.delete_expense(expense_id, user_id)

    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()

    assert row is None


def test_delete_expense_helper_scoped_by_user_id_does_not_delete_other_users_row(db):
    owner_id = db.create_user(
        "Quinn", "quinn@example.com", generate_password_hash("testpass123")
    )
    attacker_id = db.create_user(
        "Rae", "rae@example.com", generate_password_hash("testpass123")
    )
    expense_id = db.create_expense(owner_id, 5.5, "Other", TODAY, "snack")

    # attacker attempts to delete owner's row by passing their own user_id
    db.delete_expense(expense_id, attacker_id)

    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["amount"] == 5.5


def test_delete_expense_helper_nonexistent_id_is_a_no_op(db):
    user_id = db.create_user(
        "Sam", "sam@example.com", generate_password_hash("testpass123")
    )

    # Should not raise even though no row matches.
    db.delete_expense(999999, user_id)

    conn = db.get_db()
    count = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    conn.close()

    assert count == 0
