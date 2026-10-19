# Architecture audit before consolidation

Agent A, 19 October 2026. Read-only implementation audit; no training or model promotion performed. Only this report and `architecture_import_graph.json` were created. The graph is an AST inventory, not evidence that all import paths were executed.

## Concrete recommendation

Keep the incumbent byte-bound preprocessing files intact. Introduce a runtime facade under `src/` that selects a versioned strategy from explicit bundle metadata, and make the existing `app.predictor.Predictor` call that facade. Keep one FastAPI app, one validator layer, one forecast grid validator, one cache, and one lock policy. Default selection should remain explicit and documented; adding a selectable ensemble does not by itself establish scientific superiority.

The minimum new runtime boundary consists of a dispatcher/bundle contract module, an ensemble inference module, and runtime-only catalog/allocation helpers. File names are an implementation choice. This boundary must not import `integration`, `research`, `scripts`, or training modules. The old experiment programs can remain historical or become thin wrappers pointing to the canonical implementation, provided their original source snapshots remain available to verify old manifests.

## Observed dependency chains

| Entry point | Current chain | Consequence |
|---|---|---|
| API | `app.main -> app.predictor -> src.predict -> src.data/features/baselines/submission/artifacts` | Existing inference is already independent of experiment directories. Preserve this property. |
| Experimental CLI | `integration.experimental_predict -> integration.corrected_models/catalog_policy/ensemble_engine` | CLI accepts paths and reloads all three models for each call; this is not a reusable loaded API strategy. |
| Components | `integration.corrected_models -> src.train.PARAMS` | Training and inference occupy one module; importing inference brings training code unnecessarily. |
| Allocation | `integration.corrected_models -> scripts.architecture_experiments -> scripts.qa_analysis`, `src.metrics`, `psutil`, training and research runners | Importing five useful pure functions also imports broad experiment infrastructure. |
| Catalog | `integration.catalog_policy -> catalog_audit/first_observed.csv` through a cached optional default | Inference must always derive first observation from uploaded sales and must never invoke that historical-file fallback. |

`scripts.architecture_experiments` supplies exactly `BUCKETS`, `weekly_frame`, `weekday_weights`, `allocate_buckets`, and `warehouse_shares` to corrected inference. Extract their arithmetic and order unchanged into the runtime. Keep `fit_components`, `origins_for`, parameter selection, metrics, source provenance analysis, and experiment loops outside the serving import graph.

## Integrity constraints observed

`src.artifacts.SOURCE_FILES` is exactly `data.py`, `features.py`, `baselines.py`, `predict.py`, `submission.py`, and `artifacts.py`. Incumbent loading recomputes their byte hashes and dependency versions. Moving, reformatting, or replacing them invalidates the incumbent even if the resulting arithmetic is equivalent. The new dispatcher should wrap `src.predict.load_bundle/predict_64`, not edit those files or silently rewrite the incumbent manifest.

The existing experimental manifest binds eight source files including `scripts/architecture_experiments.py` and `src/train.py`, plus three text models and config. All 12 recorded file/source hashes were recomputed and matched during this audit; booleans are in the import graph JSON. This check establishes byte agreement only. It does not independently establish training provenance, quality, or API readiness.

The experimental config separately binds the adapter hash, dependencies, weights, policies and category encodings. Its loader verifies model feature names. However, the legacy experimental loader does not define a robust new public schema: it iterates supplied manifest file names, lacks an exact required-file set, and has no path containment check or independent canonical manifest identity. Do not broaden its use as the shared API loader unchanged.

Keep old experimental manifests, models and original source snapshots as historical artifacts. Create a distinct migrated bundle manifest that records parent manifest/config/model hashes, the new runtime source hashes, exact required artifact names, validated schema/strategy/candidate, selected weights and postprocessing, dependency versions, catalogs and feature schemas. Reusing the identical model bytes requires no retraining. Bind the new runtime manifest to the new source; do not claim the old source manifest validates migrated code.

## Shared strategy contract

Provide a loader returning one bundle-shaped object with `config`, `catalogs`, `manifest` and loaded strategy state. A single `predict(sales, stock, bundle)` returns the existing four-column frame. The incumbent adapter delegates unchanged. The ensemble adapter receives already parsed DataFrames, derives first-observed sales membership, builds the panel with the selected bundle output catalog, computes components once, aligns by identity and applies the declared mixture/policy. The CLI should call that same function instead of retaining a separate CSV-only algorithm.

Strategy dispatch must reject unknown metadata. It should not infer a strategy from a convenient directory name or fall back silently after verification failure. Retain the original `MODEL_DIR` path mechanism or document an explicit startup selector; avoid creating separate routes or a second application. The effective bundle ID and candidate must be visible in diagnostics and cache metadata. One loaded process should own one immutable selection; changing bundle selection after a cached result requires clear cache invalidation.

`Predictor` currently assumes a dictionary bundle and deep-copies it. A minimal facade preserves that interface and existing test injection. Avoid embedding mutable startup selection in request handlers. Do not deep-copy an additional second set of Boosters merely to satisfy this interface; assess the current copy behavior when introducing a loaded ensemble.

## Duplication that can be removed safely

- Batch horizon inference is present in `src.predict.predict_panel` and `integration.corrected_models.predict_components`. Preserve the incumbent implementation to retain its hash contract; the migrated ensemble can have its own small batch helper. Abstracting both now would unnecessarily disturb the incumbent release.
- CSV parsing, minimum-history checks and input handling exist in the experimental adapter and API validators. Canonical model inference should accept DataFrames; the API retains its stricter public CSV validation. CLI validation should call the same public validator if its documented contract is intended to match the API.
- Output grid validation and deterministic sorting already belong to `Predictor`; reuse them for both strategies. The runtime must also return a well-defined grid for offline callers.
- Combination and postprocessing should have one canonical runtime implementation. The original historical source can be retained as evidence with a clear frozen label, rather than staying an independently maintained active engine.

The API rejects identifiers outside its fixed output catalog. The ensemble's zero fallback concerns IDs in that fixed output catalog not observed in supplied sales; it does not authorize arbitrary new external IDs. Retain that distinction in documentation and tests.

## Migration validation required

1. Record protected incumbent/source/model hashes before edits. Verify incumbent loading and a saved forecast remain equal after edits.
2. Replay migrated component outputs and selected equal4 postprocessing against the original experimental implementation on the same 180-day input; compare keys and values, not CSV formatting alone. Verify all four components as well as final mixture so cancellation cannot conceal changes.
3. Prove inference works with experiment/research directories absent from the packaged runtime. Static forbidden-import checks should accompany a real clean-package import and prediction.
4. Exercise the shared existing API contracts against both strategies: full grid, filters, deterministic repeated POST, error status, cache isolation, correct identity, and startup rejection of unsupported or tampered manifests/config/models.
5. Run the final packaged artifact or container, with only declared inputs and selected models, under the stated CPU/RAM/no-network constraints. Existing experimental offline replay is insufficient evidence for the newly shared API/container.

Preserve floating-point operation order, SHA256 categorical codes, the nine seven-day buckets plus one day, raw allocations and threshold-after-mixture order. Dense category remapping would require a separate weight compatibility treatment; changing it during consolidation is not a mechanical refactor.

## Scope and limitations

No inference, API request, build, training or test suite was executed by this audit agent. Source inspection and static import graph plus 12 SHA256 checks are the actual evidence. The current Dockerfile copies only `src`, `app`, and incumbent `model`; it cannot serve the experimental directory without a declared packaging change. Runtime consolidation can remove this dependency without transferring foreign protected source code or inventing a second downloaded project.
