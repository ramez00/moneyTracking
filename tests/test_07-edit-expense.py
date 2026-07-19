"""Tests for the edit-expense form.

Spec: .claude/specs/07-edit-expense.md

Assertions are derived from the spec's Routes and Definition of done
sections -- not from reading app.py/database/db.py's implementation.
"""
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

VALID_CATEGORIES = (
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"
)

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


def _valid_form(**overrides):
    form = {
        "amount": "77.00",
        "category": "Transport",
        "date": TODAY,
        "description": "Updated expense",
    }
    form.update(overrides)
    return form


def _edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


# ---------------------------------------------------------------------------
# Route-level tests: auth guards
# ---------------------------------------------------------------------------

def test_edit_expense_get_requires_login_redirects(client):
    response = client.get(_edit_url(1), follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_edit_expense_get_requires_login_flash_message(client):
    response = client.get(_edit_url(1), follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "sign in" in html.lower()


def test_edit_expense_post_requires_login_redirects_and_modifies_nothing(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Owner", "owner@example.com")
    expense_id = db_module.create_expense(
        owner_id, 20.0, "Food", TODAY, "original"
    )

    response = client.post(_edit_url(expense_id), data=_valid_form(),
                            follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    row = _get_expense_row(db_module, expense_id)
    assert row["amount"] == 20.0
    assert row["description"] == "original"


# ---------------------------------------------------------------------------
# Route-level tests: ownership / 404s
# ---------------------------------------------------------------------------

def test_edit_expense_get_nonexistent_id_returns_404(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Alice", "alice@example.com")
    _login(client, user_id)

    response = client.get(_edit_url(999999))

    assert response.status_code == 404


def test_edit_expense_get_other_users_expense_returns_404(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Bob", "bob@example.com")
    other_id = _create_user(db_module, "Carl", "carl@example.com")
    expense_id = db_module.create_expense(
        owner_id, 15.0, "Food", TODAY, "bob's lunch"
    )
    _login(client, other_id)

    response = client.get(_edit_url(expense_id))

    assert response.status_code == 404


def test_edit_expense_post_other_users_expense_returns_404_and_does_not_modify(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Dana", "dana@example.com")
    other_id = _create_user(db_module, "Evan", "evan@example.com")
    expense_id = db_module.create_expense(
        owner_id, 15.0, "Food", TODAY, "dana's lunch"
    )
    _login(client, other_id)

    response = client.post(_edit_url(expense_id), data=_valid_form())

    assert response.status_code == 404

    row = _get_expense_row(db_module, expense_id)
    assert row["amount"] == 15.0
    assert row["description"] == "dana's lunch"


# ---------------------------------------------------------------------------
# Route-level tests: happy path
# ---------------------------------------------------------------------------

def test_edit_expense_get_own_expense_renders_prefilled_form(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Faye", "faye@example.com")
    expense_id = db_module.create_expense(
        user_id, 33.75, "Health", TODAY, "pharmacy run"
    )
    _login(client, user_id)

    response = client.get(_edit_url(expense_id))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="amount"' in html
    assert 'name="category"' in html
    assert 'name="date"' in html
    assert 'name="description"' in html
    assert "33.75" in html
    assert "pharmacy run" in html
    assert TODAY in html


def test_edit_expense_valid_post_updates_existing_row_no_new_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Gus", "gus@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "old description"
    )
    baseline_count = _count_expenses(db_module, user_id)

    _login(client, user_id)
    client.post(_edit_url(expense_id), data=_valid_form(
        amount="88.88", category="Shopping", description="new description"
    ))

    assert _count_expenses(db_module, user_id) == baseline_count

    row = _get_expense_row(db_module, expense_id)
    assert row["amount"] == 88.88
    assert row["category"] == "Shopping"
    assert row["description"] == "new description"


def test_edit_expense_valid_post_redirects_to_profile(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Hana", "hana@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "old description"
    )
    _login(client, user_id)

    response = client.post(_edit_url(expense_id), data=_valid_form(),
                            follow_redirects=False)

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]


def test_edit_expense_valid_post_appears_in_profile_list_and_total(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Ivan", "ivan@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "old description"
    )
    _login(client, user_id)

    response = client.post(
        _edit_url(expense_id),
        data=_valid_form(amount="123.45", description="edited keyboard"),
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "edited keyboard" in html
    assert "123.45" in html
    assert "old description" not in html


@pytest.mark.parametrize("category", VALID_CATEGORIES)
def test_edit_expense_valid_categories_all_accepted(client, category):
    from database import db as db_module

    user_id = _create_user(db_module, "Jill", "jill@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    _login(client, user_id)

    response = client.post(_edit_url(expense_id),
                            data=_valid_form(category=category),
                            follow_redirects=False)

    assert response.status_code == 302

    row = _get_expense_row(db_module, expense_id)
    assert row["category"] == category


# ---------------------------------------------------------------------------
# Route-level tests: validation rejections (form re-rendered, row unchanged)
# ---------------------------------------------------------------------------

def _assert_rejected(client, db_module, expense_id, original_row, form):
    response = client.post(_edit_url(expense_id), data=form,
                            follow_redirects=False)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="amount"' in html

    row = _get_expense_row(db_module, expense_id)
    assert row["amount"] == original_row["amount"]
    assert row["category"] == original_row["category"]
    assert row["date"] == original_row["date"]
    assert row["description"] == original_row["description"]
    return html


def test_edit_expense_negative_amount_rejected_no_modification(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Kai", "kai@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    original_row = _get_expense_row(db_module, expense_id)
    _login(client, user_id)

    _assert_rejected(client, db_module, expense_id, original_row,
                      _valid_form(amount="-5"))


def test_edit_expense_zero_amount_rejected_no_modification(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Lena", "lena@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    original_row = _get_expense_row(db_module, expense_id)
    _login(client, user_id)

    _assert_rejected(client, db_module, expense_id, original_row,
                      _valid_form(amount="0"))


def test_edit_expense_non_numeric_amount_rejected_no_modification(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Milo", "milo@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    original_row = _get_expense_row(db_module, expense_id)
    _login(client, user_id)

    _assert_rejected(client, db_module, expense_id, original_row,
                      _valid_form(amount="not-a-number"))


def test_edit_expense_invalid_date_format_rejected_no_modification(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Nina", "nina@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    original_row = _get_expense_row(db_module, expense_id)
    _login(client, user_id)

    _assert_rejected(client, db_module, expense_id, original_row,
                      _valid_form(date="18-07-2026"))


def test_edit_expense_future_date_rejected_no_modification(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Omar", "omar@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    original_row = _get_expense_row(db_module, expense_id)
    _login(client, user_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _assert_rejected(client, db_module, expense_id, original_row,
                      _valid_form(date=tomorrow))


def test_edit_expense_invalid_category_rejected_no_modification(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Priya", "priya@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    original_row = _get_expense_row(db_module, expense_id)
    _login(client, user_id)

    _assert_rejected(client, db_module, expense_id, original_row,
                      _valid_form(category="NotACategory"))


# ---------------------------------------------------------------------------
# Template test: profile page exposes an edit link per expense
# ---------------------------------------------------------------------------

def test_profile_page_shows_edit_link_for_each_expense(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Quinn", "quinn@example.com")
    expense_id = db_module.create_expense(
        user_id, 10.0, "Food", TODAY, "original"
    )
    _login(client, user_id)

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f"/expenses/{expense_id}/edit" in html


# ---------------------------------------------------------------------------
# Database-helper tests: database/db.py
# ---------------------------------------------------------------------------

def test_get_expense_by_id_returns_row_for_owner(db):
    user_id = db.create_user(
        "Rae", "rae@example.com", generate_password_hash("testpass123")
    )
    expense_id = db.create_expense(user_id, 5.5, "Other", TODAY, "snack")

    expense = db.get_expense_by_id(expense_id, user_id)

    assert expense is not None
    assert expense["amount"] == 5.5
    assert expense["category"] == "Other"
    assert expense["date"] == TODAY
    assert expense["description"] == "snack"


def test_get_expense_by_id_returns_none_for_wrong_user(db):
    owner_id = db.create_user(
        "Sam", "sam@example.com", generate_password_hash("testpass123")
    )
    other_id = db.create_user(
        "Tia", "tia@example.com", generate_password_hash("testpass123")
    )
    expense_id = db.create_expense(owner_id, 5.5, "Other", TODAY, "snack")

    assert db.get_expense_by_id(expense_id, other_id) is None


def test_get_expense_by_id_returns_none_for_nonexistent_id(db):
    user_id = db.create_user(
        "Uma", "uma@example.com", generate_password_hash("testpass123")
    )

    assert db.get_expense_by_id(999999, user_id) is None


def test_update_expense_modifies_row_in_place(db):
    user_id = db.create_user(
        "Vik", "vik@example.com", generate_password_hash("testpass123")
    )
    expense_id = db.create_expense(user_id, 1.0, "Food", TODAY, "before")

    db.update_expense(expense_id, user_id, 2.0, "Bills", TODAY, "after")

    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    count = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    conn.close()

    assert count == 1
    assert row["amount"] == 2.0
    assert row["category"] == "Bills"
    assert row["description"] == "after"


def test_update_expense_does_not_affect_other_users_row(db):
    owner_id = db.create_user(
        "Will", "will@example.com", generate_password_hash("testpass123")
    )
    attacker_id = db.create_user(
        "Xena", "xena@example.com", generate_password_hash("testpass123")
    )
    expense_id = db.create_expense(owner_id, 1.0, "Food", TODAY, "before")

    # attacker attempts to update owner's row by passing their own user_id
    db.update_expense(expense_id, attacker_id, 999.0, "Bills", TODAY, "hacked")

    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()

    assert row["amount"] == 1.0
    assert row["description"] == "before"
