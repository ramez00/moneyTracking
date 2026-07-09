from flask import Flask, render_template, request, session, g
from flask_babel import Babel, gettext
import os

from database.db import get_db, init_db, seed_db

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
    return render_template("landing.html")


@app.route("/register")
def register():
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
    app.run(debug=True, port=5001)
