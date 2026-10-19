# Независимая проверка консолидированного проекта

Проверяющий: агент C, 19 октября 2026. Это ограниченная перекрёстная проверка внутри той же команды: агент ранее написал `src.cli`, `tests/test_cli.py` и `tests/test_unified_runtime.py`. Поэтому проверка не заявляется полностью внешним аудитом. Проверяющий не обучал модели, не менял их веса и не выполнял promotion. Другие реализации проверялись чтением и собственными исполнимыми проверками.

## Вердикт

**PASS для проверенных исходников, зависимостей, переноса моделей, CLI/API и обоих окончательных Docker-образов.** Активным остаётся nonton-v1; equal4:P1 технически доступен через ту же архитектуру и проверенный candidate image. Это не заключение о его гарантированном превосходстве по точности. Целостность окончательного release ZIP проверяется отдельным sidecar после упаковки; этот документ не выдаёт ещё не созданный архив за проверенный.

## Исполнено проверяющим

- `independent_release_check.py`: сверены с исходным manifest **403 защищённых файла**, включая **387 NPZ**, шесть source-bound модулей incumbent, official scorer, production model/cache и прежние корневые ZIP. Все SHA-256 совпали. Это более широкий scope, чем прежние 151 forecast NPZ: здесь учтены все NPZ, вошедшие в текущий pre-merge inventory.
- Для **10 исходных строк cleanup ledger** оригиналы в `legacy_source.zip` совпали с pre-merge SHA-256. Шесть `archive_remove` действительно отсутствуют; четыре `merge` оставляют необходимые research/training adapters и используют общие реализации. Оригинал дополнительно сокращённого `scripts/predict.py` сохранён в pre-merge snapshot. Snapshot независимо проверен по полному SHA-256; повторно хэшированы **все 1003 extracted rollback файла**, каждый совпал с pre-merge inventory (`independent_review_evidence/rollback_hashes.json`). Реальный rollback replay выполнен root-скриптом `verify_rollback.py`, результат прочитан: 562496 строк, максимальная разница 3.553×10⁻¹⁵; проверяющий отдельно этот inference не повторял.
- В обеих новых средах повторно выполнен `pip check`: нарушенных зависимостей нет. Повторные Ruff E9/F для `src/app` и deptry с областью из `pyproject.toml` прошли. Это не объявление отсутствия lint-проблем во всех исторических research/external источниках.
- В чистой `.venv_runtime` отдельно вызван настоящий `python -m src.cli predict` с incumbent и 180-дневными CSV. Получены **562496 строк**, ключи и значения совпали с regression reference точно. Единственное изменение CSV bytes — явный LF вместо прежнего CRLF: после нормализации line endings bytes совпадают. SHA-256 нового CLI CSV: `ec1423820e9d13689f38b5d9dd2d82b2eb067f7e06fe123fecab9898991d98c3`. Численного изменения forecasting не обнаружено.
- На копиях config/manifest реального migrated bundle отдельно проверено повреждение: изменение config отвергнуто как artifact hash mismatch, изменение bundle_id — как manifest identity mismatch. TXT использовались только для чтения через hardlinks; оригинальный bundle повторно прошёл `verify_runtime_bundle` после проверок. Результат — `independent_review_evidence/corruption.json`.
- Повторно исполнены **60 cases**: canonical components, unified runtime, metrics и independent backend regressions — 60 passed, одна известная FastAPI/TestClient deprecation warning. Отдельно после исправления Docker CLI — **19 CLI cases passed**. Эти 79 cases не прибавляются к полному набору как уникальные новые tests.
- Независимо пересчитаны **25 forecast×origin** из нового provided180 backtest по всем пяти официальным метрикам. Использованы напрямую исходные `smape_series`, `bias_abs_series`, `wape`, `rmse`, `rmsle`, без нового backtest scorer; максимальное расхождение CSV — **2.842×10⁻¹⁴**. Проверены origin, history_days=180, shape (64,8789), конечность и неотрицательность. Полный квадратичный `compute_all_metrics` merge для этих 25 панелей не запускался. Подробные расхождения — `independent_review_evidence/official_metric_errors.csv`.

Машинные результаты основных проверок: `independent_review_evidence/checks.json`, `metrics.json`, `corruption.json`, логи Ruff/deptry и полноразмерного CLI. Прочитан окончательный clean-environment regression root: **238 passed** за 61.56 с в `final_tests.log`, одна известная deprecation warning. Прежние **237 passed** в `full_regression.log` и targeted **39 passed** в `cli_compatibility.log` не прибавляются к этому количеству как уникальные tests.

## Найденная и исправленная ошибка

QA обнаружил, что `cli docker test --image <candidate>` не передавал Strategy verification script и выбирал incumbent reference по умолчанию. С разрешения root добавлен явный `--strategy nonton-v1|equal4`, проброшенный в `-Strategy`; meaningful argv regression включён в 19 cases. Окончательный `src.cli` в обоих финальных образах проверен по SHA-256. Исправление не меняет bound runtime или model TXT.

Вторая найденная QA ошибка: candidate image изначально копировал repository config с `active_strategy=nonton-v1`, хотя в `/app/model` находился component bundle. API через MODEL_DIR мог работать, но CLI default config противоречил этому выбору. Root добавил build-time запись image-local config из выбранного model config; repository active release не меняется. Новый config проверен исполнением `configured_selection()` внутри обоих окончательных образов; HTTP проверки выполнены после этой правки, прежний Docker probe не выдаётся за финальный.

Совместимый `scripts/predict.py` после дополнительной правки root делегирует каноническому CLI predictor. Его прежние flags сохранены; общая проверка теперь соответствует API, включая metadata sales. Отдельная проверка старого и нового command path прошла в 39-case scope. Историческая версия сохранена в pre-merge snapshot.

Последняя правка research adapter добавляет пять новых shared-module hashes в будущие training manifests, чтобы после дедупликации research reproducibility зависела от реальных реализаций. Parent manifests и веса не изменены; поздний targeted scope в `legacy_adapter_final_tests.log` — 16 passed. Это изменение не входит в serving path и не меняет два frozen Docker image.

## Архитектура и границы качества

Активный `config/runtime.json` однозначно задаёт `nonton-v1`. `src.runtime` переключает версии явно, не подменяя encoder или preprocessing incumbent. Canonical runtime не импортирует `scripts`, `integration` или research defaults. Новый bundle проверяет hashes, feature ordering, catalog/encoding identity, dependency versions и provenance до выбранного model load. Для S используются те же D/W, отдельного shape Booster нет. API сохраняет атомарную публикацию cache и single-worker policy.

История — вся предоставленная, минимум 180 календарных дней. `long_mean` сохраняет full provided history, остальные окна ограничены; historical backtest намеренно передаёт ровно 180 дней. Он проверяет serving существующих full-history-trained весов и input-derived membership, а не новый rolling-180 training protocol. Каталог включает сырые sales с нулевым quantity; unknown output IDs детерминированно получают ноль. Stock-only IDs не добавляются в feature catalog.

В provided180 результатах equal4 немного улучшает все пять средних метрик относительно corrected D на одинаковых четырёх development origins. Это не доказательство превосходства над incumbent на четырёх 180-day origins: его сохранённые исторические TXT доступны лишь на двух. Повторно использованные окна и terminal не становятся новым untouched test. Cleanup сам по себе не означает улучшения прогнозной точности.

## Окончательные Docker-образы

Проверяющий самостоятельно запустил lightweight Python внутри обоих frozen images: SHA-256 всех **20 файлов src/app** совпал с окончательным host tree, выбранный model manifest совпал, config указал `/app/model` и правильную стратегию. CSV/NPZ под `/app` отсутствуют. Данные — `independent_review_evidence/final_images.json`.

| Показатель | nonton-v1 | equal4:P1 |
|---|---:|---:|
| POST, секунд | 11.305632 | 21.868425 |
| Повторный POST, секунд | 11.505580 | 20.933966 |
| Peak cgroup memory, байт | 1325481984 | 4691660800 |
| Offline/API max abs difference | 3.553e-15 | 1.066e-14 |
| Docker inspect Size, байт | 143563315 | 147131116 |

Это отдельные последовательные acceptance measurements, не статистический latency benchmark. Более ранний incumbent POST 16.867 с пересекался с candidate image build и заменён последним последовательным прогоном. Образы работали с `--network none`, 4 CPU и 6 GiB; container inspect подтверждает эти ограничения и окончательный image ID. Оба выдали полный grid 562496 строк, byte-identical repeat, сохранность cache после ошибочного POST и пустой cache после restart. GET CSV/JSON/filtered уложились менее чем в секунду на окончательных прогонах. Runtime package inventory не содержит pytest/httpx/psutil/Ruff/deptry/matplotlib/coverage.

Идентификаторы:

- nonton-v1: `sha256:eec978ddc812e8599afd82c04d6da2325b247a0bd0ac51a969ba7738b31d75bb`.
- equal4:P1: `sha256:6ce94440b4f5a040d0a7129787af28340afa222e81bd2fe793ed81a3e181e8fc`.

Самостоятельно сверены forecast CSV hashes с verification JSON, actual container image IDs, resource limits и restart JSON. Итоговая копия прочитанных результатов — `independent_review_evidence/docker_checks.json`. Исходные HTTP probes исполнял root; проверяющий не приписывает себе второй полный API inference.

Остаётся отдельный package-integrity gate после записи ZIP и release manifest. Никакого нового fit или автоматического promotion для завершения этого gate не требуется.
