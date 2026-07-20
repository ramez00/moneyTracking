from flask import (Flask, render_template, request, session, g, redirect,
                   url_for, flash, abort)
from flask_babel import Babel, gettext
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import math
import os

from database.db import (get_db, init_db, seed_db, get_user_by_email,
                         create_user, get_user_by_id, get_expense_summary,
                         get_expenses_by_user, create_expense,
                         get_expense_by_id, update_expense,
                         delete_expense as delete_expense_row)
from alerts import send_visit_alert

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'

# Supported languages
LANGUAGES = {
    'en': 'English',
    'ar': 'العربية'
}

EXPENSE_CATEGORIES = ("Food", "Transport", "Bills", "Health",
                      "Entertainment", "Shopping", "Other")
MAX_EXPENSE_AMOUNT = 1_000_000
MAX_DESCRIPTION_LENGTH = 500

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


def _require_login(error_message):
    """Return the current user_id, or None if the session is missing/stale.

    Also flashes error_message and clears a stale session, so callers only
    need to redirect to login when this returns None.
    """
    user_id = session.get("user_id")
    if not user_id:
        flash(error_message, "error")
        return None

    if get_user_by_id(user_id) is None:
        session.clear()
        flash(error_message, "error")
        return None

    return user_id


def _validate_expense_form(form):
    """Validate expense form fields; returns (amount, category, expense_date,
    description, error). error is None on success, all other fields may be
    None/partial when error is set.
    """
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    date_raw = form.get("date", "").strip()
    description = form.get("description", "").strip()

    expense_date = None
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = None

    error = None
    if amount is None or not math.isfinite(amount) or amount <= 0:
        error = gettext("Amount must be a positive number.")
    elif amount > MAX_EXPENSE_AMOUNT:
        error = gettext("Amount is too large.")
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        error = gettext("Description is too long.")
    elif category not in EXPENSE_CATEGORIES:
        error = gettext("Please choose a valid category.")
    else:
        try:
            expense_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
            if expense_date > date.today():
                error = gettext("Date cannot be in the future.")
        except ValueError:
            error = gettext("Please enter a valid date.")

    return amount, category, expense_date, description, error


def _parse_date_range(start_raw, end_raw):
    if not start_raw or not end_raw:
        return None, None

    try:
        start_dt = datetime.strptime(start_raw, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_raw, "%Y-%m-%d").date()
    except ValueError:
        flash(gettext("Invalid date range — showing all expenses."), "error")
        return None, None

    if start_dt > end_dt:
        flash(gettext("Invalid date range — showing all expenses."), "error")
        return None, None

    return start_dt.isoformat(), end_dt.isoformat()


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

    start_date, end_date = _parse_date_range(request.args.get("start"),
                                              request.args.get("end"))

    summary = get_expense_summary(user_id, start_date, end_date)
    expenses = get_expenses_by_user(user_id, start_date, end_date)

    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    return render_template(
        "profile.html", user=user, summary=summary, expenses=expenses,
        this_month_start=this_month_start.isoformat(),
        this_month_end=today.isoformat(),
        last_month_start=last_month_start.isoformat(),
        last_month_end=last_month_end.isoformat(),
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = _require_login(gettext("Please sign in to add an expense."))
    if user_id is None:
        return redirect(url_for("login"))

    today = date.today().isoformat()

    if request.method == "POST":
        amount, category, expense_date, description, error = \
            _validate_expense_form(request.form)

        if error:
            return render_template("add_expense.html", error=error,
                                   categories=EXPENSE_CATEGORIES,
                                   today=today, form=request.form)

        create_expense(user_id, amount, category, expense_date.isoformat(),
                       description or None)
        flash(gettext("Expense added."), "success")
        return redirect(url_for("profile"))

    return render_template("add_expense.html",
                           categories=EXPENSE_CATEGORIES, today=today, form={})


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = _require_login(gettext("Please sign in to edit an expense."))
    if user_id is None:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    today = date.today().isoformat()

    if request.method == "POST":
        amount, category, expense_date, description, error = \
            _validate_expense_form(request.form)

        if error:
            return render_template("edit_expense.html", error=error,
                                   categories=EXPENSE_CATEGORIES,
                                   today=today, form=request.form,
                                   expense_id=id)

        update_expense(id, user_id, amount, category,
                       expense_date.isoformat(), description or None)
        flash(gettext("Expense updated."), "success")
        return redirect(url_for("profile"))

    form = {
        "amount": f"{expense['amount']:.2f}",
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    return render_template("edit_expense.html",
                           categories=EXPENSE_CATEGORIES, today=today,
                           form=form, expense_id=id)


@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
def delete_expense(id):
    user_id = _require_login(gettext("Please sign in to delete an expense."))
    if user_id is None:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "POST":
        delete_expense_row(id, user_id)
        flash(gettext("Expense deleted."), "success")
        return redirect(url_for("profile"))

    return render_template("delete_expense.html", expense=expense)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
