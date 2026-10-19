# Nonton repository instructions

- Communicate with the user in Russian. Keep `docs/CODEX_PROJECT_MASTER_PROMPT.md` and `docs/CODEX_RESUME_PROMPT.md` in English.
- Read [the project master prompt](docs/CODEX_PROJECT_MASTER_PROMPT.md) and [live status](docs/PROJECT_STATUS.md), then inspect actual code, Git state and execution evidence. Historical task lists are not current instructions to rerun experiments.
- Work on the existing 64-day sales forecasting system. Canonical runtime is `src/runtime.py`; CLI is `python -m src.cli`; API is `app/main.py`. Share validation/features/inference rather than making separate applications.
- `config/runtime.json` explicitly selects the active release. Preserve `nonton-v1` unless an intentional, tested model-selection decision changes it. `bundles/equal4-rc1` supports D/W/S/A and `equal4:P1`; three Boosters produce four representations, with S sharing D/W.
- Official output: `date,warehouse_name,article,quantity`, 64 consecutive days after the last sales date, full 11×799 grid (562496 rows), unique keys, finite nonnegative quantities. Preserve identifiers as strings.
- Serving uses all supplied history, minimum 180 calendar days; cutoff is max sales date. Future targets/stock cannot become features. Corrected feature membership comes only from supplied sales rows, including zero sales. Catalog-known IDs unavailable to the corrected feature model receive zero; input IDs outside the output catalog are rejected.
- Threshold remains `<0.25 -> 0`, applied after blending. Do not enable integer rounding or change weights under a cleanup label. Incumbent and corrected categorical encoders are incompatible.
- Protect model artifacts, original data, official scorer, prior releases and research evidence. Six incumbent files are source-bound: `src/data.py`, `src/features.py`, `src/baselines.py`, `src/predict.py`, `src/submission.py`, `src/artifacts.py`. Candidate source bindings are enumerated by `src.runtime.RUNTIME_SOURCES`. Preserve bytes and feature ordering. Do not disable integrity checks or refresh hashes to conceal drift; a deliberate new artifact contract needs provenance and regression evidence.
- Keep runtime/training/dev/research dependency groups separate. Use existing pip locks; preserve numerical pins unless a migration is explicitly in scope. `.gitattributes` disables newline normalization because hashes bind exact bytes. Large artifacts use Git LFS; never commit datasets, credentials, environments, external checkouts or generated extraction copies.
- Prefer small explicit functions, useful boundary type hints, clear exceptions and existing structured CLI/API errors. Keep logs free of secrets. Do not copy unlicensed external code. Only one user-provided external repository was confirmed; do not invent a second integration.
- Before changing behavior, preserve a reference and compare identical inputs. Run appropriate tests after changes. Before a release use the commands below, plus actual model/API/Docker verification when affected. Mocked tests cannot replace real-model acceptance.

```powershell
.venv_consolidated/Scripts/python.exe -X utf8 -m src.cli test -- tests reports/qa/check_backend_independent.py integration/test_catalog_policy.py integration/test_ensemble_engine.py -q
.venv_consolidated/Scripts/python.exe -m pip check
.venv_consolidated/Scripts/python.exe -m ruff check src app
.venv_consolidated/Scripts/python.exe -m deptry .
```

- Docker/API changes require real offline/API parity, network-disabled inference, complete grid, cache/error/repeat/restart checks and measured resource limits. See the master prompt for exact build/test commands and private input prerequisites.
- Use native subagents for independent useful tasks with non-overlapping ownership; disclose unavailable delegation. Verify outputs yourself. Seek peer review for consequential ML/release changes and instruction changes; author review is not external certification.
- Report measured facts, hypotheses and blockers separately. Never fabricate test runs, remote pushes, untouched holdouts, leaderboard scores or future superiority. Update `docs/PROJECT_STATUS.md` and the execution log after meaningful work. Keep frozen release evidence immutable; new Git/documentation revisions are separate from the archived release.
