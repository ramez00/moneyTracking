from flask import (Flask, render_template, request, session, g, redirect,
                   url_for, flash, jsonify, abort)
from flask_babel import Babel, gettext
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

from database.db import (get_db, init_db, seed_db, get_user_by_email,
                         create_user, get_user_by_id, get_expense_summary,
                         get_expenses_by_user, get_user_theme, save_user_theme,
                         delete_user_theme)
from alerts import send_visit_alert
from palette import generate_palette, is_valid_hex

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


@app.template_filter('friendly_date')
def friendly_date(value):
    return datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S').strftime('%d %b %Y')


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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            error = gettext("Please enter your email and password.")
            return render_template("login.html", error=error)

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            error = gettext("Invalid email or password.")
            return render_template("login.html", error=error)

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash(gettext("You've been signed out."), "success")
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        flash(gettext("Please sign in to view your profile."), "error")
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        flash(gettext("Please sign in to view your profile."), "error")
        return redirect(url_for("login"))

    summary = get_expense_summary(user_id)
    expenses = get_expenses_by_user(user_id)
    theme = get_user_theme(user_id)
    return render_template("profile.html", user=user, summary=summary,
                          expenses=expenses, theme=theme)


@app.route("/api/generate-palette", methods=["POST"])
def api_generate_palette():
    if not session.get("user_id"):
        abort(401)

    data = request.get_json(silent=True) or {}
    base_color = data.get("base_color", "")
    if not is_valid_hex(base_color):
        abort(400)

    return jsonify(generate_palette(base_color))


@app.route("/api/save-theme", methods=["POST"])
def api_save_theme():
    user_id = session.get("user_id")
    if not user_id:
        abort(401)

    data = request.get_json(silent=True) or {}
    base_color = data.get("base_color", "")
    if not is_valid_hex(base_color):
        abort(400)

    palette = generate_palette(base_color)
    save_user_theme(user_id, base_color, palette)
    return jsonify({"base_color": base_color, "palette": palette})


@app.route("/api/theme")
def api_theme():
    if not session.get("user_id"):
        abort(401)

    return jsonify(get_user_theme(session["user_id"]))


@app.route("/api/reset-theme", methods=["POST"])
def api_reset_theme():
    if not session.get("user_id"):
        abort(401)

    delete_user_theme(session["user_id"])
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


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
