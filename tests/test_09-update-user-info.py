"""Tests for the edit-profile (update user info) flow.

Spec: .claude/specs/09-update-user-info.md

Assertions are derived from the spec's Routes, Database changes, Rules for
implementation, and Definition of done sections -- not from reading app.py's
edit_profile implementation or database/db.py's update_user implementation.
"""
from werkzeug.security import generate_password_hash, check_password_hash

import pytest

EDIT_PROFILE_URL = "/profile/edit"
DEFAULT_PASSWORD = "testpass123"


def _create_user(db_module, name, email, password=DEFAULT_PASSWORD):
    return db_module.create_user(name, email, generate_password_hash(password))


def _login(client, user_id, user_name="Test User"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


def _get_user_row(db_module, user_id):
    conn = db_module.get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def _edit_form(name="Updated Name", email="updated@example.com",
                current_password=DEFAULT_PASSWORD, new_password="",
                confirm_password=""):
    return {
        "name": name,
        "email": email,
        "current_password": current_password,
        "new_password": new_password,
        "confirm_password": confirm_password,
    }


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_get_edit_profile_requires_login_redirects(client):
    response = client.get(EDIT_PROFILE_URL, follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_get_edit_profile_requires_login_flash_message(client):
    response = client.get(EDIT_PROFILE_URL, follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "sign in" in html.lower()


def test_post_edit_profile_requires_login_redirects_and_does_not_write(client):
    from database import db as db_module

    owner_id = _create_user(db_module, "Owner", "owner@example.com")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Hacked Name", email="hacked@example.com"),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    row = _get_user_row(db_module, owner_id)
    assert row["name"] == "Owner"
    assert row["email"] == "owner@example.com"


# ---------------------------------------------------------------------------
# GET pre-fill
# ---------------------------------------------------------------------------

def test_get_edit_profile_prefills_name_and_email(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Alice Original", "alice@example.com")
    _login(client, user_id, "Alice Original")

    response = client.get(EDIT_PROFILE_URL)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Alice Original" in html
    assert "alice@example.com" in html


def test_get_edit_profile_password_fields_blank(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Bob Original", "bob@example.com",
                            password="original-secret")
    _login(client, user_id, "Bob Original")

    response = client.get(EDIT_PROFILE_URL)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    # The real password (or any password) must never be echoed into a
    # password input's value attribute.
    assert 'value="original-secret"' not in html
    assert "original-secret" not in html


# ---------------------------------------------------------------------------
# Wrong current password blocks the whole submission
# ---------------------------------------------------------------------------

def test_post_wrong_current_password_rejected_no_db_write(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Carl Original", "carl@example.com",
                            password="correct-password")
    _login(client, user_id, "Carl Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="New Name", email="newcarl@example.com",
                         current_password="wrong-password"),
        follow_redirects=False,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200  # re-render, not a redirect
    assert "incorrect" in html.lower() or "error" in html.lower()

    row = _get_user_row(db_module, user_id)
    assert row["name"] == "Carl Original"
    assert row["email"] == "carl@example.com"
    assert check_password_hash(row["password_hash"], "correct-password")


# ---------------------------------------------------------------------------
# Happy path: name/email change
# ---------------------------------------------------------------------------

def test_post_correct_current_password_updates_name_and_email(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Dana Original", "dana@example.com")
    _login(client, user_id, "Dana Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Dana Updated", email="dana.updated@example.com",
                         current_password=DEFAULT_PASSWORD),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]

    row = _get_user_row(db_module, user_id)
    assert row["name"] == "Dana Updated"
    assert row["email"] == "dana.updated@example.com"


def test_post_success_updates_session_user_name(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Evan Original", "evan@example.com")
    _login(client, user_id, "Evan Original")

    client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Evan Updated", email="evan@example.com",
                         current_password=DEFAULT_PASSWORD),
    )

    with client.session_transaction() as sess:
        assert sess["user_name"] == "Evan Updated"


def test_post_success_flashes_message(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Faye Original", "faye@example.com")
    _login(client, user_id, "Faye Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Faye Updated", email="faye@example.com",
                         current_password=DEFAULT_PASSWORD),
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    # Should land back on the profile page showing the new details.
    assert "Faye Updated" in html


def test_post_success_profile_page_shows_new_name_and_email(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Gus Original", "gus@example.com")
    _login(client, user_id, "Gus Original")

    client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Gus Updated", email="gus.updated@example.com",
                         current_password=DEFAULT_PASSWORD),
    )

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Gus Updated" in html
    assert "gus.updated@example.com" in html


# ---------------------------------------------------------------------------
# Email uniqueness
# ---------------------------------------------------------------------------

def test_post_email_already_used_by_another_user_rejected(client):
    from database import db as db_module

    _create_user(db_module, "Existing User", "taken@example.com")
    user_id = _create_user(db_module, "Hana Original", "hana@example.com")
    _login(client, user_id, "Hana Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Hana Original", email="taken@example.com",
                         current_password=DEFAULT_PASSWORD),
        follow_redirects=False,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200  # re-rendered with error, not redirected
    assert "error" in html.lower() or "already" in html.lower() or "exist" in html.lower()

    row = _get_user_row(db_module, user_id)
    assert row["email"] == "hana@example.com"


def test_post_keeping_own_existing_email_is_accepted(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Ivy Original", "ivy@example.com")
    _login(client, user_id, "Ivy Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Ivy Updated", email="ivy@example.com",
                         current_password=DEFAULT_PASSWORD),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]

    row = _get_user_row(db_module, user_id)
    assert row["name"] == "Ivy Updated"
    assert row["email"] == "ivy@example.com"


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------

def test_post_new_password_matches_confirm_allows_login_with_new_password(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Jack Original", "jack@example.com",
                            password="old-password1")
    _login(client, user_id, "Jack Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Jack Original", email="jack@example.com",
                         current_password="old-password1",
                         new_password="new-password1",
                         confirm_password="new-password1"),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]

    # Log out, then verify the new password works and the old one doesn't.
    client.get("/logout")

    bad_login = client.post(
        "/login", data={"email": "jack@example.com", "password": "old-password1"}
    )
    assert bad_login.status_code == 200  # re-rendered login form, no redirect
    with client.session_transaction() as sess:
        assert "user_id" not in sess

    good_login = client.post(
        "/login",
        data={"email": "jack@example.com", "password": "new-password1"},
        follow_redirects=False,
    )
    assert good_login.status_code == 302
    assert "/profile" in good_login.headers["Location"]


def test_post_new_password_too_short_rejected(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Kai Original", "kai@example.com",
                            password="old-password1")
    _login(client, user_id, "Kai Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Kai Original", email="kai@example.com",
                         current_password="old-password1",
                         new_password="short1",
                         confirm_password="short1"),
        follow_redirects=False,
    )

    assert response.status_code == 200  # re-render with error

    row = _get_user_row(db_module, user_id)
    assert check_password_hash(row["password_hash"], "old-password1")
    assert not check_password_hash(row["password_hash"], "short1")


def test_post_new_password_confirm_mismatch_rejected(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Lea Original", "lea@example.com",
                            password="old-password1")
    _login(client, user_id, "Lea Original")

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Lea Original", email="lea@example.com",
                         current_password="old-password1",
                         new_password="new-password1",
                         confirm_password="different-password1"),
        follow_redirects=False,
    )

    assert response.status_code == 200  # re-render with error

    row = _get_user_row(db_module, user_id)
    assert check_password_hash(row["password_hash"], "old-password1")
    assert not check_password_hash(row["password_hash"], "new-password1")


def test_post_blank_new_password_fields_leaves_hash_unchanged(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Mona Original", "mona@example.com",
                            password="stays-the-same1")
    _login(client, user_id, "Mona Original")

    before = _get_user_row(db_module, user_id)["password_hash"]

    response = client.post(
        EDIT_PROFILE_URL,
        data=_edit_form(name="Mona Updated", email="mona@example.com",
                         current_password="stays-the-same1",
                         new_password="", confirm_password=""),
        follow_redirects=False,
    )

    assert response.status_code == 302

    after = _get_user_row(db_module, user_id)["password_hash"]
    assert after == before
    assert check_password_hash(after, "stays-the-same1")


# ---------------------------------------------------------------------------
# Template: profile.html has a working edit-profile link
# ---------------------------------------------------------------------------

def test_profile_page_has_edit_profile_link(client):
    from database import db as db_module

    user_id = _create_user(db_module, "Nora Original", "nora@example.com")
    _login(client, user_id, "Nora Original")

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert EDIT_PROFILE_URL in html

    follow = client.get(EDIT_PROFILE_URL)
    assert follow.status_code == 200
