"""Tests for the profile date-range filter.

Spec: .claude/specs/05-profile-date-filter.md

Assertions are derived from the spec's Routes, Database changes, Rules
for implementation, and Definition of done sections -- not from reading
app.py/database/db.py's implementation.
"""
from werkzeug.security import generate_password_hash


def _create_user(db_module, name, email, password="testpass123"):
    return db_module.create_user(name, email, generate_password_hash(password))


def _insert_expense(db_module, user_id, amount, category, date_str, description=""):
    conn = db_module.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    conn.close()


def _login(client, user_id, user_name="Test User"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


# ---------------------------------------------------------------------------
# Route-level tests: GET /profile
# ---------------------------------------------------------------------------

def test_profile_requires_login_redirects(client):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_no_params_is_alltime(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Alice", "alice@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db_module, user_id, 20.0, "Food", "2020-06-15")
    _login(client, user_id)

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "30.00" in html
    assert "2020-01-01" in html
    assert "2020-06-15" in html


def test_profile_valid_range_narrows_stats_and_list(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Bob", "bob@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-01-01", "outside range")
    _insert_expense(db_module, user_id, 20.0, "Food", "2020-06-15", "inside range")
    _insert_expense(db_module, user_id, 5.0, "Food", "2020-06-20", "inside range")
    _login(client, user_id)

    response = client.get("/profile?start=2020-06-01&end=2020-06-30")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "25.00" in html
    assert "2020-06-15" in html
    assert "2020-06-20" in html
    assert "2020-01-01" not in html


def test_profile_range_is_inclusive_of_boundary_dates(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Nia", "nia@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-06-01", "start boundary")
    _insert_expense(db_module, user_id, 20.0, "Food", "2020-06-30", "end boundary")
    _login(client, user_id)

    response = client.get("/profile?start=2020-06-01&end=2020-06-30")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2020-06-01" in html
    assert "2020-06-30" in html
    assert "30.00" in html


def test_profile_start_after_end_falls_back_to_alltime_with_flash(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Cara", "cara@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db_module, user_id, 20.0, "Food", "2020-06-15")
    _login(client, user_id)

    response = client.get("/profile?start=2020-06-30&end=2020-06-01")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Invalid date range" in html
    assert "30.00" in html


def test_profile_malformed_date_does_not_crash(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Dan", "dan@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-01-01")
    _login(client, user_id)

    response = client.get("/profile?start=notadate&end=2020-06-30")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Invalid date range" in html
    assert "10.00" in html


def test_profile_out_of_range_calendar_date_does_not_crash(client):
    """Syntactically date-shaped but impossible value, e.g. month 13."""
    from database import db as db_module

    user_id = _create_user(db_module, "Eve", "eve@example.com")
    _login(client, user_id)

    response = client.get("/profile?start=2026-13-40&end=2026-01-01")

    assert response.status_code == 200


def test_profile_only_one_param_present_is_treated_as_unfiltered(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Faye", "faye@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db_module, user_id, 20.0, "Food", "2020-06-15")
    _login(client, user_id)

    response = client.get("/profile?start=2020-06-01")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Invalid date range" not in html
    assert "30.00" in html


def test_profile_scoped_to_logged_in_user_only(client):
    from database import db as db_module

    user_a = _create_user(db_module, "UserA", "usera@example.com")
    user_b = _create_user(db_module, "UserB", "userb@example.com")
    _insert_expense(db_module, user_a, 10.0, "Food", "2020-06-10", "user a expense")
    _insert_expense(db_module, user_b, 999.0, "Bills", "2020-06-10", "user b secret expense")

    _login(client, user_a)
    response = client.get("/profile?start=2020-06-01&end=2020-06-30")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "user a expense" in html
    assert "user b secret expense" not in html
    assert "999.00" not in html


def test_profile_sticky_form_values(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Gus", "gus@example.com")
    _login(client, user_id)

    response = client.get("/profile?start=2020-06-01&end=2020-06-30")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="2020-06-01"' in html
    assert 'value="2020-06-30"' in html


def test_profile_zero_match_range_shows_empty_state(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Hana", "hana@example.com")
    _insert_expense(db_module, user_id, 10.0, "Food", "2020-01-01")
    _login(client, user_id)

    response = client.get("/profile?start=2021-01-01&end=2021-01-31")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No expenses yet." in html


# ---------------------------------------------------------------------------
# Database-helper tests: database/db.py
# ---------------------------------------------------------------------------

def test_get_expenses_by_user_no_args_is_backward_compatible(db):
    user_id = _create_user(db, "Ivan", "ivan@example.com")
    _insert_expense(db, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db, user_id, 20.0, "Food", "2020-06-15")

    expenses = db.get_expenses_by_user(user_id)

    assert len(expenses) == 2


def test_get_expenses_by_user_filters_by_range(db):
    user_id = _create_user(db, "Jan", "jan@example.com")
    _insert_expense(db, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db, user_id, 20.0, "Food", "2020-06-15")
    _insert_expense(db, user_id, 5.0, "Food", "2020-06-20")

    expenses = db.get_expenses_by_user(
        user_id, start_date="2020-06-01", end_date="2020-06-30"
    )

    assert len(expenses) == 2
    assert {row["date"] for row in expenses} == {"2020-06-15", "2020-06-20"}


def test_get_expenses_by_user_range_is_inclusive(db):
    user_id = _create_user(db, "Kim", "kim@example.com")
    _insert_expense(db, user_id, 10.0, "Food", "2020-06-01")
    _insert_expense(db, user_id, 20.0, "Food", "2020-06-30")

    expenses = db.get_expenses_by_user(
        user_id, start_date="2020-06-01", end_date="2020-06-30"
    )

    assert len(expenses) == 2


def test_get_expenses_by_user_scoped_to_user_id(db):
    user_a = _create_user(db, "Leo", "leo@example.com")
    user_b = _create_user(db, "Moe", "moe@example.com")
    _insert_expense(db, user_a, 10.0, "Food", "2020-06-10")
    _insert_expense(db, user_b, 20.0, "Food", "2020-06-10")

    expenses = db.get_expenses_by_user(
        user_a, start_date="2020-06-01", end_date="2020-06-30"
    )

    assert len(expenses) == 1
    assert expenses[0]["amount"] == 10.0


def test_get_expense_summary_no_args_is_backward_compatible(db):
    user_id = _create_user(db, "Nora", "nora@example.com")
    _insert_expense(db, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db, user_id, 20.0, "Bills", "2020-06-15")

    summary = db.get_expense_summary(user_id)

    assert summary["total"] == 30.0
    assert summary["count"] == 2
    assert len(summary["by_category"]) == 2


def test_get_expense_summary_filters_by_range(db):
    user_id = _create_user(db, "Omar", "omar@example.com")
    _insert_expense(db, user_id, 10.0, "Food", "2020-01-01")
    _insert_expense(db, user_id, 20.0, "Bills", "2020-06-15")
    _insert_expense(db, user_id, 5.0, "Food", "2020-06-20")

    summary = db.get_expense_summary(
        user_id, start_date="2020-06-01", end_date="2020-06-30"
    )

    assert summary["total"] == 25.0
    assert summary["count"] == 2
    assert {row["category"] for row in summary["by_category"]} == {"Bills", "Food"}


def test_get_expense_summary_zero_matches_in_range(db):
    user_id = _create_user(db, "Priya", "priya@example.com")
    _insert_expense(db, user_id, 10.0, "Food", "2020-01-01")

    summary = db.get_expense_summary(
        user_id, start_date="2021-01-01", end_date="2021-01-31"
    )

    assert summary["total"] == 0
    assert summary["count"] == 0
    assert summary["by_category"] == []
