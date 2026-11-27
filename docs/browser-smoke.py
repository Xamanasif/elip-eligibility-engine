"""Exercise the dashboard in Chromium against a server with a disposable database."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright

DOCS = Path(__file__).resolve().parent
URL = os.getenv("ELIP_TEST_URL", "http://127.0.0.1:8765/")
PROFILE_URL = urljoin(URL, "/api/profile")
SHOTS = DOCS / "screenshots"
SHOTS.mkdir(exist_ok=True)
checks = []
page_errors = []


def open_page(browser, width=1440, height=1000, mobile=False):
    page = browser.new_page(viewport={"width": width, "height": height}, is_mobile=mobile, has_touch=mobile)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.goto(URL)
    expect(page.get_by_role("heading", name="Verified shortlist")).to_be_visible()
    return page


def nav(page, name):
    page.get_by_role("navigation", name="Main navigation").get_by_role("button", name=name, exact=True).click()


def outcome(page, name):
    page.get_by_role("group", name="Eligibility categories").get_by_role(
        "button", name=re.compile("^" + re.escape(name) + r" \d+$")
    ).click()


def dialog(page):
    return page.get_by_role("dialog")


def save_profile(page):
    page.get_by_role("button", name="Save profile", exact=True).click()
    expect(page.get_by_text("Profile saved.", exact=True)).to_be_visible()


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.getenv("ELIP_CHROMIUM_PATH"), args=["--no-sandbox"])
    page = open_page(browser)

    expect(page.get_by_text("0 verified vacancies")).to_be_visible()
    expect(page.get_by_text("No real audit vacancy had enough verified information", exact=False)).to_be_visible()
    expect(page.locator(".results-panel .job-row")).to_have_count(21)
    actual_scores = [float(s) for s in page.locator(".results-panel .score").all_text_contents()]
    assert actual_scores == sorted(actual_scores, reverse=True)
    expect(page.get_by_role("img", name=re.compile("full dataset.*31 cards.*Needs confirmation: 21.*Ineligible: 9.*Closed: 1"))).to_be_visible()
    page.screenshot(path=SHOTS / "dashboard-desktop.png")
    checks.append("Audit review shows zero verified jobs, 21 ranked unresolved jobs and an accessible decision chart.")

    outcome(page, "All")
    expect(page.locator(".results-panel .job-row")).to_have_count(31)
    expect(page.locator(".duplicate-group")).to_have_count(2)
    page.get_by_role("checkbox", name="Group possible duplicates").uncheck()
    expect(page.locator(".duplicate-group")).to_have_count(0)
    expect(page.locator(".results-panel .job-row")).to_have_count(31)
    page.get_by_role("checkbox", name="Group possible duplicates").check()
    for label, count in [("Eligible", 0), ("Needs confirmation", 21), ("Ineligible", 9), ("Closed", 1)]:
        outcome(page, label)
        expect(page.locator(".results-panel .job-row")).to_have_count(count)
    checks.append("All 31 rows and the four outcome filters retain their original audit counts. Grouping preserves both members of each pair.")

    outcome(page, "All")
    page.get_by_role("combobox", name="Filter country").select_option("MY")
    expect(page.locator(".results-panel .job-row")).to_have_count(5)
    page.get_by_role("combobox", name="Filter work mode").select_option("onsite")
    expect(page.locator(".results-panel .job-row")).to_have_count(5)
    page.get_by_role("searchbox", name="Search vacancies").fill("not-a-role")
    expect(page.get_by_role("heading", name="No vacancies to show")).to_be_visible()
    page.get_by_role("button", name="Show all vacancies").click()
    page.get_by_role("combobox", name="Sort vacancies").select_option("employer")
    employers = [s.strip() for s in page.locator(".job-company").all_text_contents()]
    page.get_by_role("checkbox", name="Group possible duplicates").uncheck()
    sorted_employers = [s.split("Possible duplicate")[0].strip().casefold() for s in page.locator(".job-company").all_text_contents()]
    assert sorted_employers == sorted(sorted_employers) and len(employers) == 31
    page.get_by_role("searchbox", name="Search vacancies").fill("CommerceIQ")
    expect(page.locator(".results-panel .job-row")).to_have_count(2)
    expect(page.locator(".duplicate-group")).to_have_count(0)
    checks.append("Search, country and work-mode filters, employer sorting and empty-result reset work. Distinct CommerceIQ postings stay separate.")

    page.get_by_role("searchbox", name="Search vacancies").fill("Google")
    first = page.get_by_role("button", name="Forward Deployed Engineer Intern, 2027", exact=True)
    first.focus()
    first.press("Enter")
    expect(dialog(page)).to_be_visible()
    expect(dialog(page).get_by_text("Academic stage", exact=True)).to_be_visible()
    expect(dialog(page).get_by_role("heading", name="Source evidence")).to_be_visible()
    expect(dialog(page).get_by_role("link", name="Open source").first).to_have_attribute("href", re.compile(r"^https://"))
    expect(dialog(page).get_by_text("Recommended next step")).to_be_visible()
    page.screenshot(path=SHOTS / "vacancy-evidence.png")
    dialog(page).get_by_role("button", name=re.compile("^A02")).click()
    expect(dialog(page).get_by_role("heading", name="Forward Deployed Engineer Internship")).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog(page)).to_have_count(0)
    expect(first).to_be_focused()
    checks.append("Keyboard opens evidence, follows the paired vacancy without merging decisions, and Escape restores the original focus.")

    nav(page, "Baseline ranking")
    expect(page.locator(".results-panel .job-row")).to_have_count(10)
    assert [float(s) for s in page.locator(".results-panel .score").all_text_contents()] == sorted(
        [float(s) for s in page.locator(".results-panel .score").all_text_contents()], reverse=True)
    page.screenshot(path=SHOTS / "baseline-ranking.png")
    checks.append("The baseline exposes its original top ten and is kept separate from the verified shortlist.")

    nav(page, "Candidate profile")
    original = page.request.get(PROFILE_URL).json()["profile"]
    expect(page.get_by_role("group", name="Degree 1")).to_be_visible()
    expect(page.get_by_role("group", name="Degree 2")).to_be_visible()
    page.get_by_role("button", name="Add degree", exact=True).click()
    third = page.get_by_role("group", name="Degree 3")
    third.get_by_label("Degree level").select_option("masters")
    third.get_by_label("Field of study").fill("Computer Science")
    third.get_by_label("Completed").check()
    for label, value in [("Skills", "pytest"), ("Preferred roles", "site reliability"), ("Allowed cities", "Bengaluru")]:
        page.get_by_label(label, exact=True).fill(value)
        page.get_by_label(label, exact=True).press("Enter")
        expect(page.get_by_role("button", name=f"Remove {value} from {label}")).to_be_visible()
    page.get_by_label("Allowed countries", exact=True).fill("US")
    page.get_by_role("button", name="Add to Allowed countries").click()
    page.get_by_label("Allowed work modes", exact=True).select_option("conditional_remote")
    page.get_by_label("Industry experience (months)").fill("12")
    page.get_by_label("Earliest start").fill("2027-01-05")
    page.get_by_label("Expected monthly stipend (INR)").fill("35000")
    save_profile(page)
    page.reload()
    nav(page, "Candidate profile")
    expect(page.get_by_role("group", name="Degree 3").get_by_label("Field of study")).to_have_value("Computer Science")
    expect(page.get_by_label("Expected monthly stipend (INR)")).to_have_value("35000")
    expect(page.get_by_role("button", name="Remove pytest from Skills")).to_be_visible()
    expect(page.get_by_label("Earliest start")).to_have_value("2027-01-05")
    page.get_by_role("button", name="Remove degree 3").click()
    page.get_by_role("button", name="Remove pytest from Skills").click()
    expect(page.get_by_role("group", name="Degree 3")).to_have_count(0)
    page.screenshot(path=SHOTS / "candidate-profile.png", full_page=True)
    save_profile(page)
    restored = page.request.get(PROFILE_URL).json()
    response = page.request.put(PROFILE_URL, data={"version": restored["version"], "profile": original})
    assert response.ok
    page.reload()
    checks.append("Multiple degree rows, chip entry/removal, dropdowns, dates, experience and stipend save through FastAPI and persist across refresh.")

    page.get_by_role("combobox", name="Dataset", exact=True).select_option("synthetic")
    expect(page.locator(".shortlist .job-row")).to_have_count(1)
    nav(page, "Candidate profile")
    page.get_by_label("Duration (months)", exact=True).fill("5")
    nav(page, "Match review")
    nav(page, "Candidate profile")
    expect(page.get_by_label("Duration (months)", exact=True)).to_have_value("5")
    save_profile(page)
    nav(page, "Match review")
    expect(page.locator(".shortlist .job-row")).to_have_count(0)
    nav(page, "Candidate profile")
    page.get_by_label("Duration (months)", exact=True).fill("6")
    save_profile(page)
    nav(page, "Match review")
    expect(page.locator(".shortlist .job-row")).to_have_count(1)
    checks.append("Profile drafts survive navigation, and a saved duration change recomputes the synthetic shortlist.")

    nav(page, "Guided demo")
    cases = [
        ("Infineon", "Country requirement catches five mismatches", 5),
        ("Agoda", "Official status takes priority", 1),
        ("Celonis", "The job type must fit", 1),
        ("Google", "Academic stage and possible duplication", 2),
        ("CommerceIQ", "An open signal still leaves questions", 2),
        ("Synthetic", "A fully verified fixture reaches the shortlist", 1),
    ]
    for name, title, count in cases:
        page.get_by_role("navigation", name="Demo steps").get_by_role("button", name=re.compile(name)).click()
        expect(page.get_by_role("heading", name=title)).to_be_visible()
        expect(page.locator(".demo-records > div")).to_have_count(count)
    expect(page.get_by_text("Synthetic test fixture", exact=True)).to_be_visible()
    expect(page.locator(".demo-records .badge")).to_have_text("Eligible")
    page.screenshot(path=SHOTS / "guided-synthetic-demo.png")
    page.get_by_role("button", name="Open synthetic matches").click()
    expect(page.get_by_text("Synthetic test data", exact=True)).to_be_visible()
    expect(page.locator(".shortlist .job-row")).to_have_count(1)
    page.get_by_role("combobox", name="Dataset", exact=True).select_option("regression")
    expect(page.get_by_text("Elip’s own posting", exact=True)).to_be_visible()
    page.locator(".results-panel .job-title").first.click()
    expect(dialog(page).get_by_role("heading", name="Compensation")).to_be_visible()
    expect(dialog(page).get_by_text("Internship stipend", exact=True)).to_be_visible()
    expect(dialog(page).get_by_text("PPO base salary", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    checks.append("All five audit scenarios and the clearly labelled synthetic eligible fixture render. The regression posting shows stipend and PPO pay separately.")

    error_page = browser.new_page()
    error_page.route("**/api/match", lambda route: route.fulfill(status=503, json={"detail": "Test-triggered outage."}), times=1)
    error_page.goto(URL)
    expect(error_page.get_by_role("alert")).to_contain_text("Test-triggered outage.")
    error_page.get_by_role("button", name="Try again").click()
    expect(error_page.get_by_role("heading", name="Verified shortlist")).to_be_visible()
    error_page.get_by_role("combobox", name="Dataset").select_option("synthetic")
    error_page.get_by_role("combobox", name="Dataset").select_option("audit")
    expect(error_page.get_by_text("0 verified vacancies")).to_be_visible()
    expect(error_page.get_by_text("21 of 31 shown")).to_be_visible()
    checks.append("A browser-injected 503 displays an error, retry recovers, and rapid dataset switches show the latest scope.")

    conflict_page = open_page(browser)
    nav(conflict_page, "Candidate profile")
    conflict_page.get_by_label("Expected monthly stipend (INR)").fill("38500")
    same = conflict_page.request.get(PROFILE_URL).json()
    assert conflict_page.request.put(PROFILE_URL, data=same).ok
    conflict_page.get_by_role("button", name="Save profile", exact=True).click()
    expect(conflict_page.get_by_role("alert")).to_contain_text("Profile changed")
    expect(conflict_page.get_by_label("Expected monthly stipend (INR)")).to_have_value("38500")
    conflict_page.get_by_role("button", name="Reload saved profile and discard edits").click()
    expect(conflict_page.get_by_label("Expected monthly stipend (INR)")).to_have_value(str(same["profile"]["expected_stipend_inr"]))
    checks.append("A stale profile version reports a conflict, preserves the draft, and reloads only after explicit action.")

    for width in [360, 390, 430, 768]:
        phone = open_page(browser, width, 844, mobile=width < 500)
        assert phone.evaluate("document.documentElement.scrollWidth === innerWidth")
        if width == 390:
            phone.screenshot(path=SHOTS / "dashboard-mobile.png")
        phone.locator(".results-panel .job-title").first.click()
        expect(dialog(phone)).to_be_visible()
        assert dialog(phone).evaluate("(el) => el.scrollWidth === el.clientWidth")
        if width == 390:
            phone.screenshot(path=SHOTS / "evidence-mobile.png")
        phone.keyboard.press("Escape")
        nav(phone, "Candidate profile")
        expect(phone.get_by_role("heading", name="Candidate profile", exact=True)).to_be_visible()
        assert phone.evaluate("document.documentElement.scrollWidth === innerWidth")
        phone.close()
        checks.append(f"{width}px viewport: review, evidence dialog, and profile have no horizontal overflow.")
    browser.close()
assert not page_errors, page_errors
print(json.dumps({"checks": checks, "browser_page_errors": page_errors}, indent=2))
