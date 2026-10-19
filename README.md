# Nonton — единый проект прогнозирования

Для продолжения работы в Codex: [AGENTS.md](AGENTS.md), [постоянный master prompt](docs/CODEX_PROJECT_MASTER_PROMPT.md), [короткий resume prompt](docs/CODEX_RESUME_PROMPT.md), [текущий статус](docs/PROJECT_STATUS.md). Клонирование с моделями и архивами требует Git LFS: [инструкция публикации](docs/github_publication_ru.md).

Активный выпуск — **nonton-v1**, выбранный в [`config/runtime.json`](config/runtime.json). Исполняемый кандидат **equal4:P1**, corrected D/W/S/A используют тот же runtime, API и CLI с отдельным совместимым bundle `bundles/equal4-rc1`. Три LightGBM Booster дают четыре представления; S повторно использует D и W. Веса при консолидации не переобучались.

Итоги: [`consolidation/final_release_report_ru.md`](consolidation/final_release_report_ru.md). Архитектура: [`consolidation/canonical_architecture.md`](consolidation/canonical_architecture.md). Проверка выпуска: [`consolidation/independent_release_review.md`](consolidation/independent_release_review.md). Исторические исследования и выпуски сохранены в `reports/`, `research/`, `integration/` и прежних ZIP.

## Установка и тесты

Python 3.12. NumPy 2.5.4, pandas 3.0.6, LightGBM 4.7.0 сохранены. Pip устанавливает готовые lock-файлы; uv используется для их разрешения. Исходная `.venv` сохранена для отката.

```powershell
python -m venv .venv_consolidated
.venv_consolidated/Scripts/python.exe -m pip install -r requirements-dev.lock
.venv_consolidated/Scripts/python.exe -m pip check
.venv_consolidated/Scripts/python.exe -m src.cli test
```

Для inference достаточно `requirements.lock`; training, dev, research имеют отдельные `.txt` и `.lock`. Тесты не входят в runtime. Статистический benchmark с другим pandas остаётся в изолированном историческом окружении.

## Прогноз и API

Команды выполняются из корня проекта. Все операции: `python -m src.cli --help`. Полные команды: [`consolidation/cli_commands_ru.md`](consolidation/cli_commands_ru.md).

```powershell
.venv_consolidated/Scripts/python.exe -m src.cli predict --sales sales.csv --stock stock.csv --output forecast.csv
.venv_consolidated/Scripts/python.exe -m src.cli predict --model-dir bundles/equal4-rc1 --strategy equal4:P1 --sales sales.csv --stock stock.csv --output ensemble.csv
.venv_consolidated/Scripts/python.exe -m src.cli validate --input forecast.csv --origin 2026-07-31
.venv_consolidated/Scripts/python.exe -m src.cli serve --host 127.0.0.1 --port 8000
.venv_consolidated/Scripts/python.exe -m src.cli serve --model-dir bundles/equal4-rc1 --strategy equal4:P1
```

`--strategy D`, `W`, `S`, `A` выбирает отдельное представление corrected bundle с тем же порогом. `--config` или `FORECAST_CONFIG` выбирает альтернативную конфигурацию. Пути bundle внутри config разрешаются относительно config. API поддерживает `MODEL_DIR` и `FORECAST_STRATEGY`; `FORECAST_CONFIG` имеет приоритет. CLI разрешает свой явный выбор перед запуском API.

`POST /predict` принимает multipart CSV `sales`, `stock`; `GET /predict/all` возвращает полный кэш; `GET /predict?article=...&warehouse=...` — 64 дня пары; `format=json` переключает формат. `/health` и `/diagnostics` показывают состояние. До успешного POST кэш пуст (409); ошибка POST сохраняет прежний кэш; перезапуск очищает его. Один worker обязателен; параллельный POST получает 409.

История — минимум 180 календарных дней. Используется **вся переданная история**, cutoff — последняя дата sales; будущие stock не входят в признаки. CSV соответствуют схемам `app/validators.py`. Отрицательные/нечисловые значения, конфликтующие stock-дубли и неизвестные output ID отклоняются. Прогноз: 64 дня × 11 складов × 799 товаров = 562496 строк. В corrected моделях membership определяется только sales входного окна, включая нулевые записи; неизвестные модели output ID получают 0. Каталоги и encoder разных bundles не взаимозаменяемы.

Смесь считается до порога `<0.25 → 0`; обязательного округления до целых нет. CLI пишет LF и 17 значащих цифр; прежние Windows CSV могли использовать CRLF. Количества сохранены, текстовый хэш может измениться из-за перевода строки.

Для исходного stock с отрицательными измерениями и конфликтующими дублями есть явная подготовка `scripts/prepare_api_inputs.py`: исключаются отрицательные измерения и целиком конфликтующие дневные ключи. Пропуски stock остаются неизвестными. Sales суммируются по дневному ключу; отсутствие строки трактуется как 0 по допущению событийной выгрузки. Цель — наблюдаемые продажи.

## Обучение, оценка, упаковка

CLI объединяет `test`, `audit`, `train`, `backtest`, `score`, `predict`, `validate`, `package`, `serve`, `docker`. `train` воспроизводит incumbent из cache и frozen selection в явно заданный output-dir. Обучение компонентов сохранено как исследовательская процедура; для переключения поставленных bundles обучение не требуется. Старые публичные scripts сохранены там, где необходима совместимость; `scripts/predict.py` делегирует общему CLI.

`scripts/official_score.py` не изменён. Исполнимый SMAPE исключает пары (0,0), текстовая формула трактует их иначе; диагностический вариант назван отдельно. Веса — 50/20/15/10/5. Локальные rank/minmax зависят от пула и не воспроизводят неизвестный leaderboard.

180-дневная проверка: [`consolidation/backtest_180/report_ru.md`](consolidation/backtest_180/report_ru.md). Небольшой выигрыш equal4 против corrected D сохраняется на пяти средних development-метриках. Это повторно использованные окна, untouched test отсутствует. Полное сопоставление с incumbent на 180-дневных входах ограничено наличием исторических весов. Численная регрессия рефакторинга и изменение исторического контекста оцениваются отдельно.

```powershell
.venv_consolidated/Scripts/python.exe -m src.cli package --model-dir model --output consolidation/incumbent_bundle.zip
.venv_consolidated/Scripts/python.exe -m src.cli package --model-dir bundles/equal4-rc1 --strategy equal4:P1 --output consolidation/equal4_bundle.zip
.venv_consolidated/Scripts/python.exe -m src.cli docker build --image nonton:consolidated-v1 --bundle model
.venv_consolidated/Scripts/python.exe -m src.cli docker test --image nonton:consolidated-v1 --strategy nonton-v1
.venv_consolidated/Scripts/python.exe -m src.cli docker build --image nonton:consolidated-equal4 --bundle bundles/equal4-rc1
.venv_consolidated/Scripts/python.exe -m src.cli docker test --image nonton:consolidated-equal4 --strategy equal4
```

Docker включает выбранный bundle, runtime lock и приложение. Исходные CSV, OOF, исследования, чужие репозитории и окружения исключены. Проверка использует `--network none`, 4 CPU, 6 GiB; тестовые CSV копируются после старта. Runtime-only образ предназначен для API/inference, обучение и исторические исследования запускаются на host с соответствующим lock. Manifests проверяют hashes, catalogs, признаки и численные зависимости до загрузки.

## Состав и происхождение

`src/` — общий runtime и обучение incumbent; `app/` — API; `config/` — активный выбор; `model/` — incumbent; `bundles/` — кандидаты; `tests/` — инженерные проверки; `consolidation/` — новая верификация и поставка. Исторические integration imports делегируют общие расчёты в src. Шесть заменённых release-инструментов архивированы в `consolidation/legacy_source.zip`. Полный frozen source доступен в `pre_merge_snapshot.zip`; старые manifests проверяются на соответствующем frozen source.

Подтверждён один внешний источник: `filipp880/forecast-64-v1`, commit `f8a8c6e60edaf12af2fd351e290c35e6875afea0`. Лицензия в tracked tree отсутствует. Внешний код не переносился; общая выпуклая смесь и postprocessing реализованы самостоятельно. Второй пользовательский репозиторий не установлен. Подробности: `integration/source_license_audit.md`.

Откат: [`consolidation/rollback_plan.md`](consolidation/rollback_plan.md). Проверенный снимок распаковывается в новую пустую папку без перезаписи текущей работы. Прежние models, submission, ZIP и исследовательские NPZ сохранены.
