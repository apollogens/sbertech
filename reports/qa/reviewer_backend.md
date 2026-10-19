# Независимый аудит backend — Agent C

Дата: 18.10.2026, рабочая папка `D:\SberTech`. Аудитор не изменял implementation, model, submission, существующие тесты и старые отчёты. Новые файлы: этот отчёт и `check_backend_independent.py`.

## Область и источники

Прочитаны `app/main.py`, `app/predictor.py`, `app/validators.py`, транзитивные пути `src/data.py`, `src/predict.py`, `src/submission.py`; `Dockerfile`, `.dockerignore`, requirements; `scripts/verify_parity.py`, `scripts/verify_docker.ps1`, `scripts/container_probe.py`, `tests/test_api.py`, документированные допущения. Выполнен разбор backend DOCX через zip/XML: `C:\Users\apollo\Downloads\Nonton_Backend_TZ_Forecasting_API.docx`, а также markdown ТЗ `C:\Users\apollo\Desktop\выборка\markdown hakaton.md`. DOCX сам маркирует свои решения и не заменяет требования организаторов.

В Git ещё нет коммита: `git rev-parse HEAD` завершился ошибкой unknown revision; исходные проектные файлы untracked. Поэтому ревизия фиксируется контрольными суммами, а не вымышленным commit ID. Начальный manifest сохранён главным аудитором в `initial_manifest.json`.

Путь запроса: multipart UploadFile → строгий CSV → validate_history → Predictor.predict → общий predict_64 → build_panel → snapshot/horizon_features → сохранённый LightGBM → проверка полного грида → атомарная замена RAM-кэша → StreamingResponse. GET берёт ссылку на завершённый неизменяемый DataFrame; обновление cache не меняет уже взятый snapshot. POST lock берётся до CSV parsing и освобождается после вычисления, перед завершением потоковой отдачи.

## Подтверждённые находки и исправления

### C-01, P2: повреждённые записи CSV молча восстанавливались pandas

Исходный `app/validators.py::read_csv` проверял strict csv.reader только для заголовка. Тела `a,b,c\n1,2\n`, `a,b\n1,2\n3\n` и `a,b\n"broken"suffix,2\n` принимались без InputError. В HTTP-тесте из корректной 180-дневной sales удалено последнее значение characteristic у одной строки: получен **200**, хотя контракт требует **400** для сломанного CSV. Это структурная потеря поля, отличная от явно переданного пустого значения `...,`.

Команда воспроизведения: `.\.venv\Scripts\python.exe -X utf8 -m pytest reports/qa/check_backend_independent.py -q`. Первый прогон: **16 passed, 4 failed**. Три failing проверки напрямую вызывали реальный read_csv; четвёртая проходила HTTP-обёртку с synthetic model stub.

Исправление интегрировал главный аудитор: strict csv.reader проходит все записи и проверяет число полей, blank lines сохраняют прежнюю политику. Независимая повторная проверка: **21 passed, 0 failed, 0 skipped**; добавлен положительный тест quoted embedded newline и явно пустой последней ячейки, чтобы не запрещать легальный CSV. Исправление проверено; модель не переобучалась, правила inference не изменились.

### C-02, P2: значения вне диапазона внутренней float32-панели

Главный аудитор воспроизвёл float64→float32 overflow при quantity/stock=1e40 и переполнение суммы нескольких допустимых значений. Исходная проверка конечности float64 пропускала эти входы; в модели появлялся inf. Исправление главного аудитора ограничивает значения и агрегированные quantity в app/validators.py:80–89, а также в общем offline data path. В независимом suite оба значения 1e40 отклоняются **422 VALIDATION_ERROR** до model stub; в отдельном запуске с настоящим LightGBM оба входа также дают **422**, прошлый cache сохраняется. Аггрегированное переполнение проверяет основной regression suite главного аудитора, а не данный независимый файл.

## Независимые исполнимые проверки

Новый файл `reports/qa/check_backend_independent.py` содержит **21 pytest-проверку**. Помимо новых CSV-repro, проверены реально перекрывающиеся в потоках POST, одинаковые и разные payload, 409 без очереди, GET предыдущего cache во время вычисления, атомарный переход на новый cache, сохранение cache после 422, пустой cache отдельного процесса/нового Predictor, дополнительные формы NaN/Inf/overflow. Concurrency не подменена предварительным ручным acquire lock: один inference удерживается Event-barrier, параллельный HTTP POST реально проходит endpoint.

Команда: `.\.venv\Scripts\python.exe -X utf8 -m pytest reports/qa/check_backend_independent.py -q`.

После fix: **21 passed за 2.71s**, один StarletteDeprecationWarning о переходе TestClient с httpx на httpx2. Warning не является отказом рабочего HTTP-сервиса.

Команда настоящей модели на контролируемой минимальной истории: `.\.venv\Scripts\python.exe -X utf8 reports/qa/check_backend_independent.py --real`.

Результат: успешно загружен сохранённый `model/lightgbm.txt`; POST **4.538256s**; **562 496** строк, конечные неотрицательные quantity, уникальные ключи, 64 даты **2025-06-30–2025-09-01**. GET article/warehouse/pair даёт **704/51 136/64** строки. Повторный POST байтово совпал; добавление 180 дней будущего stock с другими значениями не изменило прогноз. Это реальные inference и полный выходной каталог, но вход контролируемый, разреженный — не benchmark полного реального CSV. SHA256 результата: `f20c3d4aace63726dcc22e208a4fb6ea43bf57ddb18553d605aa8e550fd5a436`.

## Docker: способ и идентификация

Docker Desktop 4.88.0 / Engine 29.7.2, Linux amd64; host Windows 10 build19045, Python3.12.10,16.9646GB physical RAM,16 logical CPU. Изоляция benchmark: отдельный tag `nonton-qa-audit:verified`, отдельный контейнер `nonton-qa-audit-20261018`, `--network none --memory=6g --cpus=4`. Существующие образы/контейнеры проекта не удалялись.

Команды:

```powershell
docker build --no-cache -t nonton-qa-audit:verified .
docker build -t nonton-qa-audit:verified .
docker run -d --network none --memory=6g --cpus=4 --name nonton-qa-audit-20261018 nonton-qa-audit:verified
docker cp data/parity/sales.csv nonton-qa-audit-20261018:/tmp/sales.csv
docker cp data/parity/stock.csv nonton-qa-audit-20261018:/tmp/stock.csv
docker cp data/parity/offline.csv nonton-qa-audit-20261018:/tmp/offline.csv
docker cp reports/qa/check_backend_independent.py nonton-qa-audit-20261018:/tmp/check_backend_independent.py
docker exec nonton-qa-audit-20261018 python /tmp/check_backend_independent.py --container
```

Чистая сборка зависимостей заняла **69.3665172s**. После интеграции исправлений выполнена повторная сборка с использованием dependency layers: **4.050319s**, image `sha256:0e97325bd3211b278064013ed67653970da3b978e082d9e0e4393ef374acc534`, размер **148 784 892 bytes**. После финального усиления проверки sorted catalog выполнена ещё одна COPY-сборка: **2.296653s**, финальный image `sha256:393a092aeffb3159d5059aae2026dcc7426eff7321b4b39b88d5a0f0642f71a7`, размер **148 784 934 bytes**. Чистая сборка проверяла установку зависимостей, повторные — финальные исходники; эти времена не следует выдавать за единую no-cache сборку финального дерева.

В `/app` только src,app,model,requirements.lock. Train CSV в образ не входят; benchmark inputs копируются после старта в /tmp. Runtime версии совпадают с lock: numpy2.5.4,pandas3.0.6,lightgbm4.7.0,fastapi0.146.0,uvicorn0.54.0. Модель SHA256 `ebc9bafee00b294793f0ef2b01e9b8d1b42825bc461dc7fa4cdb603496fb3b52` совпадает с исходной. Значения deterministic=true,force_col_wise=true,seed20261018,num_threads4 зафиксированы в config; межплатформенная числовая parity измеряется отдельно и не выводится из этих параметров.

При первом запуске custom Docker probe обнаружилась ошибка пути импорта в самом QA harness (`ModuleNotFoundError: app.main`); исправлен выбор корня, сервис продолжал работать. Это не дефект production-кода и не скрытый успешный прогон.

Первый полный прогон исправленного image прошёл: POST **31.906086s**, repeat POST **32.185310s**, GET CSV **0.923982s**, GET JSON **0.484782s**; **562 496** CSV и JSON строк, ключи совпадают с offline. max abs difference **3.552713678800501e-15** при rtol=0,atol=1e-7. Повторный POST и GET CSV байтово идентичны; SHA256 `10cd625f921ef958a5626ff733005343a5996919963d5e81a183ea18b908bd8e` совпадает со старым `reports/container_forecast.csv`, то есть исправления не изменили нормальный прогноз. Отдельно сопоставлены все ключи и quantity JSON/CSV: max difference также **3.552713678800501e-15**.

Измерение первого прогона: peak cgroup **3 859 812 352 bytes**, peak server RSS (PID1, шаг0.1s) **3 455 287 296 bytes**, CPU server **78.73 CPU-s**, wall всего probe **66.891694s**. RSS — выборочный максимум, cgroup peak включает benchmark-процесс, файловый cache и сервер. Эти два числа имеют разный смысл. Все фактические размеры/времена укладываются в лимиты64GB/30GB/60min POST/10min GET.

Реальный restart контейнера подтверждён: `docker restart nonton-qa-audit-20261018`, затем HTTP GET /predict/all → **409** с текстовым detail и code REQUEST_ERROR. Негативный startup: `docker run --rm --network none -e MODEL_DIR=/tmp/qa_missing_model nonton-qa-audit:verified` завершился **exit1**, "Application startup failed"; сервис не объявил себя готовым без model/config.json. Это ожидаемо успешный негативный тест, а не непрошедшая приёмка.

Входы полного benchmark: sales **256 457 024 bytes**, stock **195 879 181 bytes**, offline эталон **29 958 995 bytes** из data/parity. Это явно очищенный stock, не исходный файл с отрицательными/конфликтующими строками; политика очистки описана в документации и реализуется общим preprocessing.

## Ограничения аудита

Docker image использует изменяемый тег python:3.12-slim и apt repositories, поэтому byte-identical пересборка на иной дате не доказана. Library lock обеспечивает фиксацию Python versions, но не всех системных бинарников. Проверка выполнена на одной машине и одном Linux/Docker environment; нельзя обещать точное время или битовую идентичность на произвольном железе.

Память входов читается целиком для каждого CSV; streaming относится к выходу. Это допустимо по фактически измеренному лимиту, а не доказательство ограниченного потребления для входов произвольного размера. Один worker является частью корректности RAM-cache: несколько workers без общего cache не поддерживаются. После рестарта нужен новый POST, это ожидаемая архитектура.

DOCX просит дополнительно логировать разрывы календарного покрытия и метаданные запросов. В текущем app нет специальных структурированных логов coverage/latency; имеются стандартные access logs Uvicorn и exception logs inference. Это операционное улучшение P3, не блокирующее установленный HTTP-контракт. В real schema отсутствуют cost_price/volume_weight; их отсутствие намеренно разрешено и явно описано в docs, не классифицируется как новый дефект.

## Финальное повторное подтверждение и signoff

На финальном image `sha256:393a092aeffb3159d5059aae2026dcc7426eff7321b4b39b88d5a0f0642f71a7` весь real-input HTTP probe выполнен повторно, включая два POST, полные CSV/JSON и фильтры. Результаты:

```json
{
  "network_mode": "none",
  "python": "3.12.15, GCC 14.2.0",
  "platform": "Linux-6.18.54.1-microsoft-standard-WSL2-x86_64-with-glibc2.41",
  "post_seconds": 33.76835534800006,
  "repeat_post_seconds": 32.38673870800005,
  "get_csv_seconds": 0.8908521900000324,
  "get_json_seconds": 0.4838001279999844,
  "repeat_and_get_byte_identical": true,
  "rows": 562496,
  "max_abs_difference": 3.552713678800501e-15,
  "tolerance": 1e-7,
  "json_rows": 562496,
  "json_max_abs_difference": 3.552713678800501e-15,
  "output_sha256": "10cd625f921ef958a5626ff733005343a5996919963d5e81a183ea18b908bd8e",
  "memory_peak_bytes": 3753984000,
  "server_peak_rss_bytes": 3223523328,
  "server_cpu_seconds": 81.12,
  "total_probe_wall_seconds": 70.38899868500005,
  "status": "passed"
}
```

CPU benchmark в среднем использовал 1.152 CPU core (81.12 CPU-s /70.389 wall-s) при лимите4. Из cpu.stat: usage87.133547s,user75.927238s,system11.206309s,16 throttled periods,throttled1.222547s. Cgroup включает процесс probe и весь runtime; CPU server измерен отдельно через psutil.Process(1).cpu_times. Нагрузочный benchmark не доказывает преимущества скорости относительно старого отчёта: измеренных latency before на неизменённом коде в этой независимой сессии нет.

Дополнительный set-based контроль после повторного benchmark отдельно прочитал max(sales.date) из реального CSV: **2026-07-31**. Полный ожидаемый Cartesian grid 64×11×799 сравнен как множество ключей с Docker CSV: **равен**, дубликатов нет, даты **2026-08-01–2026-10-03**, quantity конечные и неотрицательные. Реальный HTTP malformed underfull CSV на финальном image вернул **400 VALIDATION_ERROR**, последующий GET SHA256 остался прежним, т.е. ошибочный POST не перезаписал cache.

Независимые pytest после финального loader fix: **21 passed /0 failed /0 skipped за2.33s**. Отдельно успешно выполнены сценарии настоящей модели на180-дневной контролируемой истории, два полных Docker HTTP benchmark, restart, отрицательный startup, set-based grid, ошибки CSV и cache preservation. Эти сценарии не складываются искусственно с количеством pytest cases.

Финальные SHA256 production-файлов (совпадение src/predict.py дополнительно проверено внутри финального image):

| Файл | SHA256 |
|---|---|
| app/main.py | b68ae5e075c6c4cc2dd652c9cd101b4a5fd3a16569afcc71f75ad189fa775c3a |
| app/predictor.py | ac139efdada3f3e4d5c8267a36912df052435d38b13b55a2d30942ed682aaf77 |
| app/validators.py | 9937c2f5ee667c141d5e562b0e68f706e34d5640f40184113d2c51c4269a6eb6 |
| src/data.py | f13639b8e6c67b4ab0106abd1dc16b5ab191bd2c3b06f04fc4e94f0a6b88ebde |
| src/predict.py | 67c7a36178f2bfb1bbb7d465fa4aee98e977ab969c26bfd4687f2fc97a20bc47 |
| src/submission.py | 97626f668108143ececc488d9ed113964035a2e27f5d49d888a6cacfb3b6b6ff |

**Независимый signoff Agent C: PASS в пределах backend/API/Docker.** Подтверждённых открытых P0/P1 в этой области нет; воспроизведённые P2 CSV и numeric overflow исправлены и независимо проверены. Signoff не распространяется на валидность model-selection quality, статистическую оценку Bias или корректность ещё не исследованных ML путей: их утверждает главный аудитор по отдельным независимым результатам.

После signoff по поручению главного аудитора точный stdout JSON финального probe вместе с build/environment/image facts сохранён в `reports/qa/docker_benchmark.json`; JSON повторно прочитан и проверен. Сам probe benchmark-файл в /tmp не создавал, что явно отражено в provenance. Только созданный аудитором контейнер `nonton-qa-audit-20261018` удалён; финальный проверенный image сохранён, большой CSV повторно не копировался.
