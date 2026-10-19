# Транзакционная публикация прогноза

## Что было обнаружено

Исходный `app/predictor.py` уже вычислял результат до присваивания под `cache_lock`, сохранял кэш при ошибке inference и исключал второй HTTP POST через `post_lock`. Эти работающие гарантии сохранены. Объявлять исходный кэш полностью неатомарным было бы неверно.

Подтверждённый дефект: `get_cached_forecast()` возвращал внутренний изменяемый DataFrame. Тест на исходном коде из `original_release.zip` меняет `quantity` у возвращённого объекта и видит изменение внутри кэша. Также отсутствовали cache version, model ID, input identity и технический запрет обычного многопроцессного запуска. Поэтому связь между результатом и конкретными загруженными файлами нельзя было диагностировать.

## Исправление и гарантии

Используется один процесс и кэш в памяти без внешних сервисов. POST удерживает неблокирующий `post_lock`; конкурирующий POST получает HTTP 409. Входы получают SHA-256 от точных исходных upload bytes. Новый DataFrame полностью рассчитан, проверен по значениям, датам и полному Cartesian grid и отсортирован до публикации. Только затем под `cache_lock` одновременно фиксируются копия результата и metadata: монотонная версия, model bundle ID, SHA-256 sales/stock и время commit UTC.

GET возвращает защитную копию одного committed snapshot. Внутренний объект не выдаётся вызывающему; metadata также копируются. Успешный POST публикует только целый новый snapshot. Failed validation/inference не увеличивает версию и сохраняет прошлые quantity и input hashes. Одновременный GET видит целиком старую либо новую версию, а потоковая сериализация удерживает собственный DataFrame. Порядок POST: первый захвативший lock выполняется; остальные отвергаются, очередь не создаётся.

CSV/JSON ответы содержат `X-Forecast-Version`, `X-Model-ID`, `X-Input-sales-SHA256`, `X-Input-stock-SHA256`. `/diagnostics` возвращает committed metadata и явные worker/restart policies. Контракт `/health` сохранён.

После рестарта кэш пуст: GET получает 409 до первого успешного POST. Поддерживается только `uvicorn app.main:app --workers 1` в одном экземпляре. Dockerfile уже использует 1 worker. Startup отклоняет `WEB_CONCURRENCY`/`UVICORN_WORKERS` больше 1, аргументы `--workers 2`, `--workers=2`, `-w 2`, `-w2` и дочерние multiprocessing worker processes. Несколько независимо запущенных процессов/контейнеров за балансировщиком и нестандартные launcher configurations с скрытыми worker settings не поддерживаются; общий кэш между ними не реализован. Это ограничение развёртывания, а не заявленная поддержка distributed cache.

Основания: [Python threading Lock](https://docs.python.org/3/library/threading.html) документирует атомарные acquire/release и неблокирующий захват; [FastAPI server workers](https://fastapi.tiangolo.com/deployment/server-workers/) описывает несколько серверных процессов. Локальные гарантии проверяются тестами, а не выводятся только из документации.

## Выполненные проверки

```powershell
.venv\Scripts\python.exe -m pytest tests/test_remediation_backend.py tests/test_api.py tests/test_pipeline.py tests/test_qa_regressions.py -q
```

Промежуточный targeted run: **121 passed**, 6.27 s, 1 upstream deprecation warning. Новые HTTP concurrency tests запускают реальный второй TestClient POST в другом thread, удерживают первый через Event внутри inference, выполняют второй POST/GET и затем разрешают успех либо инъецированную ошибку. Проверены HTTP 409, неизменённый прошлый snapshot во время вычисления, атомарная новая версия после успеха, сохранение прошлой после HTTP 500 и возможность следующего POST после освобождения lock. Также проверены invalid upload, mutation isolation, последовательная замена с разными hashes, JSON headers и пустой кэш после restart.

Финальный независимый regression run `.venv\Scripts\python.exe -X utf8 -m pytest -q`: **177 passed**, 1 upstream deprecation warning, 36.63 s, exit 0; протокол `final_pytest.txt`.

## Реальные полноразмерные запросы

```powershell
.venv\Scripts\python.exe -X utf8 scripts/remediation_backend_probe.py --model-dir model --output-dir reports/remediation/backend_fullsize
```

В отдельном локальном uvicorn запущен один обслуживающий worker. Использованы реальные `data/parity/sales.csv` (256457024 bytes), `stock.csv` (195879181 bytes) и `offline.csv` (29958995 bytes). Upload передаётся клиентом потоково. Финальный bundle `9267e65f0ca9e62b636d185fe7731a71b4e24a8b5110fa830701d5beb0d0f50a` имеет `training_recorded`; результат нового обучения побитово совпал с прежними весами/config/catalog (`final_refit_parity.json`, независимый `review_final_artifact.json`: passed).

Повторный полноценный probe `backend_fullsize/benchmark.json`: **passed**.

| Проверка | Измеренный результат |
|---|---|
| Первый POST | HTTP 200, 35.683457 s, cache version 1 |
| Второй полноразмерный POST | HTTP 200, 36.102847 s, cache version 2 |
| Конкурирующий POST во время второго | HTTP 409 |
| GET во время расчёта замены | Полный прежний CSV, версия 1, побитовое совпадение |
| Невалидный POST после commit | HTTP 400; версия 2 и полный CSV сохранены |
| Повторный POST | Побитово идентичный прогноз |
| Полная сетка | 562496 строк = 11×799×64; 2026-08-01–2026-10-03 |
| Максимальная абсолютная разница с offline | **0.0** |
| Peak RSS дерева серверных процессов | **3278405632 bytes** |

SHA-256 точных загруженных файлов: sales `73e04d9c495dfb9f28e2daed2d9e97b9e6fc4252bfbd734a758fd6ba4a3434b8`, stock `15e33cfaa114a7d642d27c6e1abae35e41aad087a8f4261535e7f11acc6a7e17`; совпадение response headers проверено. Файлы `first.csv`, `during.csv`, `second.csv`, `cached.csv` и `server.log` сохранены рядом с benchmark.

Уточнение измерения памяти: на Windows `.venv` запускает launcher и дочерний процесс сервера. Исправленный probe суммирует RSS launcher и всех descendants каждые 50 ms; наблюдались 2 PID — это не два обслуживающих worker. Общие страницы могут учитываться в сумме несколько раз. Изначальный `benchmark_launcher_rss_only.json` содержит 4055040 bytes, измеренные только у launcher; **это недействительная оценка памяти сервиса**, она сохранена как след обнаруженной ошибки и не используется для ресурсного вывода. Результаты времени получены на локальном Windows HTTP-сервисе и не подменяют Docker/cgroup measurements.

Реальный прогон проверил успешную замену, исключение конкурентного POST и отказ входной валидации на полноразмерном committed forecast. HTTP 500 после инъекции inference error проверен отдельно синтетическими regression tests; такая инъекция в production inference для полноразмерного прогона не добавлялась. Независимый review кода/тестов и финального артефакта выполнен.

## Контейнерный прогон

Финальный `docker_benchmark.json` имеет `status=passed`, `network_mode=none`: POST **34.208721317 s**, peak cgroup memory **3939459072 bytes**, **562496 строк**, максимальная абсолютная разница offline/Docker **3.552713678800501e-15**. Размер образа **148796116 bytes**, cached build **1.7365938 s**. Эти cgroup measurements относятся к Linux-контейнеру; их не следует напрямую приравнивать к сумме RSS Windows launcher/process tree. Сборка использовала кэш слоёв.

`docker_command_status.json` подтверждает **exit 0** повторного полного запуска с раздельными stdout/stderr. Первый результат сохранён в `docker_benchmark_first.json` (POST 39.597909063 s); внешняя PowerShell-обёртка тогда получила `NativeCommandError` от stderr BuildKit, несмотря на успешные фактические stages. Повторный запуск устранил неоднозначность exit status, его показатели используются как финальные.

Независимый `review_docker_artifacts.json`: **passed** — reviewer проверил реальные файлы образа, их совпадение с app/src/model/requirements, полную forecast grid и parity CSV. Измерения HTTP runtime/cgroup выполнил root probe; reviewer самостоятельно не повторял полноразмерный HTTP запрос. Полноразмерная конкурентная замена кэша проверена отдельным локальным HTTP probe выше; Docker-прогон подтверждает контейнерный serving/parity и не подменяет concurrency evidence.

