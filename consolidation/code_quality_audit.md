# Аудит качества кода и покрытия до консолидации

Проверяющий: агент C. Дата: 19 октября 2026. Проверка исходного состояния выполнена чтением кода и collection pytest; обучение, удаление и изменение рабочих модулей не выполнялись. Этот документ не является результатом финального regression run.

## Подтверждённые связи и дублирование

1. Production: `app.main → app.predictor → src.predict → src.data/features/submission/artifacts`. Валидация HTTP в `app.validators` намеренно строже общего panel builder: обязательные metadata и статус HTTP нельзя терять при объединении.
2. Experimental: `integration.experimental_predict → integration.corrected_models → scripts.architecture_experiments → scripts.qa_analysis`. Таким образом, inference сейчас импортирует исследовательский runner с `psutil`, training, scoring и diagnostic imports. Нужно перенести пять численных helpers (`BUCKETS`, `weekly_frame`, `weekday_weights`, `allocate_buckets`, `warehouse_shares`) в чистый runtime-модуль, а исторический runner переключить на него либо сохранить отдельно для воспроизведения прежнего исследования.
3. Daily batch inference повторён в `src.predict.predict_panel` и nested `daily` внутри `integration.corrected_models.predict_components`: восемь горизонтов в batch, feature order check, `num_threads=4`. Это реальный кандидат на один helper с явным feature schema; encoders двух версий моделей объединять нельзя.
4. Два CSV inference CLI — `scripts/predict.py` и `integration/experimental_predict.py` — используют разные loaders и serialization. Общая новая команда должна вызывать выбранный runtime, единый reader и final validator. Старые документированные CLI нельзя удалять без переноса их тестов и явного сообщения о миграции либо совместимого тонкого adapter.
5. Проверка forecast grid в `app.predictor.Predictor.predict` частично повторяет `src.submission.validate_submission`, но у них разные правила порядка: API допускает перестановку и сортирует, submission требует canonical order. Общий validator должен явно поддерживать оба режима, иначе cleanup изменит поведение.
6. `src.train.PARAMS` импортируется experimental inference через training module. Константы можно вынести; runtime не должен зависеть от training entrypoint лишь ради констант.

## Артефакты ограничивают удаление

`integration.corrected_models.source_hashes()` проверяет восемь исходных путей, включая старые `integration/*`, `scripts/architecture_experiments.py`, `src/train.py`. `experimental_predict` отдельно сверяет свой SHA-256 с `ensemble_contract.adapter_sha256`; loader также требует точные версии dependencies. Простое перемещение или форматирование этих файлов делает прежний bundle несовместимым.

Нужна отдельная версия migrated manifest, подтверждённый перенос весов без retrain и numerical replay. Старые manifest/config/source hashes должны остаться историческим свидетельством. Нельзя ослаблять integrity checks ради успешной загрузки. Удаление старых модулей допустимо только после проверки отсутствия runtime imports и сохранения воспроизводимого snapshot.

Сериализованных Python pickle-модулей в изученном serving path нет: LightGBM загружается из TXT. Тем не менее sourcehash references и прямые вызовы scripts являются реальными контрактами. `tests/test_remediation_backend.py` исполняет замороженный Python из `reports/remediation/original_release.zip`; этот архив требуется сохранить.

## Существующий набор тестов

Выполнена collection-команда:

```powershell
.venv/Scripts/python.exe -m pytest tests reports/qa/check_backend_independent.py integration/test_catalog_policy.py integration/test_ensemble_engine.py --collect-only -qq
```

| Источник | Количество cases | Основной путь |
|---|---:|---|
| tests/test_api.py | 49 | HTTP validation, cache, deterministic output, failed POST |
| tests/test_metrics.py | 13 | official formula parity, SMAPE discrepancy, edge cases |
| tests/test_pipeline.py | 10 | aggregation, stock, cutoff, tiny trained model, serialization |
| tests/test_qa_regressions.py | 26 | malformed CSV, numeric overflow, catalog order, metric/keys |
| tests/test_remediation_backend.py | 36 | artifact corruption, provenance, actual HTTP concurrency, cache |
| tests/test_remediation_cli.py | 20 | subprocess scripts, foreign cwd, actual isolated tiny pipeline |
| tests/test_remediation_models.py | 2 | historical two-part training/cutoff |
| reports/qa/check_backend_independent.py | 21 | additional independent backend regressions |
| integration/test_catalog_policy.py | 6 | origin-local catalog, stable codes, unknown fallback |
| integration/test_ensemble_engine.py | 10 | keyed alignment, weights, threshold/rounding/order |
| **Всего** | **193** | **156 + 21 + 16** |

Это количество собранных cases, не новый PASS. Число 177 относится к первым двум группам. Число 172 относится к `tests/` и двум integration-файлам без 21 independent cases. Эти scopes не следует смешивать.

API tests преимущественно используют synthetic predictor; реальные tiny training/CLI и bundle integrity уже проверяются отдельно. Подтверждение full-size saved-model/API/Docker требует новых исполнимых release probes, оно не следует из unit suite.

## Пробелы для новой архитектуры

- Обе стратегии через один API и один CLI: selection, unknown strategy, несовместимая версия bundle, startup failure, metadata active model.
- Совпадение каждого migrated D/W/S/A прогноза с сохранённым reference, а также final equal4 after-threshold output. Проверка числа вызовов Booster: S использует D/W; daily-only не должен запускать ненужные модели.
- Rejection несовпадающих model/catalog/origin/horizon identities при совпадающих ключах. Старый `align_components` проверяет ключи, но не отдельную metadata identity.
- 180-day-only исторический backtest с той же membership policy, что serving. Существующий full-history quality report нельзя считать таким backtest.
- Inference не читает `integration/catalog_audit/first_observed.csv`, original research data и не вызывает fit; добавление будущих sales/stock не меняет fixed-cutoff forecast.
- Corrupt migrated config/TXT/schema/mappings и неполный output grid безопасно отвергаются. Failed POST сохраняет прежний cache для каждой стратегии.
- Новая единая CLI: foreign cwd, help, invalid options, exit 2, реальный результат и submission validation; packaging, API и Docker обязаны использовать тот же selected runtime.

## Ошибки и инструменты

Широкий `except Exception` в `app.main` оборачивает только inference, пишет server log и возвращает безопасный HTTP 500; внешний `finally` снимает lock. Это обоснованная граница API, не dead exception handler. Существующие CLI перехватывают ожидаемые `OSError/ValueError/KeyError`; новую CLI нужно проверить также на повреждённый JSON и missing bundle. Runtime asserts не должны служить artifact validation: например, dtype assert в experimental fit относится к training и не заменяет loader checks.

Ruff и deptry отсутствуют и как модули рабочей `.venv`, и как команды PATH. Проверка: `importlib.util.find_spec` для обоих вернула False, `Get-Command ruff,deptry -ErrorAction SilentlyContinue` не нашёл executable. Пакеты в рамках read-only аудита не устанавливались. Нулевой lint/deptry baseline не заявляется; root должен выполнить их в новой development environment. Coverage установлен, но процент покрытия в этом аудите не измерялся.

## Решение по cleanup

Безусловно безопасного удаления рабочих исходников до миграции не установлено. Есть конкретные MERGE/ARCHIVE candidates в `deletion_candidates.csv`; это предварительный ledger, не журнал выполненных удалений. После переноса runtime и regression gate нужно физически убрать прежние executable реализации из активного дерева либо оставить лишь требуемые тонкие CLI adapters. Исследовательские evidence/replay scripts и frozen release archives сохраняются с явным статусом historical. Одно изменение flags или `.dockerignore` не устраняет дублирование кода.
