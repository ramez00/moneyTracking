"""Tests for the add-expense form.

Spec: .claude/specs/06-add-expense.md

Assertions are derived from the spec's Routes, Rules for implementation,
and Definition of done sections -- not from reading app.py/database/db.py's
implementation.
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
        "amount": "42.50",
        "category": "Food",
        "date": TODAY,
        "description": "Test expense",
    }
    form.update(overrides)
    return form


# ---------------------------------------------------------------------------
# Route-level tests: auth guards
# ---------------------------------------------------------------------------

def test_add_expense_get_requires_login_redirects(client):
    response = client.get("/expenses/add", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_add_expense_get_requires_login_flash_message(client):
    response = client.get("/expenses/add", follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "sign in" in html.lower()


def test_add_expense_post_requires_login_redirects_and_inserts_nothing(client):
    from database import db as db_module

    baseline = _count_expenses(db_module)
    response = client.post("/expenses/add", data=_valid_form(),
                           follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert _count_expenses(db_module) == baseline


# ---------------------------------------------------------------------------
# Route-level tests: happy path
# ---------------------------------------------------------------------------

def test_add_expense_get_logged_in_renders_form(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Alice", "alice@example.com")
    _login(client, user_id)

    response = client.get("/expenses/add")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="amount"' in html
    assert 'name="category"' in html
    assert 'name="date"' in html
    assert 'name="description"' in html


def test_add_expense_valid_post_creates_row_for_current_user(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Bob", "bob@example.com")
    _login(client, user_id)

    client.post("/expenses/add", data=_valid_form(description="lunch out"))

    conn = db_module.get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["amount"] == 42.50
    assert rows[0]["category"] == "Food"
    assert rows[0]["date"] == TODAY
    assert rows[0]["description"] == "lunch out"


def test_add_expense_valid_post_redirects_to_profile(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Cara", "cara@example.com")
    _login(client, user_id)

    response = client.post("/expenses/add", data=_valid_form(),
                           follow_redirects=False)

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]


def test_add_expense_valid_post_appears_in_profile_list_and_total(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Dan", "dan@example.com")
    _login(client, user_id)

    response = client.post(
        "/expenses/add",
        data=_valid_form(amount="99.25", description="new keyboard"),
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "new keyboard" in html
    assert "99.25" in html


def test_add_expense_description_is_optional(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Eve", "eve@example.com")
    _login(client, user_id)

    response = client.post("/expenses/add", data=_valid_form(description=""),
                           follow_redirects=False)

    assert response.status_code == 302
    assert _count_expenses(db_module, user_id) == 1


@pytest.mark.parametrize("category", VALID_CATEGORIES)
def test_add_expense_valid_categories_all_accepted(client, category):
    from database import db as db_module

    user_id = _create_user(db_module, "Faye", "faye@example.com")
    _login(client, user_id)

    response = client.post("/expenses/add",
                           data=_valid_form(category=category),
                           follow_redirects=False)

    assert response.status_code == 302
    assert _count_expenses(db_module, user_id) == 1


# ---------------------------------------------------------------------------
# Route-level tests: validation rejections
# ---------------------------------------------------------------------------

def _assert_rejected(client, db_module, user_id, form):
    response = client.post("/expenses/add", data=form, follow_redirects=False)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="amount"' in html
    assert _count_expenses(db_module, user_id) == 0
    return html


def test_add_expense_negative_amount_rejected_no_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Gus", "gus@example.com")
    _login(client, user_id)

    _assert_rejected(client, db_module, user_id, _valid_form(amount="-5"))


def test_add_expense_zero_amount_rejected_no_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Hana", "hana@example.com")
    _login(client, user_id)

    _assert_rejected(client, db_module, user_id, _valid_form(amount="0"))


def test_add_expense_non_numeric_amount_rejected_no_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Ivan", "ivan@example.com")
    _login(client, user_id)

    _assert_rejected(client, db_module, user_id,
                     _valid_form(amount="not-a-number"))


def test_add_expense_invalid_date_format_rejected_no_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Jan", "jan@example.com")
    _login(client, user_id)

    _assert_rejected(client, db_module, user_id, _valid_form(date="18-07-2026"))


def test_add_expense_future_date_rejected_no_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Kim", "kim@example.com")
    _login(client, user_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _assert_rejected(client, db_module, user_id, _valid_form(date=tomorrow))


def test_add_expense_invalid_category_rejected_no_insert(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Leo", "leo@example.com")
    _login(client, user_id)

    _assert_rejected(client, db_module, user_id,
                     _valid_form(category="NotACategory"))


# ---------------------------------------------------------------------------
# Database-helper tests: database/db.py
# ---------------------------------------------------------------------------

def test_create_expense_inserts_row_with_given_fields(db):
    user_id = _create_user(db, "Moe", "moe@example.com")

    db.create_expense(user_id, 12.34, "Transport", "2026-07-01", "bus fare")

    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["amount"] == 12.34
    assert row["category"] == "Transport"
    assert row["date"] == "2026-07-01"
    assert row["description"] == "bus fare"


def test_create_expense_returns_new_row_id(db):
    user_id = _create_user(db, "Nora", "nora@example.com")

    expense_id = db.create_expense(user_id, 5.0, "Other", "2026-07-01", None)

    conn = db.get_db()
    row = conn.execute(
        "SELECT id FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()

    assert isinstance(expense_id, int)
    assert expense_id == row["id"]
