from flask import Flask, render_template, request, session, g, redirect, url_for, flash
from flask_babel import Babel, gettext
from werkzeug.security import generate_password_hash
import os

from database.db import get_db, init_db, seed_db, get_user_by_email, create_user
from alerts import send_visit_alert

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'

# Supported languages
LANGUAGES = {
    'en': 'English',
    'ar': 'العربية'
}

# Babel configuration
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'
app.config['LANGUAGES'] = LANGUAGES
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'

babel = Babel(app, locale_selector=lambda: session.get('language',
              request.accept_languages.best_match(LANGUAGES.keys()) or 'en'))

with app.app_context():
    init_db()
    seed_db()

def get_locale():
    """Get the current locale"""
    locale = session.get('language')
    if locale and locale in LANGUAGES:
        return locale
    locale = request.accept_languages.best_match(LANGUAGES.keys())
    return locale or 'en'

@app.before_request
def before_request():
    # Get language from URL param
    lang = request.args.get('lang')
    if lang and lang in LANGUAGES:
        session['language'] = lang
    
    # Store current language in g for template access
    g.locale = get_locale()

@app.context_processor
def inject_locale():
    """Make locale available in templates"""
    return {'get_locale': get_locale}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    send_visit_alert(request)
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = gettext("All fields are required.")
            return render_template("register.html", error=error)

        if len(password) < 8:
            error = gettext("Password must be at least 8 characters.")
            return render_template("register.html", error=error)

        if get_user_by_email(email) is not None:
            error = gettext("An account with that email already exists.")
            return render_template("register.html", error=error)

        create_user(name, email, generate_password_hash(password))
        flash(gettext("Account created — please sign in."), "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/login")
def login():
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
