import json

from conftest import login


def test_add_user_prints_a_password_that_works(app):
    result = app.test_cli_runner().invoke(args=["add-user", "Emil"])
    name, password = result.output.strip().split("\t")
    assert name == "Emil"
    assert login(app.test_client(), "EMIL", password).status_code == 302


def test_import_fills_gaps_and_keeps_existing_notes(app, tmp_path):
    client = app.test_client()
    login(client, "Ben", "ben-pass")
    ben = next(u["id"] for u in client.get("/api/data").json["users"] if u["name"] == "Ben")
    client.put(f"/api/users/{ben}/visits/SWE", json={"note": "mine"})
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"ben": {"SWE": "seeded", "FIN": "seeded"}}))
    result = app.test_cli_runner().invoke(args=["import-visits", str(seed)])
    assert result.exit_code == 0, result.output
    visits = next(u["visits"] for u in client.get("/api/data").json["users"] if u["name"] == "Ben")
    assert visits == {"SWE": "mine", "FIN": "seeded"}


def test_import_refuses_unknown_countries(app, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"Ben": {"XXX": ""}}))
    result = app.test_cli_runner().invoke(args=["import-visits", str(seed)])
    assert result.exit_code != 0 and "XXX" in result.output
