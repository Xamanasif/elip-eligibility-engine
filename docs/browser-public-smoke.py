"""Check public reads, isolated previews and the evidence export in Chromium."""
import json
import os
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


URL = os.getenv("ELIP_TEST_URL", "http://127.0.0.1:8766/")
PROFILE_URL = urljoin(URL, "/api/profile")
SCREENSHOTS = Path(__file__).resolve().parent / "screenshots"


def navigate(page, name):
    page.get_by_role("navigation", name="Main navigation").get_by_role(
        "button", name=name, exact=True
    ).click()


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.getenv("ELIP_CHROMIUM_PATH"))
    page = browser.new_page(accept_downloads=True, viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL)
    expect(page.get_by_text("0 verified vacancies")).to_be_visible()
    expect(page.get_by_role("button", name="Needs confirmation 21")).to_be_visible()
    assert page.request.get(PROFILE_URL + "?include_mode=true").json()["mode"] == "read_only"

    page.screenshot(path=SCREENSHOTS / "public-desktop.png")
    page.get_by_role("button", name="All 31", exact=True).click()
    search = page.get_by_role("searchbox", name="Search vacancies", exact=True)
    search.fill("Agoda")
    expect(page.get_by_text("1 of 31 shown", exact=True)).to_be_visible()
    page.get_by_role("button", name="Clear filters", exact=True).click()
    expect(search).to_have_value("")
    page.get_by_role("button", name="Review 21 unresolved", exact=True).press("Enter")
    expect(page.get_by_role("heading", name="Needs confirmation", exact=True)).to_be_focused()
    expect(page.get_by_role("button", name="Needs confirmation 21", exact=True)).to_have_attribute("aria-pressed", "true")

    page.get_by_role("button", name="Closed 1", exact=True).click()
    with page.expect_download() as download:
        page.get_by_role("button", name="Download evidence", exact=True).click()
    report = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert report["dataset"] == "audit"
    assert report["view"] == "review"
    assert report["as_of"] == "2026-11-27"
    assert report["total_cards"] == 31
    assert report["displayed_cards"] == 1
    assert [row["id"] for row in report["vacancies"]] == ["A10"]
    assert report["vacancies"][0]["evidence"]
    assert "profile" not in report

    page.get_by_role("combobox", name="Dataset", exact=True).select_option("synthetic")
    expect(page.get_by_text("Synthetic test data", exact=True)).to_be_visible()
    before = page.request.get(PROFILE_URL).json()
    navigate(page, "Candidate profile")
    expect(page.get_by_label("Duration (months)")).to_have_value("6")
    page.get_by_label("Duration (months)").fill("3")
    page.get_by_role("button", name="Apply preview", exact=True).click()
    expect(page.get_by_text("Profile preview applied.", exact=True)).to_be_visible()
    page.get_by_role("button", name="View matches", exact=True).click()
    expect(page.get_by_text("0 verified vacancies")).to_be_visible()
    assert page.request.get(PROFILE_URL).json() == before

    other = browser.new_page()
    other.goto(URL)
    navigate(other, "Candidate profile")
    expect(other.get_by_label("Duration (months)")).to_have_value("6")
    page.reload()
    navigate(page, "Candidate profile")
    expect(page.get_by_label("Duration (months)")).to_have_value("6")
    phone = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    phone.goto(URL)
    expect(phone.get_by_role("button", name="Download evidence", exact=True)).to_be_enabled()
    assert phone.evaluate("document.documentElement.scrollWidth === innerWidth")
    phone.screenshot(path=SCREENSHOTS / "public-mobile.png")
    navigate(phone, "Guided demo")
    expect(phone.get_by_role("heading", name="Guided demo", exact=True)).to_be_visible()
    assert not errors, errors
    browser.close()

print("Public browser checks passed: fixed audit, queue navigation, filter reset, evidence download, isolated profile preview and mobile navigation.")
