import click
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask.cli import with_appcontext
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from platform_app.database import get_db
from platform_app.extensions import limiter, login_manager
from platform_app.models import Owner

bp = Blueprint("auth", __name__)
DUMMY_HASH = generate_password_hash("not-a-real-account-password", method="scrypt")


@login_manager.user_loader
def load_owner(owner_id):
    return get_db().get(Owner, owner_id)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.applications"))
    if request.method == "POST":
        username = request.form.get("login", "").strip().lower()
        password = request.form.get("password", "")
        owner = get_db().scalar(select(Owner).where(Owner.login == username))
        valid = check_password_hash(owner.password_hash if owner else DUMMY_HASH, password)
        if owner and valid:
            session.clear()
            login_user(owner)
            session.permanent = True
            return redirect(url_for("dashboard.applications"))
        flash("Invalid login or password.", "error")
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@click.command("create-owner")
@click.option("--login", prompt=True)
@click.password_option()
@with_appcontext
def create_owner(login, password):
    """Provision a local owner without putting passwords in shell history."""
    login = login.strip().lower()
    if not 1 <= len(login) <= 128 or len(password) < 12:
        raise click.ClickException("Login must be 1–128 characters; password at least 12.")
    database = get_db()
    if database.scalar(select(Owner).where(Owner.login == login)):
        raise click.ClickException("That login already exists.")
    database.add(
        Owner(login=login, password_hash=generate_password_hash(password, method="scrypt"))
    )
    database.commit()
    click.echo("Owner created.")
