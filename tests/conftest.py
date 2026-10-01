import threading

import pytest
from werkzeug.serving import make_server

from weltenbummler import create_app
from weltenbummler.db import connect
from weltenbummler.users import create_user


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE": str(tmp_path / "test.sqlite"),
            "SESSION_COOKIE_SECURE": False,
        }
    )
    db = connect(app.config["DATABASE"])
    create_user(db, "Anna", "admin-pass", is_admin=True)
    create_user(db, "Ben", "ben-pass")
    create_user(db, "Clara", "clara-pass")
    db.close()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, name, password):
    return client.post("/login", data={"name": name, "password": password})


@pytest.fixture
def live_server(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
