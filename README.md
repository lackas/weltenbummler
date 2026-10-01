# Weltenbummler

A world map for the family: everyone marks the countries they have been to,
with a short note per country (dates, a link to the trip). Everyone sees every
map; only the owner and the admin can change it.

Flask, SQLite and argon2 on the server; d3 and topojson in the browser, vendored,
no build step. Map data is Natural Earth 1:50m (`tools/build-countries.sh`),
shown in Equal Earth by default, with the UN emblem projection and Mercator as
alternatives.

## Run locally

    python3 -m venv ~/src/venv/weltenbummler
    ~/src/venv/weltenbummler/bin/pip install -e ".[serve,test]"
    export WELTENBUMMLER_INSTANCE=$PWD/instance WELTENBUMMLER_INSECURE_COOKIE=1
    flask --app weltenbummler add-user Anna --admin   # prints the password
    flask --app weltenbummler run

`WELTENBUMMLER_INSECURE_COOKIE=1` is for plain http on localhost only; without it
the session cookie is `Secure`.

## Users

Login is by first name, case-insensitive. The admin creates users and resets
passwords under /admin (the new password is shown once); on the command line:

    flask --app weltenbummler add-user NAME [--admin]
    flask --app weltenbummler reset-password NAME
    flask --app weltenbummler import-visits seed.json   # {"Name": {"DEU": "note"}}

Country keys are Natural Earth `ADM0_A3` codes.

## Tests

    pytest

## Deploy

`docker compose up -d --build` listens on 127.0.0.1:8070; put Caddy in front,
see `deploy/Caddyfile.example`. The `instance/` directory holds the database and
the session key and is mounted into the container.
