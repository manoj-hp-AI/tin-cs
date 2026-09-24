## What this workflow does

`growth.source_gap_placements` finds third-party roundups, directories, comparison posts and curated lists that already list a business's competitors but not the business. It opens and verifies each page, then delivers one report, `reports/SOURCE_GAP_PLACEMENTS.md`, that says which pages are worth pursuing, the exact ask and a listing blurb for each, which pages are on hold, and why every other opened page was rejected. Nothing is sent: no email, form, pull request or account.

## Who would run it

A founder or a one-person marketing team at a small company with a nameable category and a few known competitors, who wants to be found where buyers already look but has no time to check dozens of "best X" pages by hand.

## Why it is missing today

Tin can measure whether AI assistants recommend you (`visibility.audit`), write pages on your own site (`content.answer_page`, `content.public_article`) and email people from your own inbox history (`outreach.email_shortlist`). Nothing earns a place on other people's pages. `src/tin_lite/growth_plan_assets/programs.json` also rates platform/marketplace and earned-media coverage as partial, which is the gap this fills.

## How it works

It is a `codex.procedure` because the agent has to decide which pages to open next, with a small reviewed Python validator for the parts that can be checked mechanically.

1. **Preflight:** read the project files and build a company fact card, with a file path behind every fact. If the files cannot say what the business does and its own domain, stop with an incomplete report instead of guessing.
2. **Queries:** use the supplied buyer questions and competitors, or derive them and label them `(derived)` / `(inferred)`.
3. **Discover and verify:** open at most 25 pages. For each, record its visible date, options listed, competitors present, whether the business is already listed, whether placement is paid, who publishes it, and a published route (pull request, form or email).
4. **Decide:** the first matching rule wins: `ALREADY_LISTED`, `COMPETITOR_OWNED`, `PAY_TO_PLAY`, `THIN`, `STALE` (over 24 months), `MISFIT`, then Hold for `UNDATED`, `NO_PATH` or `OVERFLOW`, otherwise Pursue.
5. **Draft:** for each Pursue page, a one-sentence ask, a 12 to 60 word blurb in the page's own format using only facts from project files (paths cited), and an affiliation disclosure.
6. **Validate:** `VALIDATE.md` checks that the recorded evidence supports every status, blurbs are not duplicated or hype, at most two pages come from one domain, every opened page is accounted for, and the written report matches the ledger.

If few or no pages qualify, the report says so instead of lowering a rule.

Not included, for maintainers: no `PUBLIC_WORKFLOWS` registration, no `system` assignment (`organic-traffic` looks closest), and no change to `catalog.py` or any existing workflow. The 24-month freshness limit is a judgment call and easy to tighten.

## Inspiration

- Ahrefs' analysis of which page types ChatGPT cites found that recently updated "best X" lists are the most prominent, and that only about a third of its most-cited pages are ones a marketer can realistically influence: https://ahrefs.com/blog/chatgpts-most-cited-pages
- The practice of finding third-party pages that are cited for competitors but never for you and sorting them by how reachable they are. I based the reachability triage and the reject list on that idea, but the design here is my own.
- The repo's own coverage map (`programs.json`).

I also considered event and CFP scouting, a community rulebook for Reddit-style venues, podcast guest vetting, mining public "why I switched" stories, and marketplace listing packets. I chose this one because it works for any category, every row can be checked by opening a live page, and it needs no outbound action.

## Testing

- `uv run tin-lite validate-community`: all 5 packages valid; `--private --package growth.source_gap_placements` also passes.
- `uv run pytest tests/test_source_gap_placements.py`: 48 offline tests covering the manifest, input bounds and defaults, and the validator, including plausible-but-unusable ledgers (paid, competitor-owned, stale, undated, hype or duplicated blurbs, mislabeled rejects) and reports that drift from their ledger. I also disabled three validator rules on a scratch copy and confirmed the tests then failed.
- `python -m tin_lite.workflow_qualification_cli check ...` passes, including with synthetic outputs, where good reports pass every assertion and a wrong report fails. This checks the assertion mechanics only, not real report quality.
- `ruff format --check`, `ruff check` and `lint-imports` are clean. Full `pytest -n auto`: 2168 passed, 644 skipped, 3 failing (see below).

**Not tested:** I did not run the workflow on hosted Tin. I did not verify that a contributed procedure receives web search or that the validator block executes in the procedure sandbox, and the qualification cases and rubric are author-proposed and unreviewed.

## Issues encountered

- Three tests in `tests/test_scheduled_reviews.py` fail or error in my environment because the Temporal test-server download returned HTTP 403. They fail identically on the untouched `main` baseline and are unrelated to this change.
- The first review of `SKILL.md` found two ambiguities (what an incomplete preflight report must contain, and how `market` affects queries). I fixed both and re-ran the checks.
- The validator's superlative filter also flags "best" in harmless phrasing such as "best suited". I kept it because rewording is cheap and generic hype was the risk I most wanted to catch.
- The workflow finds pages through search, so it can miss pages that AI assistants cite but that do not rank in Google. The report's Limits section says it does not show any assistant cites a page.
