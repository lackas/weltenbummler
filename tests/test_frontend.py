import pytest
from playwright.sync_api import expect, sync_playwright


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1300, "height": 800})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    yield page
    context.close()
    assert errors == []


def login(page, live_server, name, password):
    page.goto(live_server + "/login")
    page.fill("input[name=name]", name)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_selector(".country")


def country(page, name):
    return page.locator(f".country:has(title:text-is('{name}'))")


def test_a_click_marks_a_country_and_the_note_is_kept(page, live_server):
    login(page, live_server, "ben", "ben-pass")
    country(page, "Schweden").click()
    expect(country(page, "Schweden")).to_have_class("country visited selected")
    page.fill("#detail-note", "Sommer 1998 https://example.org/schweden/")
    expect(page.locator("#detail-status")).to_have_text("Gespeichert")
    page.reload()
    page.wait_for_selector(".country.visited")
    link = page.locator("#visits a")
    expect(link).to_have_text("example.org/schweden")
    expect(link).to_have_attribute("href", "https://example.org/schweden/")


def test_unticking_removes_the_country(page, live_server):
    login(page, live_server, "ben", "ben-pass")
    country(page, "Finnland").click()
    page.uncheck("#detail-visited")
    expect(country(page, "Finnland")).not_to_have_class("country visited selected")
    expect(page.locator("#list-title")).to_have_text("Ben: 0 Länder")


def test_another_persons_map_is_read_only(page, live_server):
    login(page, live_server, "ben", "ben-pass")
    country(page, "Finnland").click()
    page.fill("#detail-note", "<b>nicht fett</b>")
    expect(page.locator("#detail-status")).to_have_text("Gespeichert")
    page.click("#detail .close")

    page.click("text=Abmelden")
    login(page, live_server, "Clara", "clara-pass")
    page.click("#people button:has-text('Ben')")
    country(page, "Finnland").click()
    expect(page.locator("#detail-visited")).to_be_hidden()
    expect(page.locator("#detail-note")).to_be_hidden()
    # the note is shown as text, not as markup
    expect(page.locator("#detail-text")).to_have_text("<b>nicht fett</b>")
    country(page, "Schweden").click()
    expect(page.locator("#detail-text")).to_have_text("Ben war noch nicht hier.")
    expect(country(page, "Schweden")).not_to_have_class("country visited selected")


def test_the_admin_edits_someone_elses_map(page, live_server):
    login(page, live_server, "Anna", "admin-pass")
    page.click("#people button:has-text('Clara')")
    country(page, "Tschechien").click()
    expect(page.locator("#detail-who")).to_have_text("Hier war Clara")
    expect(page.locator("#people button:has-text('Clara') .count")).to_have_text("1")


@pytest.mark.parametrize("projection", ["equalEarth", "un", "mercator"])
def test_every_projection_draws_the_world(page, live_server, projection):
    login(page, live_server, "Ben", "ben-pass")
    page.click(f"[data-projection={projection}]")
    box = page.locator(".sphere").bounding_box()
    assert box["width"] > 400 and box["height"] > 400
    # Antarctica stays inside the frame, which Mercator would otherwise blow up
    antarctica = country(page, "Antarktika").bounding_box()
    assert antarctica is None or antarctica["y"] + antarctica["height"] <= box["y"] + box["height"] + 1
    page.reload()
    page.wait_for_selector(".country")
    expect(page.locator(f"[data-projection={projection}]")).to_have_attribute("aria-pressed", "true")


def test_equal_earth_is_the_default(page, live_server):
    login(page, live_server, "Ben", "ben-pass")
    expect(page.locator("[data-projection=equalEarth]")).to_have_attribute("aria-pressed", "true")


def test_a_saved_note_shows_its_links_until_edited(page, live_server):
    login(page, live_server, "Ben", "ben-pass")
    country(page, "Schweden").click()
    page.fill("#detail-note", "Mittsommer https://example.org/")
    expect(page.locator("#detail-status")).to_have_text("Gespeichert")
    page.click("#detail .close")
    country(page, "Schweden").click()
    expect(page.locator("#detail-note")).to_be_hidden()
    expect(page.locator("#detail-text a")).to_have_attribute("href", "https://example.org/")
    page.click("#detail-edit")
    expect(page.locator("#detail-note")).to_be_focused()
    expect(page.locator("#detail-note")).to_have_value("Mittsommer https://example.org/")


def test_the_country_list_shows_flags(page, live_server):
    login(page, live_server, "Ben", "ben-pass")
    country(page, "Schweden").click()
    expect(page.locator("#visits .country-name")).to_have_text("🇸🇪Schweden")
    expect(page.locator("#detail-name")).to_have_text("🇸🇪 Schweden")


def test_people_are_ranked_by_how_many_countries_they_have(page, live_server):
    login(page, live_server, "Clara", "clara-pass")
    expect(page.locator("#people button")).to_have_text(["Alle0", "Anna0", "Ben0", "Clara0"])
    country(page, "Schweden").click()
    expect(page.locator("#people button")).to_have_text(["Alle1", "Clara1", "Anna0", "Ben0"])


def test_the_family_view_colours_by_how_many_were_there(page, live_server):
    login(page, live_server, "Anna", "admin-pass")
    for name in ["Anna", "Ben", "Clara"]:
        page.click(f"#people button:has-text('{name}')")
        country(page, "Schweden").click()
    page.click("#people button:has-text('Ben')")
    country(page, "Finnland").click()
    page.fill("#detail-note", "Helsinki https://example.org/")
    expect(page.locator("#detail-status")).to_have_text("Gespeichert")

    page.click("#people button:has-text('Alle')")
    expect(page.locator("#people button[aria-current=true]")).to_have_text("Alle2")
    expect(country(page, "Schweden")).to_have_class("country heat-3")
    expect(country(page, "Finnland")).to_have_class("country selected heat-1")
    expect(page.locator("#legend span")).to_have_text(["1", "2", "alle"])
    expect(page.locator("#visits .country-name")).to_have_text(["🇸🇪Schweden", "🇫🇮Finnland"])
    expect(page.locator("#visits p")).to_have_text(["alle", "Ben"])

    # read-only, even for the admin, and shows everyone with their note
    country(page, "Finnland").click()
    expect(page.locator("#detail-visited")).to_be_hidden()
    expect(page.locator("#detail-note")).to_be_hidden()
    expect(page.locator("#detail-text .visitor")).to_have_text(["BenHelsinki example.org"])
    country(page, "Polen").click()
    expect(page.locator("#detail-text")).to_have_text("Hier war noch niemand.")
    expect(country(page, "Polen")).to_have_class("country selected")

    page.click("#people button:has-text('Ben')")
    expect(page.locator("#legend")).to_be_hidden()
    expect(country(page, "Finnland")).to_have_class("country visited")


def state_shape(page, name):
    return page.locator(f".country:has(title:text-is('{name}'))")


def test_the_usa_view_splits_the_country_into_states(page, live_server):
    login(page, live_server, "Ben", "ben-pass")
    expect(page.locator("#region")).to_have_attribute("aria-pressed", "false")
    expect(state_shape(page, "Kalifornien")).to_have_count(0)

    page.click("#region")
    expect(country(page, "Vereinigte Staaten")).to_have_count(0)
    expect(state_shape(page, "Kalifornien")).to_have_count(1)
    expect(page.locator("#list-title")).to_have_text("Ben: 0 Staaten")
    # the traditional USA map: only the states, Alaska and Hawaii moved in below
    expect(country(page, "Kanada")).to_have_count(0)
    expect(page.locator(".projection")).to_be_hidden()
    texas = state_shape(page, "Texas").bounding_box()
    alaska = state_shape(page, "Alaska").bounding_box()
    hawaii = state_shape(page, "Hawaii").bounding_box()
    assert texas["width"] > 150
    assert alaska["y"] > texas["y"] and hawaii["y"] > texas["y"]
    assert alaska["x"] < texas["x"] and hawaii["x"] < texas["x"] + texas["width"]

    # marking a state marks the country as well
    state_shape(page, "Kalifornien").click()
    page.fill("#detail-note", "Highway 1")
    expect(page.locator("#detail-status")).to_have_text("Gespeichert")
    expect(page.locator("#list-title")).to_have_text("Ben: 1 Staat")
    expect(page.locator("#people button[aria-current=true]")).to_have_text("Ben1")

    page.reload()
    page.wait_for_selector(".country")
    expect(page.locator("#region")).to_have_attribute("aria-pressed", "true")
    page.click("#region")
    expect(page.locator(".projection")).to_be_visible()
    expect(page.locator("#list-title")).to_have_text("Ben: 1 Land")
    expect(country(page, "Vereinigte Staaten")).to_have_class("country visited")


def test_the_family_view_counts_states_in_the_usa_view(page, live_server):
    login(page, live_server, "Anna", "admin-pass")
    page.click("#region")
    for name in ["Anna", "Ben"]:
        page.click(f"#people button:has-text('{name}')")
        state_shape(page, "Texas").click()
    page.click("#people button:has-text('Alle')")
    expect(page.locator("#people button[aria-current=true]")).to_have_text("Alle1")
    expect(state_shape(page, "Texas")).to_have_class("country selected heat-2")
