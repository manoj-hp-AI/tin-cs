"""Offline checks of growth.source_gap_placements; no web requests and no model calls."""

import json
import re
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tin_lite.community import ContributedPackage, validate, validate_private_copy
from tin_lite.workflow_inputs import WorkflowInputError, normalize_workflow_inputs

ROOT = Path(__file__).parents[1]
KEY = "growth.source_gap_placements"
PACKAGE = ROOT / "workflow_packages" / KEY
SKILL = PACKAGE / "skills/source-gap-placements"
RESOURCE = SKILL / "VALIDATE.md"


@pytest.fixture(scope="module")
def check():
    # This exact reviewed repository resource runs inside the procedure sandbox. Never use
    # this loader for packages submitted to the qualification service.
    blocks = re.findall(r"```python\n(.*?)\n```", RESOURCE.read_text(), re.S)
    assert len(blocks) == 1
    namespace = {}
    exec(compile(blocks[0], str(RESOURCE), "exec"), namespace)  # noqa: S102 - reviewed fixture
    return SimpleNamespace(**namespace)


def pursue(number, *, host="roundups.example", **changes):
    """One synthetic, fully valid pursue page for a fictional soil-testing subscription."""
    page = {
        "url": f"https://{host}/best-soil-tests-{number}",
        "status": "pursue",
        "reason": "",
        "checked": "2026-09-24",
        "published": "2026-03-10",
        "options_count": 9,
        "competitors_listed": ["SoilKit"],
        "company_listed": False,
        "paid": False,
        "publisher_is_competitor": False,
        "route": {"kind": "form", "url": f"https://{host}/suggest-a-tool"},
        "ask": f"Please add Loam to the soil test list; it is a mail-in kit variant {number}.",
        "blurb": (
            f"Loam is a mail-in soil test for home gardeners that returns nutrient results "
            f"and a planting plan within five days, priced at $29 per kit. Variant {number}."
        ),
        "disclosure": "I'm the founder of Loam.",
        "blurb_facts": ["docs/pricing.md", "README.md"],
        "check_first": ["Confirm the form still accepts new tools."],
    }
    page.update(changes)
    return page


def other(url, status, reason, **changes):
    page = {
        "url": url,
        "status": status,
        "reason": reason,
        "checked": "2026-09-24",
        "published": "2026-01-05",
        "options_count": 8,
        "competitors_listed": ["SoilKit"],
        "company_listed": False,
        "paid": False,
        "publisher_is_competitor": False,
        "route": {"kind": "none", "url": ""},
    }
    page.update(changes)
    return page


@pytest.fixture
def ledger():
    return {
        "own_domains": ["loam.example"],
        "max_targets": 8,
        "opened": 7,
        "pages": [
            pursue(1),
            pursue(2, host="gardenlists.example"),
            pursue(3, host="growmore.example", route={"kind": "pr", "url": "https://g.example/pr"}),
            other("https://undated.example/soil", "hold", "UNDATED", published=None),
            other("https://noroute.example/soil", "hold", "NO_PATH"),
            other("https://paid.example/soil", "reject", "PAY_TO_PLAY", paid=True),
            other("https://old.example/soil", "reject", "STALE", published="2022-02-01"),
        ],
    }


def report(ledger):
    lines = ["# Source-gap placements: soil tests", "Status: complete", "## Company fact card"]
    lines += ["## Placement pack", "## Held pages", "## Rejected pages", "## Limits"]
    for page in ledger["pages"]:
        lines.append(page["url"])
        if page["status"] == "pursue":
            lines.append(page["blurb"])
    return "\n".join(lines)


def test_a_sound_ledger_passes_and_is_counted(check, ledger):
    assert check.check_ledger(ledger) == []
    assert check.counts(ledger) == {"opened": 7, "pursue": 3, "hold": 2, "reject": 2}


def test_zero_qualifying_pages_is_a_valid_honest_result(check, ledger):
    ledger["pages"] = [p for p in ledger["pages"] if p["status"] != "pursue"]
    ledger["opened"] = len(ledger["pages"])
    assert check.check_ledger(ledger) == []
    assert check.counts(ledger)["pursue"] == 0


def mutate(index, **changes):
    def apply(ledger):
        ledger["pages"][index].update(changes)

    return apply


def blurb(text):
    return mutate(0, blurb=text)


def drop(key):
    def apply(ledger):
        del ledger["pages"][0][key]

    return apply


@pytest.mark.parametrize(
    "break_it,expected",
    [
        (mutate(0, url="https://loam.example/blog"), "own domain"),
        (mutate(0, url="https://shop.loam.example/x"), "own domain"),
        (mutate(0, paid=True), "paid must be recorded as false"),
        (mutate(0, publisher_is_competitor=True), "publisher_is_competitor"),
        (mutate(0, company_listed=True), "company_listed"),
        (mutate(0, published="2022-02-01"), "within the last 24 months"),
        (mutate(0, published=None), "within the last 24 months"),
        (mutate(0, published="2027-01-01"), "within the last 24 months"),
        (mutate(0, published="March 2026"), "YYYY-MM-DD"),
        (mutate(0, route={"kind": "none", "url": ""}), "published route"),
        (mutate(0, route={"kind": "form", "url": "not a url"}), "route.url"),
        (mutate(0, options_count=2), "options_count"),
        (mutate(0, competitors_listed=[]), "competitors_listed"),
        (mutate(0, reason="MISFIT"), "no reason code"),
        (mutate(0, url="ftp://roundups.example/x"), "http(s)"),
        (
            blurb("Loam is the best soil test for gardeners who want a plan in five days."),
            "superlative",
        ),
        (blurb("Loam is a soil test."), "blurb must be 12-60 words"),
        (blurb("word " * 61), "blurb must be 12-60 words"),
        (drop("blurb_facts"), "blurb_facts"),
        (mutate(0, blurb_facts=["https://loam.example/pricing"]), "not web addresses"),
        (mutate(0, disclosure=""), "disclosure"),
        (mutate(0, ask=""), "ask"),
        (mutate(1, blurb=None), "blurb"),
        (
            mutate(5, reason="PAY_TO_PLAY", paid=False),
            "PAY_TO_PLAY is not supported by the recorded evidence",
        ),
        (
            mutate(6, reason="STALE", published="2026-06-01"),
            "STALE is not supported by the recorded evidence",
        ),
        (mutate(5, reason="MAYBE"), "reject reason"),
        (mutate(3, reason="UNDATED", published="2026-01-01"), "UNDATED needs published"),
        (
            mutate(4, reason="NO_PATH", route={"kind": "form", "url": "https://x.example"}),
            "NO_PATH needs route.kind none",
        ),
        (mutate(3, reason="SOMEDAY"), "hold reason"),
        (mutate(0, status="review"), "status must be one of"),
        (mutate(1, url="https://roundups.example/best-soil-tests-1"), "duplicate url"),
        (mutate(1, blurb="  ".join(pursue(1)["blurb"].split())), "duplicates another"),
    ],
)
def test_a_plausible_but_unusable_ledger_is_refused(check, ledger, break_it, expected):
    break_it(ledger)
    assert any(expected in problem for problem in check.check_ledger(ledger)), expected


def test_each_page_needs_its_own_evidence_not_just_a_tidy_shape(check, ledger):
    # A dossier that reads well but recommends a paid, competitor-owned, undated page.
    ledger["pages"][0].update(paid=True, publisher_is_competitor=True, published=None)
    problems = check.check_ledger(ledger)
    assert len(problems) >= 3


def test_no_more_than_two_pursue_pages_from_one_domain(check, ledger):
    ledger["pages"][2]["url"] = "https://roundups.example/best-soil-tests-3"
    ledger["pages"][1]["url"] = "https://roundups.example/best-soil-tests-2"
    assert any("at most 2 pursue pages" in p for p in check.check_ledger(ledger))


def test_pursue_pages_cannot_exceed_the_requested_maximum(check, ledger):
    ledger["max_targets"] = 3
    ledger["pages"].append(pursue(4, host="fourth.example"))
    ledger["opened"] += 1
    assert any("exceed max_targets" in p for p in check.check_ledger(ledger))


def test_every_opened_page_is_accounted_for_and_the_budget_holds(check, ledger):
    ledger["opened"] = 6
    assert any("opened must equal" in p for p in check.check_ledger(ledger))
    ledger["pages"] += [other(f"https://filler{i}.example/", "reject", "THIN") for i in range(20)]
    ledger["opened"] = len(ledger["pages"])
    assert any("at most 25" in p for p in check.check_ledger(ledger))


def test_the_business_must_state_its_own_site(check, ledger):
    ledger["own_domains"] = []
    assert any("own_domains" in p for p in check.check_ledger(ledger))


def test_a_matching_report_passes(check, ledger):
    assert check.check_report(ledger, report(ledger)) == []


@pytest.mark.parametrize(
    "edit,expected",
    [
        (lambda t: t.replace("Status: complete\n", ""), "Status"),
        (lambda t: t.replace("## Limits", ""), "## Limits"),
        (lambda t: t.replace("https://paid.example/soil", ""), "page missing"),
        (lambda t: t.replace("Variant 2.", "Variant two."), "blurb differs"),
    ],
)
def test_a_report_that_drifts_from_its_ledger_is_refused(check, ledger, edit, expected):
    problems = check.check_report(ledger, edit(report(ledger)))
    assert any(expected in problem for problem in problems)


async def test_the_package_loads_publicly_and_as_a_private_copy():
    package = ContributedPackage(key=KEY, path=PACKAGE)
    await validate(package)
    await validate_private_copy(package)


def manifest():
    return json.loads((PACKAGE / "workflow.json").read_text())["definition"]


def test_key_folder_skill_and_declared_files_agree():
    definition = manifest()
    assert definition["key"] == KEY == PACKAGE.name
    procedure = definition["procedure"]
    assert procedure["entry_skill"] == SKILL.name
    on_disk = {p.relative_to(PACKAGE).as_posix() for p in (PACKAGE / "skills").rglob("*.md")}
    assert set(procedure["skill_files"]) == on_disk
    header = (SKILL / "SKILL.md").read_text().split("---")[1]
    assert f"name: {SKILL.name}\n" in header
    assert definition["schedule_modes"] == ["on_demand"]
    assert procedure["sandbox"] == {
        "profile": "isolated",
        "egress": "fenced",
        "timeout_seconds": 1200,
    }


def test_every_input_is_bounded():
    schema = manifest()["input_schema"]
    for name, field in schema["properties"].items():
        if name == "project_id":
            continue
        if field["type"] == "string":
            assert "maxLength" in field, name
        if field["type"] == "array":
            assert "maxItems" in field and "maxLength" in field["items"], name
        if field["type"] == "integer":
            assert {"minimum", "maximum"} <= set(field), name


def test_inputs_apply_defaults_and_refuse_out_of_contract_values():
    schema = manifest()["input_schema"]

    def run(**inputs):
        return normalize_workflow_inputs(schema=schema, project_id=uuid4(), inputs=inputs)

    assert run(category="mail-in soil test kits") == {
        "category": "mail-in soil test kits",
        "buyer_questions": [],
        "competitors": [],
        "market": "",
        "max_targets": 8,
        "exclusions": "",
    }
    for bad in (
        {},
        {"category": ""},
        {"category": "x" * 201},
        {"category": "soil", "buyer_questions": ["q"] * 6},
        {"category": "soil", "competitors": ["c"] * 7},
        {"category": "soil", "competitors": ["c" * 101]},
        {"category": "soil", "max_targets": 2},
        {"category": "soil", "max_targets": 13},
        {"category": "soil", "project_id": str(uuid4())},
        {"category": "soil", "unknown": "value"},
    ):
        with pytest.raises(WorkflowInputError):
            run(**bad)
    with pytest.raises(WorkflowInputError):
        normalize_workflow_inputs(schema=schema, project_id=uuid4(), inputs=None)
    assert deepcopy(schema) == schema
