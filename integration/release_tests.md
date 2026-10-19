# Проверка сохранённого выпуска nonton-v1

Дата: 19 октября 2026. Проверяющий инженер E. Обучение не запускалось. Рабочий production `src/`, `app/`, `model/`, исходный `submission.csv` и прежние Docker tags сохранены.

## Сохранность

До изменения реализаций создан восстанавливаемый `release/pre_integration_snapshot.zip`: 724 файла, включая исходный код, тесты, документацию, модель, исследования, отчёты, зависимости и оба CSV submission. SHA-256: `e9d505e4d2deb622897e3a7e4d9936e342696bd878efeec3f7f9e30d2dd9a548`. Хеши и размеры находятся в `release/preservation_manifest.json`. Архив исключает виртуальные окружения, вложенные `.git`, Python cache и прежние ZIP; прежние ZIP сохраняются на месте и отдельно захешированы. Полные исходные сырые CSV входов не дублируются в ZIP.

Проверка `release/verify_artifacts.py`: 724/724 файла без изменений, 152/152 NPZ без изменений (151 исследовательский прогноз плюс `cache/panel.npz`), все прежние ZIP без изменений. Дополнительная проверка старого `reports/remediation/delivery_manifest.json`: 409/409 файлов и прежний ZIP совпадают. Сведения о Git, зависимостях, Python и предыдущих Docker images записаны в `release/`.

Модель: `nonton-v1`, LightGBM Tweedie 1.3, 220 деревьев, 45 признаков, порог 0.25. Bundle ID: `9267e65f0ca9e62b636d185fe7731a71b4e24a8b5110fa830701d5beb0d0f50a`. Реальное чтение и verification bundle внутри отдельного контейнера прошло; хеши `release/container_model_check.json` совпадают с host model. Новые экспериментальные ансамбли в serving не включены.

## Исполненные тесты

- `.venv/Scripts/python.exe -m pytest -q`: **156 passed**, 40.35 с; `release/tests.log`.
- `.venv/Scripts/python.exe -m pytest reports/qa/check_backend_independent.py -q`: **21 passed**, 1.92 с; `release/independent_backend_tests.log`.
- Итого воспроизведены прежние **177** тестов в двух запусках с различной областью поиска. Есть одно предупреждение Starlette об устаревающем TestClient transport; это не ошибка теста.
- `.venv/Scripts/python.exe integration/release_probe.py`: полноразмерный offline/API parity, POST повторно, GET CSV/JSON, GET фильтр, пустой cache перед POST, сохранение и повторное чтение submission — passed.
- `.venv/Scripts/python.exe integration/release/verify_artifacts.py`: независимая проверка сохранности и полного CSV без вызова production submission validator — passed.
- `powershell -NoProfile -ExecutionPolicy Bypass -File integration/docker_verify.ps1`: HTTP через loopback в контейнере `--network none --cpus 4 --memory 6g`; полный POST, GET CSV/JSON/фильтр, сравнение offline и restart с пустым cache — passed. На машине Docker Desktop первоначально не был запущен; инженер запустил установленный Docker Desktop и проверил доступность Engine. Верифицированный контейнер остановлен после проверки.

## Полноразмерная проверка

Вход: неизменённые `data/parity/sales.csv` и уже очищенный `data/parity/stock.csv`; их SHA-256 записаны в `release/parity.json`. Это полная история, не новый сырой stock upload. Конец истории 2026-07-31, прогноз 2026-08-01—2026-10-03. CSV проверен после записи: ровно **562496** строк, 64 последовательные даты, 11 складов, 799 товаров, точная последовательность полного декартова grid, 4 обязательных столбца, без дубликатов, отрицательных и неконечных значений.

Host offline/API max absolute difference **0.0**; повторный POST побитово идентичен. Host/container max absolute difference **3.552713678800501e-15**, ниже допуска 1e-7. Различие с сохранённым исходным submission — **4.9918806865889565e-09** из-за прежнего формата `%.10g`; исходный файл не заменён. Новая копия `release/submission.csv` и host API CSV имеют SHA-256 `dd8c2b34b1a7900a7392dc427b8eae7116f0f49828693942c925d47342f61dc1`. Docker CSV отличается последними битами float между платформами: его SHA записан отдельно; байтовая идентичность между Windows и Linux не заявляется.

| Измерение | Host TestClient | Docker HTTP loopback |
|---|---:|---:|
| Загрузка bundle, с | 0.0195 | отдельно не измерена |
| Полный offline, с | 11.4734 | отдельно не измерен |
| Полный POST, с | 34.8045 | 34.3760 |
| Повторный POST, с | 39.7371 | отдельно не измерен |
| GET CSV, с | 1.7214 | 1.0162 |
| GET JSON, с | 0.9477 | 0.5178 |
| GET фильтр, с | отдельно не измерен | 0.0389 |
| Память, байт | 2838343680 sampled process RSS | 3810914304 cgroup memory.peak |

Host RSS включает TestClient, запросы и ответы; Docker peak включает API, in-container HTTP probe и последующее чтение CSV. Это ресурсы всего проверяемого сценария, не изолированная память модели. CPU quota подтверждена `400000 100000`, memory max **6442450944**. Внешней сети у контейнера нет. POST не запускает training по сохранённому serving коду. Ограничения 6 GiB и 4 CPU соблюдены фактическим cgroup enforcement; нет заявления о новом прогнозном выигрыше.

Новый tag: `nonton:integration-verified`; image ID `sha256:1d7f2a17f7cd115177d12daf1861a62511e0de37b8d02debc3b00d2244d1b01e`. Docker `image ls` показывает **645 MB**, `image inspect Size` — **148796116** байт; это разные представления Docker storage, оба сохранены без подмены. Build использовал cache; cold build и его время не измерялись. Старый `nonton-forecast:remediation` ID `sha256:5bb1ea1fea5a136cfc54c2a80701baefd1f97d23a50e17d9b1a42b476913faef` сохранён.

## Границы вывода

Результаты подтверждают техническую воспроизводимость сохранённого incumbent, корректность нового изолированного CSV и отсутствие регрессии serving. Они не устраняют известную историческую проблему каталога обучения incumbent и не доказывают независимый выигрыш качества. Выбор между corrected challengers принадлежит отдельному исследованию. Старый официальный deliverable остаётся неизменённым.

## Новые модульные проверки экспериментальной интеграции

Команда `.venv/Scripts/python.exe -m pytest integration/test_ensemble_engine.py integration/test_catalog_policy.py -q` исполнена отдельно: **16 passed** (10 ensemble engine и 6 catalog policy), результат `release/integration_tests.log`. Сумма проверенных pytest cases на этом этапе — **193**: 177 прежних и 16 новых. Это отдельные области проверки; дополнительные независимые научные проверки описываются своими отчётами.
