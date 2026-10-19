# Аудит зависимостей и окружения

Проверка Agent B, 19 октября 2026. Это исходный read-only аудит до миграции. Манифесты, Dockerfile и существующая `.venv` не изменялись. Машинный снимок импортов 85 first-party Python-файлов, установленных версий и транзитивных рёбер — `dependency_graph.json`. Внешние `research/sources`, source inspection и распакованные копии bundle исключены из first-party анализа.

## Исходное состояние

Python `.venv`: 3.12.10, Windows amd64. `pip list --format=json`: **42 distributions**, включая pip 25.0.1. `pip check`: **No broken requirements found**. В `requirements.txt` 7 прямых pins; `requirements-dev.txt` включает runtime и добавляет pytest, httpx, coverage, matplotlib. В `requirements.lock` **33 pins**, но смешаны runtime и тестовые зависимости. Docker устанавливает именно этот смешанный lock. `uv.exe` доступен; Ruff, deptry, pip-tools в исходном окружении отсутствуют. Их будущая установка и запуск не заявляются результатом этого аудита.

`numpy==2.5.4`, `pandas==3.0.6`, `lightgbm==4.7.0` совпадают с manifest production. `src/artifacts.py` проверяет текущие версии этих distributions при загрузке bundle. `integration/experimental_predict.py` также сверяет версии через `importlib.metadata`. Эти pins нельзя менять при технической очистке: даже загрузка старой модели может быть отвергнута. Общий импорт scipy не виден в коде приложения, но он обязателен по metadata LightGBM. Аналогично narwhals и opentelemetry-api нельзя удалять на основании отсутствия first-party import.

## Границы групп

| Группа | Прямые зависимости | Основание |
|---|---|---|
| Serving/offline inference | numpy, pandas, lightgbm, fastapi, uvicorn, python-multipart, starlette | `src/predict.py`, data/features/submission, `app/main.py`; multipart обязателен для File/UploadFile, uvicorn — Docker startup |
| Training/benchmark tools | runtime + psutil | `scripts/run_pipeline.py`, qa_retrain, architecture_experiments, integration/run_experiments; мониторинг RSS |
| Tests/QA | runtime + pytest, httpx, coverage; psutil для release probes | TestClient использует httpx; тестовые subprocess запускают CLI/uvicorn; coverage — явный инструмент измерения |
| Reproducible research/plots | предыдущие группы + matplotlib | `scripts/qa_analysis.py:191–193`, графики через Agg |
| Изолированный statistical benchmark | statsforecast и его отдельный исторический lock | `scripts/remediation_statistical.py`, `reports/remediation/statsforecast_requirements.lock`; statsforecast в основной `.venv` отсутствует |
| External references | собственные manifests внешних проектов | Не переносить TensorFlow/PyTorch/прочие зависимости внешних клонов в runtime |

Starlette прямо импортируется приложением (`run_in_threadpool`, exceptions), поэтому следует указать `starlette==1.8.0` как прямой pin, хотя FastAPI уже устанавливает её транзитивно. Psutil не используется `src/` или `app/`: перенос в training/dev обоснован, удаление из всей системы — нет. Matplotlib нужен воспроизводимости исторических графиков, поэтому его следует перенести в research-группу, а не считать мёртвым пакетом.

## Минимальный runtime и доказательства исключения

Обход `Requires-Dist` установленных distributions, с marker Python 3.12 и без extras, для семи runtime roots даёт **23 пакета Windows / 22 Linux**. Разница — tzdata, обязательная pandas только на Windows/emscripten. Если нужен общий cross-platform lock, tzdata должна иметь marker `sys_platform == "win32" or sys_platform == "emscripten"`. В Windows-runtime closure нет десяти прежних lock-пакетов:

| Пакеты | Почему можно исключить из runtime lock | Где сохранить |
|---|---|---|
| pytest, iniconfig, pluggy, Pygments, packaging, colorama | Нет в runtime Requires-Dist closure; нужны pytest и его Windows-консоли | dev lock |
| httpx, httpcore, certifi | Нет runtime исходящих рёбер; HTTP-клиент нужен TestClient, сервер не вызывает внешний HTTP | dev lock |
| psutil | Нет serving импортов, нет в runtime closure; есть реальные benchmark imports | training/dev lock |

Это предложение исключить **10 из 33** старых runtime-install pins на Windows (11 на Linux с tzdata), а не доказательство успешного clean install. Нарушения импортов, startup и Docker после удаления обязан проверить release workflow. Подтверждённое сокращение образа/latency не заявляется.

Транзитивные runtime зависимости: annotated-doc, annotated-types, anyio, click, h11, idna, narwhals, opentelemetry-api, pydantic, pydantic-core, python-dateutil, scipy, six, typing-extensions, typing-inspection и условная tzdata. Точные версии и рёбра записаны в JSON. Системная Linux dependency `libgomp1` необходима LightGBM и должна остаться в Dockerfile. Стандартная установка uvicorn без extras не требует httptools, watchfiles, uvloop, websockets или python-dotenv; добавлять их для очистки не нужно.

## Динамические пути и ограничения

Production загружает LightGBM TXT через Booster; pickle/python-object deserialization не обнаружена в serving. `src/artifacts.py` использует distribution metadata, а не динамический импорт модулей модели. В research reviewers встречается `importlib.util.spec_from_file_location` для точного официального scorer; `__import__('os')` импортирует стандартную библиотеку. `research/audit_sparse_artifacts.py` проверяет `find_spec` torch/transformers/lightning: это фиксация доступности, а не требование их устанавливать. Полные найденные вызовы записаны в JSON.

Статический импорт-граф не покрывает внешние пользовательские плагины и неизвестные будущие CLI. По этому аудиту нельзя удалять first-party файлы. Historical statistical benchmark воспроизводится в отдельной среде; его отсутствие в главной `.venv` не означает успешную проверку этого benchmark.

## Предлагаемая миграция без смены ML-версий

1. Оставить прямые версии runtime в `requirements.txt`, добавить явный starlette, перенести psutil в `requirements-training.txt`; research-группе оставить matplotlib. Dev включает runtime, training и pytest/httpx/coverage плюс отдельно закреплённые Ruff/deptry.
2. Сформировать отдельные полные locks runtime/training/dev/research из текущих точных версий. Новый lint tool требует осознанно закреплённой версии; не обновлять numpy/pandas/lightgbm и их существующий closure вслед за установкой инструментов.
3. Создать новую `.venv-consolidated` через `python -m venv`; старую `.venv` оставить для rollback. `python -m pip install -r requirements-dev.lock`, затем `pip check`, inventory JSON, Ruff и deptry. Нельзя использовать `pip freeze` общей dev-среды как runtime lock.
4. Отдельную чистую runtime-среду установить только из `requirements.lock`; проверить отсутствие pytest/httpx/psutil и успешные import, bundle load, API/CLI inference. На Docker Linux проверить фактические marker и `libgomp1`.
5. Deptry запускать по каноническим first-party модулям с явным package/module mapping (`python-multipart`/`python_multipart`), учитывая CLI uvicorn и multipart как контрактные зависимости. Замечания инструмента не являются автоматическим разрешением удалить пакет.
6. После тестов сохранить новые lock hashes, новый inventory и таблицу фактически удалённых runtime пакетов. До этого этапа результат — предложение, не состоявшийся выпуск.

Audit commands: чтение requirements/Dockerfile; `rg` imports/dynamic calls; `.venv/Scripts/python.exe -m pip list --format=json`; `.venv/Scripts/python.exe -m pip check`; AST/metadata обход выполнен Python в исходной `.venv`. Новое обучение, uninstall и изменение requirements не выполнялись.

## Выполненная миграция Gate 7

После разрешения root, полученного после regression gate (219 тестов и побитовое совпадение полного CSV двух стратегий), подготовленные manifests и locks перенесены в корень. Это последующий этап; предыдущие разделы сохраняют исходный снимок. Разрешение uv universal выполнено с ограничениями всех baseline-версий, без обновления прежних пакетов. `requirements-training.*`, `requirements-dev.lock` и `requirements-research.*` добавлены; runtime требования исключают psutil и явно объявляют starlette.

Созданы **две новые среды**, исходная `.venv` сохранена. Реальные `pip list`/`pip check`:

| Среда | Пакетов с pip | Пакетов без pip | pip check |
|---|---:|---:|---|
| Исходная `.venv` | 42 | 41 | Пройден |
| `.venv_consolidated` (dev lock) | 39 | 38 | Пройден |
| `.venv_runtime` (runtime lock) | 24 | 23 | Пройден |

Во всех трёх средах numpy 2.5.4, pandas 3.0.6, lightgbm 4.7.0; исходные версии остальных сохранённых пакетов не изменены. Runtime не содержит pytest, httpx, psutil, Ruff, deptry, matplotlib или coverage. Dev добавляет только закреплённые инструменты ruff 0.17.1, deptry 0.25.1 и их новые транзитивные requirements-parser 0.13.1 / tomli 2.5.0. Инвентарь и точные результаты — `dependency_clean_environments.json`; installation logs — `dependency_dev_install.log`, `dependency_runtime_install.log`.

Создан `pyproject.toml` с Ruff E9/F для src/app и deptry для канонических src/app. Read-only Ruff: **0 замечаний** (`dependency_ruff_initial.json`). Deptry: **20 файлов, 0 замечаний** (`dependency_deptry_initial.json`, `.log`). Точечные DEP002 exceptions только для uvicorn (CLI/startup) и python-multipart (FastAPI upload). Автоматическое исправление или форматирование кода не запускалось; защищённые preprocessing-файлы, source и Dockerfile не изменялись этим агентом.

Фактический ledger — `dependency_changes.csv`, 45 package rows: 10 пакетов удалены только из runtime install и сохраняются в соответствующих группах. Полная установка runtime на Linux и Docker остаётся отдельным последующим gate: universal resolution не заменяет реальный container run.

В чистой `.venv_runtime`, где нет pytest/httpx/psutil, реально выполнена последовательная загрузка и inference обеих поставок на 180-дневном входе. Каждый результат — 562496 строк; CSV `%.17g` **побитово совпал** с предконсолидационным reference: nonton-v1 SHA-256 `354ae527536640ce4e56012e233f3ead679e616ea51f1d2a6f423014b681377a`, equal4:P1 `310d000f954f48e389661954c9a3d2ac38815d603bae7c9cfc40409015fbd164`. Runtime успешно импортирует FastAPI/Starlette/Uvicorn/python_multipart и сверяет manifests обеих моделей. Incumbent inference 6.039 с, equal4 inference 14.127 с, model loads отдельно 0.020/3.004 с; это единичные проверки, не доказательство ускорения. Машинный результат — `dependency_runtime_inference.json`. Equal4 загрузил ровно три модели (daily, weekly, article); дублированного shape Booster нет.
