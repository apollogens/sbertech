# Аудит кода и карта исполнения

Дата 18.10.2026; Principal QA Architect — root, единственный интегратор production-исправлений. Реально работали независимые Agent A metrics_audit, Agent B leakage_audit, Agent C backend_audit. Использованы нативные subagents; дополнительный AI-model override не задавался и наличие иных моделей не заявляется.

Git HEAD отсутствует: репозиторий без коммитов, все исходные файлы untracked. Исходная ревизия — initial_manifest.json, SHA256 `6b84aa8e64abd89d921a0d041e9da128d339e812a7b64f67b3fd1e778cb38235`; восстановимый код/модели — pre_audit_snapshot.zip. Все старые OOF, CSV, результаты и исходные данные сохранены; список SHA до изменений включает99 файлов. Аудированное финальное дерево: `41005a07b86da198c4d42c3c2cb2645106c587a16ea6796748d0abd176d0679f`; состав — revision.json. SHA рабочих весов, конфигурации, каталога и исходного submission не изменены.

## Источники и исполнение

Сначала прочитано оригинальное markdown ТЗ; встроенный scorer извлечён и дословно/AST совпал с scripts/official_score.py. Реальные CSV прочитаны и независимо реконструированы; backend DOCX разобран zip/XML. Затем проверены код/config/артефакты/старые отчёты. Противоречия SMAPE, full grid против observed pairs, отсутствующие cost_price/volume_weight и inclusive180 описаны явно. DOCX не подменяет организаторское ТЗ. Данные не отправлялись внешним AI; сеть использовалась для официальной документации и установки QA-зависимостей.

Тренировка: run_pipeline → prepare_cache/load_panel → read_inputs → clean_stock → build_panel → training_data → snapshot/horizon_features → train_model → lgb.Dataset/train → save_model/config/catalog. Кандидаты L2/Tweedie с220trees и thresholds0/.25/.5 сравниваются на одинаковых folds1/2; frozen JSON записывается до holdout; final refit использует всю допустимую историю.

Инференс: scripts/predict.py либо HTTP POST → общий predict_64 → build_panel фиксированного каталога → predict_panel → snapshot только до origin → horizon_features известных будущих дат →8 batch по8 горизонтов → LightGBM → finite/nonnegative/threshold → forecast_frame → validate_submission. Ни один forecast не подаётся обратно в lag.

HTTP путь: UploadFile → strict CSV → validate_history → post_lock → Predictor.predict → проверка full grid → атомарная публикация cache → StreamingResponse. GET удерживает завершённый snapshot. Cache живёт в RAM одного worker и пропадает после restart. Docker копирует только runtime source/model/lock, train не требуется.

Модель зависит от ordered feature list, ordered catalogs, horizon64, schema1 и текстовых весов. Loader проверяет schema/kind/threshold/order/uniqueness/features. Отсортированная замена содержимого каталога пока не привязана fingerprint к весам; это residual P2, не текущая порча bundle.

## Независимая проверка данных

Sales1,492,370 строк →970,677 aggregated keys, панель943×8789 точно совпала с raw; quantity total1,826,791. Департаменты суммируются, join со stock не используется для умножения строк. Все943 sales даты есть в источнике. Из всех8789 required pairs наблюдались8777, остальные12 отдельно проверены: каждый имеет64 прогнозов, все0 после фактического inference/threshold, а не заполнения отсутствующих output keys. Полный grid chosen по фиксированному числу562496; неоднозначность прозы ТЗ раскрыта.

Stock6,153,988 строк, negative57, conflicting keys804,588; после удаления negatives конфликтных ключей804,560, clean unique keys4,079,621. Независимые min/max по ключам воспроизвели clean policy и cache stock побитово. Missing stock=NaN отличается от0. Это допущение очистки неоднозначных данных, не восстановленная истинная величина запасов.

Категории по реальному train: конфликтующих article на каждом из levels1/2/3 —0; отсутствующие категории допустимы. Для segmented diagnostics категории определялись только по истории fold. Missing sales=0 — явно принятое event-export допущение; истинный скрытый спрос не измерен.

## Полнота обхода и coverage

Статическая карта imports/entrypoints всех first-party .py: dependency_map.json. Команда inventory: `rg --files` с исключением venv/cache/binaries; источники читались с Get-Content UTF8 и Python AST. Root и reviewers трассировали data→training/inference→API и вспомогательные CLI. Не заявляется ручная проверка каждой строки новых и старых скриптов. Third-party/venv и бинарные NPZ вручную построчно не читались; NPZ проверены программно. CI-конфигурация в дереве не обнаружена.

Покрытие core src/app: statements500/550 (90.91%), branches164/196 (83.67%). Полный инструментированный набор src/app/scripts имеет отдельное coverage.json и coverage_summary.txt: CLI-обёртки сильно снижают общий процент. Coverage записывалась для main tests, real OOF/temporal/backend, свежего инференса и шести full fits; часть QA/CLI запусков сделана до включения scripts в coverage и не должна трактоваться как неисполненная только по0%.

Риск непокрытых ветвей: HIGH — run_pipeline orchestration/cache refresh целиком не запускалась, чтобы не перезаписывать лучшие результаты; вместо этого отдельно повторены все6 реальных fits и pipeline transformations. MEDIUM — prepare_cache при смене источника, исходные audit/packaging wrappers, baseline-only bundle route, некоторые invalid schema branches. LOW — empty streaming frame и malformed internal alias branches. Dead-code выводы не делались: baseline/train/finalize CLI используются README, хотя не являются runtime API.

## Инвентарь модулей

| path | lines | entry_functions | imports |
|---|---|---|---|
| src/__init__.py | 1 |  |  |
| src/baselines.py | 27 | baseline_predict | .features, numpy |
| src/data.py | 145 | read_inputs, catalog_from_sales, Panel, clean_stock, build_panel, prepare_cache, load_panel | dataclasses, json, numpy, pandas, pathlib |
| src/features.py | 69 | snapshot, horizon_features, training_data | numpy, pandas |
| src/metrics.py | 83 | _arrays, compute_metrics, smape_include_zero_zero, normalize_metrics, weighted_score, evaluate | collections.abc, numpy |
| src/predict.py | 63 | load_bundle, predict_panel, predict_64 | .baselines, .data, .features, .submission, json, lightgbm, numpy, pandas, pathlib |
| src/submission.py | 41 | forecast_frame, validate_submission, write_submission | numpy, pandas, pathlib |
| src/train.py | 23 | train_model | .features, lightgbm |
| app/__init__.py | 1 |  |  |
| app/main.py | 112 | csv_chunks, json_chunks, csv_response, create_app | .predictor, .validators, contextlib, fastapi, fastapi.exceptions, fastapi.responses, logging, os, pathlib, starlette.concurrency, starlette.exceptions |
| app/predictor.py | 51 | Predictor | numpy, pandas, pathlib, src.predict, threading |
| app/validators.py | 98 | InputError, read_csv, validate_history | csv, io, numpy, pandas, warnings |
| scripts/audit_inputs.py | 65 | audit | collections, csv, json, math, pathlib, time |
| scripts/backtest_baselines.py | 20 |  | pandas, pathlib, src.baselines, src.data, src.metrics, sys |
| scripts/container_probe.py | 52 | connection | http.client, json, pathlib, time |
| scripts/finalize_reports.py | 144 | digest, table, run | hashlib, json, numpy, pandas, pathlib, src.predict, src.submission, subprocess, sys, zipfile |
| scripts/official_score.py | 372 | smape_series, smape, wape, rmse, bias_abs_series, bias_abs, rmsle, compute_all_metrics, normalize_minmax, normalize_rank, validate_submission, main | argparse, json, numpy, pandas, pathlib, sys, typing |
| scripts/predict.py | 20 |  | argparse, pathlib, src.data, src.predict, src.submission, sys |
| scripts/prepare_api_inputs.py | 20 |  | argparse, pathlib, src.data, sys |
| scripts/qa_analysis.py | 211 | bias_diagnostics, table, run | argparse, collections, hashlib, json, matplotlib, matplotlib.pyplot, numpy, pandas, pathlib, src.data, src.features, src.metrics, src.submission, sys |
| scripts/qa_retrain.py | 67 | run | gc, hashlib, json, numpy, pandas, pathlib, psutil, src.data, src.metrics, src.predict, src.train, sys, threading, time |
| scripts/qa_stock_integrity.py | 53 | run | hashlib, json, numpy, pandas, pathlib, src.data, sys, time |
| scripts/qa_verify_submission.py | 36 | run | json, numpy, pandas, pathlib, src.data, src.predict, src.submission, sys, time |
| scripts/run_pipeline.py | 140 | run | argparse, gc, json, numpy, pandas, pathlib, psutil, src.baselines, src.data, src.features, src.metrics, src.predict, src.submission, src.train, sys, threading, time |
| scripts/train_final.py | 21 |  | json, pathlib, src.data, src.train, sys |
| scripts/validate_submission.py | 15 |  | argparse, pandas, pathlib, src.predict, src.submission, sys |
| scripts/verify_parity.py | 90 | run | app.main, fastapi.testclient, gc, io, json, lightgbm, numpy, pandas, pathlib, psutil, src.data, src.metrics, src.predict, src.submission, sys, threading, time |
| tests/test_api.py | 221 | setup, post, parse, test_full_contract_and_determinism, test_bad_query_error_shape, test_missing_file, test_bad_csv, test_invalid_history, test_stock_duplicate_policy, test_sales_duplicates_are_not_dropped, test_failed_post_preserves_cache_and_concurrent_post_rejected, test_invalid_model_output_not_cached, test_stock_article_alias, test_required_sales_metadata, test_actual_sales_schema_and_empty_categories, test_strict_date_format, test_unsupported_numeric_range_is_422_and_preserves_cache, test_truncated_metadata_csv_record_is_400 | app.main, app.predictor, fastapi.testclient, io, numpy, pandas, pytest |
| tests/test_metrics.py | 64 | as_frame, test_official_parity, test_smape_document_conflict_is_explicit, test_all_zero_truth_official_edge_case, test_normalization_and_score_parity, test_perfect_forecast_score, test_invalid_inputs_rejected | numpy, pandas, pytest, scripts, src.metrics |
| tests/test_pipeline.py | 167 | small_panel, test_future_data_invariance_snapshot_and_horizons, test_appending_future_input_rows_does_not_change_fixed_cutoff, test_departments_sum_missing_sales_zero_missing_stock_nan, test_stock_observability_is_not_confused_with_zero, test_training_labels_all_known_by_cutoff_and_correct_horizon, test_horizon_calendar_and_grid_serialization, test_tiny_trained_model_save_load_feature_order_and_determinism, test_conflicting_stock_duplicates_are_rejected, test_clean_stock_removes_all_ambiguous_rows_and_preserves_true_zero, test_shared_panel_rejects_conflicting_article_aliases | json, numpy, pandas, pytest, src.data, src.features, src.predict, src.submission, src.train |
| tests/test_qa_regressions.py | 146 | inputs, test_offline_requires_strict_date_format, test_panel_rejects_float32_overflow, test_panel_rejects_aggregation_overflow, test_offline_rejects_empty_identifier, test_forecast_rejects_wrong_axes_with_correct_element_count, test_unknown_model_kind_fails_at_load, test_required_bias_and_smape_independent_fixtures, test_csv_body_structure_is_strict, test_bundle_rejects_reordered_categorical_mapping, test_controlled_bias_edge_cases, test_bias_series_permutation_and_all_excluded_diagnostics, test_rank_ties_reproduce_original_evaluator_order_dependence, test_submission_key_and_finite_guards | app.validators, json, numpy, pandas, pytest, scripts.official_score, scripts.qa_analysis, src.data, src.metrics, src.predict, src.submission |

Реестр всех находок с механизмом, воспроизведением, severity, ожидаемым/наблюдавшимся поведением и статусом: defects.csv. Полные независимые выводы: reviewer_metrics.md, reviewer_leakage.md, reviewer_backend.md.
