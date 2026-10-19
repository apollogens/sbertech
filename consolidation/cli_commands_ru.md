# Единая командная строка

Рабочая директория: `D:/SberTech`. Интерфейс: `.venv/Scripts/python.exe -X utf8 -m src.cli`. В чистой development environment замените путь Python на её interpreter. `--help` доступен у каждой команды. Некорректные параметры дают exit 2; операции predict/validate/package возвращают structured JSON error без traceback для ожидаемых ошибок ввода. Команды, делегирующие существующий инструмент, сохраняют его exit code и сообщения.

Конфигурация по умолчанию — `config/runtime.json`; можно передать `--config` или задать `FORECAST_CONFIG`. Относительный путь `active_bundle` отсчитывается от файла конфигурации. `--model-dir` имеет приоритет над `--config` и окружением; `--strategy` выбирает совместимую стратегию. Incumbent принимает только `nonton-v1`; migrated component bundle принимает `D`, `W`, `S`, `A`, их варианты `:P1` и `equal4:P1`. Исторические weights с другим encoder не подменяются.

```powershell
# Все поддерживаемые автоматические tests и independent backend regressions
.venv/Scripts/python.exe -X utf8 -m src.cli test
# Опции pytest и явный scope после --
.venv/Scripts/python.exe -X utf8 -m src.cli test -- tests/test_cli.py tests/test_unified_runtime.py -q

# Потоковый read-only аудит: пути к исходным файлам заданы стандартными именами в data-dir
.venv/Scripts/python.exe -X utf8 -m src.cli audit --data-dir path/to/data --output consolidation/input_audit.json

# Поддерживаемое обучение incumbent; output-dir обязателен, production не перезаписывается по умолчанию
.venv/Scripts/python.exe -X utf8 -m src.cli train --cache-dir cache --selection reports/selection_frozen.json --output-dir model/new-incumbent

# 180-day production-like evaluation сохранённых historical bundles, без нового fit
.venv/Scripts/python.exe -X utf8 -m src.cli backtest --sales path/to/sales.csv --stock path/to/stock.csv --output consolidation/backtest_180

# Оригинальный официальный scorer, включая исходное executable поведение SMAPE
.venv/Scripts/python.exe -X utf8 -m src.cli score --truth truth.csv --submissions candidate.csv --method rank --output consolidation/score.csv

# Активный release из конфигурации
.venv/Scripts/python.exe -X utf8 -m src.cli predict --sales path/to/sales.csv --stock path/to/stock.csv --output consolidation/submission.csv
# Явный selectable candidate; bundle-dir задаётся путём к migrated runtime_manifest.json
.venv/Scripts/python.exe -X utf8 -m src.cli predict --model-dir path/to/component-bundle --strategy equal4:P1 --sales path/to/sales.csv --stock path/to/stock.csv --output consolidation/ensemble.csv
.venv/Scripts/python.exe -X utf8 -m src.cli validate --model-dir model --input consolidation/submission.csv --origin 2026-07-31

# ZIP содержит только проверенные файлы model bundle и manifest; это не полный source release
.venv/Scripts/python.exe -X utf8 -m src.cli package --model-dir model --output consolidation/incumbent-model.zip

# Один worker и пустой cache после restart
.venv/Scripts/python.exe -X utf8 -m src.cli serve --host 127.0.0.1 --port 8000

# Сборка без Docker layer cache; публикация образа не выполняется
.venv/Scripts/python.exe -X utf8 -m src.cli docker build --image nonton-consolidated --bundle model
.venv/Scripts/python.exe -X utf8 -m src.cli docker test --image nonton-consolidated
# Для candidate image выбрать соответствующий reference:
.venv/Scripts/python.exe -X utf8 -m src.cli docker test --image nonton-ensemble --strategy equal4
```

`predict` использует те же CSV/history validators, что HTTP API: sales metadata обязательны, sales и stock должны покрывать минимум 180 календарных дней. Затем вызываются общий dispatcher и output validator. Запись идёт атомарно, с `%.17g`, без integer rounding. Неуспешный запрос не заменяет прежний output.

`train` делегирует проверенному `scripts/train_final.py`, `audit` — `scripts/audit_inputs.py`, `score` — неизменённому `scripts/official_score.py`, `backtest` — `consolidation/backtest_180.py`. Это одна точка командного входа с сохранением разных реальных workflow, а не копии их реализации. Обучение новых component weights в этот интерфейс не добавлено: сохранённый ensemble используется без retrain.

Проверка самого интерфейса: `.venv_consolidated/Scripts/python.exe -m pytest tests/test_cli.py -q` — **19 cases** после исправления обнаруженного при QA выбора Docker reference. Исполнены реальные baseline-bundle inference, submission validation, two-run byte determinism, packaging/hash verification, config selection, malformed-input сохранность output, streaming audit и официальный scorer; все десять subcommand help/unknown-option проверены subprocess из другой директории. Проверено, что `serve --model-dir` перекрывает config/env и запускает ровно один worker; Docker candidate передаёт `-Strategy equal4` в verification script. Heavy training/backtest/Docker этим тестом не запускаются: их отдельные результаты публикуются в release evidence.
