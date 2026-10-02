import pytest
from conftest import login

HEADERS = {"X-Requested-With": "weltenbummler"}


def user_id(client, name):
    return next(u["id"] for u in client.get("/api/data").json["users"] if u["name"] == name)


def visits(client, name):
    return next(u["visits"] for u in client.get("/api/data").json["users"] if u["name"] == name)


def test_a_user_marks_a_country_with_a_note(client):
    login(client, "Ben", "ben-pass")
    me = user_id(client, "Ben")
    assert client.put(f"/api/users/{me}/visits/SWE", json={"note": "1998"}).status_code == 200
    assert visits(client, "Ben") == {"SWE": "1998"}
    client.put(f"/api/users/{me}/visits/SWE", json={"note": "1998 und 2004"})
    assert visits(client, "Ben") == {"SWE": "1998 und 2004"}
    assert client.delete(f"/api/users/{me}/visits/SWE", headers=HEADERS).status_code == 204
    assert visits(client, "Ben") == {}


def test_everyone_sees_every_map(client):
    login(client, "Ben", "ben-pass")
    client.put(f"/api/users/{user_id(client, 'Ben')}/visits/FIN", json={})
    login(client, "Clara", "clara-pass")
    assert visits(client, "Ben") == {"FIN": ""}


def test_a_user_cannot_change_someone_elses_map(client):
    login(client, "Clara", "clara-pass")
    ben = user_id(client, "Ben")
    assert client.put(f"/api/users/{ben}/visits/FIN", json={}).status_code == 403
    assert client.delete(f"/api/users/{ben}/visits/FIN", headers=HEADERS).status_code == 403


def test_the_admin_changes_anyones_map(client):
    login(client, "Anna", "admin-pass")
    clara = user_id(client, "Clara")
    assert client.put(f"/api/users/{clara}/visits/CZE", json={"note": "Lissabon"}).status_code == 200
    assert visits(client, "Clara") == {"CZE": "Lissabon"}


@pytest.mark.parametrize("country", ["XYZ", "usa", "DEU-BY"])
def test_only_known_countries_are_stored(client, country):
    login(client, "Ben", "ben-pass")
    assert client.put(f"/api/users/{user_id(client, 'Ben')}/visits/{country}", json={}).status_code == 404


def test_writes_need_json_or_the_custom_header(client):
    """A cross-site form can send neither, so these are the CSRF guard."""
    login(client, "Ben", "ben-pass")
    me = user_id(client, "Ben")
    assert client.put(f"/api/users/{me}/visits/SWE", data={"note": "x"}).status_code == 400
    client.put(f"/api/users/{me}/visits/SWE", json={})
    assert client.delete(f"/api/users/{me}/visits/SWE").status_code == 400
    assert visits(client, "Ben") == {"SWE": ""}


def test_a_long_note_is_cut(client):
    login(client, "Ben", "ben-pass")
    client.put(f"/api/users/{user_id(client, 'Ben')}/visits/SWE", json={"note": "x" * 5000})
    assert len(visits(client, "Ben")["SWE"]) == 2000


def test_the_page_runs_under_a_strict_csp(client):
    login(client, "Ben", "ben-pass")
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "'unsafe-inline'" not in csp and "script-src 'self'" in csp


def test_a_us_state_can_be_stored_like_a_country(client):
    login(client, "Ben", "ben-pass")
    assert client.put(f"/api/users/{user_id(client, 'Ben')}/visits/US-CA", json={"note": "2022"}).status_code == 200
    assert visits(client, "Ben") == {"US-CA": "2022"}
