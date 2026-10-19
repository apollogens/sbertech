# Независимая перекрёстная проверка Docker, API, CLI и упаковки

Проверяющий Agent B, 19 октября 2026. Docker/API/CLI и packaging реализованы другими участниками; проверяющий ранее отвечал за зависимости и не выдаёт повторную самооценку dependency migration за независимый общий аудит. Здесь выполнены собственные лёгкие контейнерные проверки и инспекция чужого кода. Полный HTTP inference повторно проверяющим не запускался: соответствующие результаты явно атрибутированы root.

## Incumbent image: подтверждено

**Статус superseded:** приведённая ниже проверка относится к предварительному image `db3c01b293e7`. После неё reviewer C обнаружил различие default CLI config и API MODEL_DIR в candidate image. Root исправляет build-time config и пересобирает обе финальные tags; прежний inventory сохраняется как предварительное свидетельство и не подтверждает окончательные image IDs. Финальный Docker verdict ожидается после повторной проверки.

В самостоятельно запущенном временном `docker run --rm --network none --entrypoint python nonton:consolidated-v1`:

- Image ID `sha256:db3c01b293e73bb3d78a723efeabb0bf6aa86043a35036d2ba9403e0f3c6333c`.
- Фактическое Linux runtime окружение содержит **22 пакета без pip**, тестовых/исследовательских pytest/httpx/psutil/Ruff/deptry/matplotlib/coverage нет.
- В `/app/model` ровно `catalogs.json`, `config.json`, `lightgbm.txt`, `manifest.json`, `training_record.json`; второго модельного bundle, raw CSV, tests/research/integration/reports/data внутри `/app` нет.
- **21 файл** src/app/config независимо хэширован в image и сопоставлен с текущими host sources: все совпадают, включая окончательный `src/cli.py`.
- Image configuration: один uvicorn worker; `/app/model`, без host raw path. Фактическая версия Python 3.12.15; контракт требует major/minor 3.12, поэтому отличие patch от Windows 3.12.10 допустимо.

Машинный результат собственных проверок — `dependency_docker_independent_inventory.json`. Dockerfile закрепляет base digest `a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`, сохраняет необходимый `libgomp1`, устанавливает только runtime lock и копирует выбранный `MODEL_BUNDLE` в `/app/model`. `.dockerignore` исключает остальные каталоги и pycache. Docker build context может включать два разрешённых каталога моделей, но финальный COPY переносит только выбранный; отсутствие второго bundle подтверждено фактическим image inventory.

Прочитаны root evidence `docker_nonton-v1/verification.json` и `restart.json`: полный HTTP прогноз 562496 строк, offline/API difference 3.553×10⁻¹⁵, repeated POST побитово идентичен, ошибка не повреждает cache, restart возвращает пустой cache и успешный health. Контейнер исполнялся с network none, 4 CPU, 6 GiB; зарегистрированный cgroup memory peak 1325944832 байт. Эти HTTP измерения исполнены root, не данным проверяющим.

Docker inspect `.Size` и табличный `docker image ls` показывают разные величины учёта хранения; улучшение размера на основании их прямого сравнения не заявляется.

## CLI и API: инспекция общего пути

`src.cli` принимает явные `--config`, `--model-dir`, `--strategy`. `selection()` вызывает общий `configured_selection`; CLI predict использует те же `app.validators`, затем `src.runtime.predict_64`. `serve` очищает старый FORECAST_CONFIG и явно задаёт MODEL_DIR/FORECAST_STRATEGY; `Predictor.load` читает FORECAST_STRATEGY. Значит D/W/S/A/equal4 выбираются общим runtime, а не копией прогнозного приложения. Single-worker policy остаётся в API lifespan.

`cli docker test` передаёт выбранный `--strategy` в PowerShell `-Strategy`; код инспектирован после исправления reviewer C. Это исключает известную ошибку выбора incumbent reference при проверке candidate image. Обратная совместимость `scripts/predict.py` сохранена через делегирование каноническому predictor. Config default остаётся nonton-v1.

## Упаковка: инспекция границ

`src.cli package` проверяет соответствующий manifest перед записью, включает только объявленные файлы и manifest, запрещает path traversal, повторно сверяет SHA-256 каждого содержимого ZIP и публикует архив через atomic replace. Это **архив модели**, его нельзя представлять полным автономным проектом без runtime sources/dependencies. Полноценный финальный project release подлежит отдельной проверке своего manifest и extracted execution.

## Ожидаемые заключительные свидетельства

На момент первичной записи candidate image ещё собирается. Этот отчёт пока подтверждает incumbent image и инспекцию общего пути; общий Docker PASS двух стратегий будет дан только после candidate inventory, HTTP/restart evidence. Окончательный project ZIP также ещё не проверен этим агентом.

## Повторная проверка окончательных frozen images

После обнаружения reviewer C root исправил build-time `config/runtime.json`: active_strategy записывается из выбранного model config, active_bundle всегда `../model`. Обе images пересобраны; эта проверка относится к окончательным IDs и заменяет предварительную оценку выше:

| Image | Окончательный SHA-256 ID | Default configured_selection | Linux runtime без pip |
|---|---|---|---:|
| nonton:consolidated-v1 | eec978ddc812e8599afd82c04d6da2325b247a0bd0ac51a969ba7738b31d75bb | /app/model, nonton-v1 | 22 |
| nonton:consolidated-equal4 | 6ce94440b4f5a040d0a7129787af28340afa222e81bd2fe793ed81a3e181e8fc | /app/model, equal4:P1 | 22 |

Проверяющий самостоятельно запустил обе final images с `--rm --network none` и явно проверил default config selection, identities, distributions, содержимое `/app` и SHA-256 **20 файлов src/app** каждой image относительно host. Все совпали. Config candidate намеренно отличается от host incumbent selection; он проверен семантически, а не объявлен побитово равным host config. Тестовых/исследовательских пакетов, raw CSV, внешних/исторических каталогов и второго bundle нет. Candidate содержит ровно пять model-файлов, из них три Booster TXT; сумма TXT — **808013424 байт**. Финальная самостоятельная фиксация — `dependency_docker_final_inventory.json`.

Размеры фиксируются в разных представлениях Docker без попытки объявить их одинаковой мерой: `.Size` image inspect — 143563315/147131116 байт; `docker image ls` — **619MB / 1.43GB** соответственно. С учётом реальных 808 MB TXT нельзя описывать candidate как модель размером 147 MB без указания метода учёта. Ускорение, сокращение памяти или superiority ансамбля этой проверкой не устанавливаются.

На этом этапе независимая лёгкая image/config проверка обоих окончательных образов пройдена. Final HTTP/restart candidate и полный project ZIP ещё ожидаются отдельно.

## Окончательный Docker/API verdict: PASS

Проверяющий прочитал опубликованные HTTP/restart результаты обеих final images и самостоятельно связал `image.json` → `container_inspect.json` → frozen image IDs из таблицы выше. Проверены network none, 4 CPU, 6 GiB, статус passed, 562496 строк, repeated POST, error-preserves-cache и empty-cache-after-restart. Результат этой отдельной проверки evidence — `dependency_docker_http_evidence_review.json`.

Equal4: POST 21.868 с, повтор 20.934 с, cgroup memory peak 4691660800 байт, offline/API maxdiff **1.066×10⁻¹⁴**. Incumbent final image также прошёл HTTP/restart с maxdiff 3.553×10⁻¹⁵; root отдельно повторяет последовательный timing после остановки candidate, поэтому сравнительный вывод о скорости здесь не делается. В обоих случаях численная разница существенно меньше 10⁻¹², повторные HTTP CSV побитово детерминированы. Это технический PASS общего serving для обеих стратегий; качество ансамбля и promotion не оцениваются этим Docker review.

Полный project ZIP ожидается отдельным packaging gate. Предварительный superseded inventory сохраняется исключительно для истории и не используется как основание окончательного PASS.

## Финальное уточнение перед упаковкой

Root завершил отдельный последовательный incumbent replay после остановки candidate: POST **11.306 с**, повтор **11.506 с**. Проверяющий повторно прочитал verification/restart evidence и связал их с тем же окончательным image ID; `dependency_docker_http_evidence_review.json` обновлён. Candidate measurement остаётся 21.868/20.934 с. Это acceptance times на конкретном запуске, без утверждения статистического ускорения.

При инспекции `package_release.py` проверяющий обнаружил, что повторная упаковка могла захватить будущий extraction directory в consolidation. Root добавил явные исключения extracted/package_extracted/release_extracted и rollback. Первоначальная находка и исправление относятся к воспроизводимости package selection; runtime sources и модели не менялись.

**Итог scope данного агента:** обе окончательные Docker images, config/CLI/API route к общему runtime и модельная упаковка технически проверены. Общий full-project ZIP пока не опубликован на момент записи; его extraction/replay и final manifest — обязательный отдельный peer packaging gate, за который данный предварительный Docker PASS не выдаётся. Текущий отчёт завершён до формирования ZIP, чтобы root мог зафиксировать его hash в окончательном release manifest.
