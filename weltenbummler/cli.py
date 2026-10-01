"""Command line: `flask --app weltenbummler <command>`."""

import json

import click

from .db import get_db, login_key
from .users import UserError, create_user, new_password, set_password


def register(app):
    @app.cli.command("add-user")
    @click.argument("name")
    @click.option("--admin", is_flag=True, help="May manage users and edit every map.")
    def add_user(name, admin):
        """Create a user and print the generated password."""
        password = new_password()
        try:
            create_user(get_db(), name, password, is_admin=admin)
        except UserError as e:
            raise click.ClickException(str(e)) from e
        click.echo(f"{name}\t{password}")

    @app.cli.command("reset-password")
    @click.argument("name")
    def reset_password(name):
        """Give a user a new generated password and print it."""
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE login = ?", (login_key(name),)).fetchone()
        if user is None:
            raise click.ClickException(f"Unknown user {name}")
        password = new_password()
        set_password(db, user["id"], password)
        click.echo(f"{name}\t{password}")

    @app.cli.command("import-visits")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    def import_visits(path):
        """Add visits from a JSON file: {"Name": {"ADM0_A3": "note", ...}, ...}.

        An existing visit keeps its note; the import only fills gaps.
        """
        db = get_db()
        countries = app.config["COUNTRIES"]
        data = json.loads(open(path, encoding="utf-8").read())
        for name, visits in data.items():
            user = db.execute("SELECT id FROM users WHERE login = ?", (login_key(name),)).fetchone()
            if user is None:
                raise click.ClickException(f"Unknown user {name}")
            unknown = set(visits) - countries
            if unknown:
                raise click.ClickException(f"Unknown countries for {name}: {sorted(unknown)}")
            for country, note in visits.items():
                db.execute(
                    "INSERT OR IGNORE INTO visits (user_id, country, note) VALUES (?, ?, ?)",
                    (user["id"], country, note),
                )
            click.echo(f"{name}: {len(visits)} countries")
        db.commit()
