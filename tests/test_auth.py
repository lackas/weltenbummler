from conftest import login

from weltenbummler.db import connect


def test_the_map_needs_a_login(client):
    assert client.get("/").headers["Location"] == "/login"
    assert client.get("/api/data").status_code == 401


def test_login_by_first_name_ignores_case(client):
    response = login(client, "  bEn ", "ben-pass")
    assert response.status_code == 302
    assert client.get("/api/data").json["me"]["admin"] is False


def test_a_wrong_password_is_refused(client):
    assert login(client, "Ben", "nope").status_code == 401
    assert login(client, "Nobody", "nope").status_code == 401
    assert client.get("/api/data").status_code == 401


def test_the_session_lasts_400_days(client):
    response = login(client, "Ben", "ben-pass")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Expires=" in cookie


def test_a_password_reset_logs_out_everywhere(app, client):
    login(client, "Ben", "ben-pass")
    admin = app.test_client()
    login(admin, "Anna", "admin-pass")
    ben_id = next(u["id"] for u in admin.get("/api/data").json["users"] if u["name"] == "Ben")
    response = admin.post(f"/admin/users/{ben_id}/reset", follow_redirects=True)
    assert "Neues Passwort für Ben" in response.text
    assert client.get("/api/data").status_code == 401


def test_changing_your_own_password_keeps_you_logged_in(app, client):
    login(client, "Clara", "clara-pass")
    other = app.test_client()
    login(other, "Clara", "clara-pass")
    response = client.post("/password", data={"old": "clara-pass", "new": "a-new-password"})
    assert response.status_code == 302
    assert client.get("/api/data").status_code == 200
    assert other.get("/api/data").status_code == 401
    assert login(app.test_client(), "clara", "a-new-password").status_code == 302


def test_only_the_admin_reaches_user_management(app, client):
    login(client, "Ben", "ben-pass")
    assert client.get("/admin").status_code == 403
    assert client.post("/admin/users", data={"name": "Eve"}).status_code == 403


def test_the_admin_creates_a_user_who_can_log_in(app, client):
    login(client, "Anna", "admin-pass")
    response = client.post("/admin/users", data={"name": "Dora"}, follow_redirects=True)
    password = response.text.split("Dora angelegt, Passwort: ")[1].split("<")[0]
    assert login(app.test_client(), "dora", password).status_code == 302


def test_a_name_cannot_be_taken_twice_in_another_case(app, client):
    login(client, "Anna", "admin-pass")
    response = client.post("/admin/users", data={"name": "CLARA"}, follow_redirects=True)
    assert "CLARA gibt es schon" in response.text
    db = connect(app.config["DATABASE"])
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 3
