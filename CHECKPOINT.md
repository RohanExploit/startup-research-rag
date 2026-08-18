# CHECKPOINT — Start up V2

Snapshot to resume work. Last updated: **2026-08-15**. Prior overnight trail: `OVERNIGHT_LOG.md`; measured status: `PROJECT_STATE.md`.

---

## Current state (end of session 2026-08-15)
- **Branch:** `phase-1-routing` (active; carries all of today's close-out work).
- **Remote:** `origin` = **https://github.com/RohanExploit/startup-research-rag** (PRIVATE). First push done this session — all 4 branches pushed (`main`, `phase-1-routing`, `phase-1-retrieval-eval`, `upgrade-phase-0`).
- **Tests:** **227 passed, 1 skipped, 0 failed** (full `pytest -q`, ~34s warm). Hermetic, no live services required. (The 1 skip is a manual PDF-parsing diagnostic.)
- **Eval baseline (`tests/eval/baseline.json`, 46-Q golden set):** overall answer **60.87%**, route classification **84.78%**. Per-route: TABULAR 95.5% (21/22), GLOBAL 42.9% (3/7), FACT 27.3% (3/11), LOCAL 16.7% (1/6).
- **Data (tenant_1):** 369 students; 334 pass / 35 fail; pass rate 90.5%; min SGPA 5.18; failed ≥4 subjects = 7.
- **Model rules (unchanged):** `qwen3:4b-instruct-2507-q4_K_M`, `num_ctx 2048`, `temperature 0`. Backend `api.main:app` on :8000; dashboard = Next.js.
- **PII:** student-PII spreadsheet fully removed from git (tracking + history); file kept on disk under retention hold. Details below.

---

## THIS SESSION — what we did

### Task A — Swarm close-out & first push to remote

**Phase 1 (4 parallel read-only verification agents):**
1. **Demo path** — ran the 5 headline queries against the live backend. **All 5 PASS**, all route TABULAR via deterministic SQL templates, cross-checked against DuckDB:
   - "gaikwad rohan result" → GAIKWAD ROHAN VIJAY, roll 23067571242048, FAIL, 8 subjects.
   - "students who failed at least 4 subjects" → 7 students.
   - "overall pass percentage" → 90.5% (334/369).
   - "which subject has the most failures" → BTCOC502 (16 failures).
   - "top 5 students by SGPA" → DHUMAL ANUSHKA 8.82, NADAF YASHARA 8.80, TIRTH VAISHNAVI 8.68, BHAIRAMADAGI 8.66, BHANGE 8.64.
   - Note: OVERNIGHT_LOG's old "failed≥4 = 10 / ≥2 = 77" figures were stale (pre re-ingest); current DB truth is 7 / 16. Data change, not a bug.
2. **Test gate** — 227 passed / 1 skipped / 0 failed. Produced ordered commit plan.
3. **Secret scan (BLOCKING)** — found `SESSION-STUDENT-DETAILS-2.xlsx` tracked, containing raw student PII (names, DOB, parents, gender, **caste**, **12-digit Aadhaar**, mobile, email) — DPDP-sensitive. No other secrets tracked. `.gitignore` otherwise good. Noted user's own phone in `auth/allowlist.json` and email in `tests/eval/*.json` (own data, left as-is).
4. **PROJECT_STATE draft** — measured status snapshot.

**Phase 2 (sequential committer):**
- Untracked the PII xlsx (`git rm --cached`, file kept on disk), hardened `.gitignore` (`*.xlsx`/`*.csv`, `.env.*` + `!.env.example`).
- Landed 5 commits (see trail below), re-verified gate green.
- Added `PROJECT_STATE.md`.
- **PII history scrub:** made a safety backup bundle, then `git filter-branch --index-filter` rewrote **all 67 commits** to purge the xlsx blob from every commit. Verified gone from every object + off the remote tree. All commit hashes after `a14d255` changed.
- Created the private remote and pushed all branches; confirmed remote is PII-clean.

**Commit trail (post-scrub hashes, `phase-1-routing`):**
```
a7c15d1 docs: add PROJECT_STATE.md close-out snapshot
ac8fa4b refactor(dashboard): restyle UI with drawn icon set and shared table styling; fix grade badge colours
bdd3192 chore(eval): add Gate-1 ingestion validation log
89435a7 fix(retrieval): resolve student lookups by name/roll regardless of word order
ebb2139 security: stop tracking raw student PII spreadsheet
1cca0d6 feat(retrieval): FACT depth k=10, entity-link confidence gate, attribute routing  (prior HEAD)
```

### Task B — Elaborate real-world test plan (IN PROGRESS, planning done)
- Ran `/plan` in plan mode; 2 Explore agents mapped the existing test infra + full product surface.
- Scope decided with user: cover **(1) adversarial & messy input, (2) dashboard UI e2e, (3) weak-route + load stress**; deliverable = **automated tests + demo runbook**; structure = **two-tier** (hermetic CI + live manual gate).
- Plan approved and saved: `C:\Users\ACER\.claude\plans\purrfect-petting-lighthouse.md`.
- Build order: (1) hermetic tier `tests/scenarios/` + config, (2) demo runbook `docs/DEMO_RUNBOOK.md`, (3) adversarial eval set `tests/eval/adversarial_set.json`, (4) Playwright e2e `dashboard/e2e/`, (5) live gate `tests/live/`.
- **Status: nothing written yet** — was reading source files (`conftest.py`, `retrieval/intent.py`, `entity_link.py`, `run_eval.py`) to bind tests to real signatures when this checkpoint was requested. Locked `golden_set.json` will NOT be mutated (contamination guard); weak routes treated as diagnostic, not gating.

---

## Results this session (headline numbers)
- Tests: **227 / 1 skip / 0 fail** (green before and after all commits).
- Eval: **60.87%** answer, **84.78%** route (unchanged baseline; no eval work done this session).
- Demo: **5/5** headline queries pass, live, DB-verified.
- Security: **1 PII file** scrubbed from all history; **0** secrets/tokens on remote; remote verified clean.
- Git: repo pushed to its **first remote** (private).

---

## Pending / next
1. **Execute the test plan** (Task B) — start with the hermetic `tests/scenarios/` tier + `pyproject.toml` marker registration, then the runbook. Plan file has the full breakdown.
2. **Optional history hygiene** — user's own phone (`auth/allowlist.json`) and email (`tests/eval/*.json`) are on the private remote; move to untracked config if the repo ever goes public.
3. **Weak routes** (from PROJECT_STATE): FACT 27.3%, LOCAL 1/6, GLOBAL churn — the "next 3 levers" if resumed.
4. The on-disk `SESSION-STUDENT-DETAILS-2.xlsx` remains under retention hold, gitignored — do not delete.

## Resume commands
```bash
cd "R:/Startup research/Start up V2"
git log --oneline -8                                   # review this session's commits
.venv312/Scripts/python.exe -m pytest -q               # full gate (expect 227 passed, 1 skipped)
.venv312/Scripts/python.exe -m pytest tests/scenarios -q   # (once Task B hermetic tier exists)
python tests/eval/run_eval.py --limit 5                # eval smoke (needs Ollama + tenant_1)
git remote -v                                          # origin = RohanExploit/startup-research-rag (private)
```
