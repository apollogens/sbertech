# Целостность артефактов

## Воспроизведённая проблема

В сохранённом `original_release.zip` загрузчик проверяет сортировку и уникальность каталогов, но не связывает их с весами. В тесте `test_frozen_original_accepts_wrong_sorted_catalog_fixed_loader_rejects` последний article заменяется на другой идентификатор с сохранением сортировки: исходный загрузчик принимает такой комплект, исправленный отклоняет с `Artifact hash mismatch: catalogs.json`. Это проверено на реальных текущих LightGBM-весах, без обучения.

## Контракт и реализация

`src/artifacts.py` создаёт обязательный `manifest.json`, версия контракта 1. SHA-256 фиксирует точные байты config/catalogs/весов, упорядоченные feature names и тип `float32`, явные отображения identifier → integer ID, полный inference config, исходники data/features/baselines/predict/submission/artifacts и версии NumPy/Pandas/LightGBM/Python major.minor. Упорядоченность mapping не исправляется автоматически. Сам manifest имеет `bundle_id`, полученный из его содержимого без поля `bundle_id`.

Каноническое представление: UTF-8 JSON, `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`, `allow_nan=False`; порядок элементов списков сохраняется. Загрузка пересчитывает все инварианты до создания Booster. Отсутствующий manifest приводит к отказу; тихого legacy fallback нет. Файл manifest пишется через временный файл и replace; упаковка производится вне работающего сервиса, весь комплект нельзя менять на месте во время загрузки.

SHA-256 обеспечивает обнаружение несогласованного комплекта относительно доверенного manifest. Это не цифровая подпись и не защита от злоумышленника, способного заменить одновременно manifest и все файлы. Принцип входной схемы основан на [официальной документации MLflow Model Signatures](https://mlflow.org/docs/latest/ml/model/signatures/); вычисление SHA-256 — [документация Python hashlib](https://docs.python.org/3/library/hashlib.html). MLflow как зависимость не добавлен.

## Происхождение и ограничения

При первой упаковке прежних файлов без manifest `scripts/package_model.py --model-dir PATH` записывает `provenance.status=reconstructed_unverified`, `training_run_id=null`. Это означает только фиксацию текущих файлов. Хэш текущего каталога не доказывает, что исторические веса обучались именно с ним. Существующий manifest CLI только проверяет: повреждённый комплект не получает новый доверенный fingerprint автоматически, а подтверждённая запись обучения не понижается до reconstructed.

В финальном релизе выполнено новое документированное обучение командой `.venv\Scripts\python.exe -X utf8 scripts/train_final.py --output-dir reports/remediation/retrained_model`. Run `final-20261018T181325Z-cdd29774bb1b`: cutoff 2026-07-31, 1476552 обучающих строк, 220 деревьев, fit **22.886230 s**. Проверенный комплект перенесён в `model/`; его provenance — `training_recorded`, bundle ID `9267e65f0ca9e62b636d185fe7731a71b4e24a8b5110fa830701d5beb0d0f50a`.

`training_record.json` включён в хэши manifest. Loader дополнительно сверяет run ID, training-data hashes и model hash между журналом и manifest. Сохранены хэши cache panel, catalog, selection и исходников train/data/features. `final_refit_parity.json` подтверждает: новые `lightgbm.txt`, `config.json`, `catalogs.json` **побитово идентичны** сохранённому исходному release. Изменены воспроизводимость и контракт комплекта; прогнозная архитектура и численный результат сохранены. Историческое происхождение прежнего комплекта не объявляется ретроспективно доказанным: доказательства относятся к вновь исполненному run.

Независимая проверка `review_final_artifact.json` имеет `status=passed`: фактические hashes данных и исходников совпали с журналом, журнал включён в manifest, model SHA-256 `ebc9bafee00b294793f0ef2b01e9b8d1b42825bc461dc7fa4cdb603496fb3b52`. Reviewer проверил результат реального refit и журнал, но не выполнял ещё один отдельный полный fit. Исходный `original_release.zip` сохранён. Зависимости требуют точного совпадения установленных версий; Python привязан к major.minor, а не patch, чтобы контракт Windows/Linux был совместим с Python 3.12 Docker.

## Выполненные проверки

Команда:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_remediation_backend.py tests/test_api.py tests/test_pipeline.py tests/test_qa_regressions.py -q
```

Промежуточный targeted результат: **121 passed**, 1 предупреждение deprecation из установленной Starlette/httpx, 6.27 s. Матрица включает перестановку articles/warehouses, замену отсортированных идентификаторов, перестановку features, порчу весов, изменение threshold, неправильные mapping IDs/dtypes/dependency/source hashes, отсутствие файлов/manifest/version/provenance, повреждённый JSON и отсутствующий/изменённый training record. Проверка semantic metadata повторно рассчитывает manifest digest, поэтому отказы не сводятся к одному проверочному хэшу manifest.

Финальный независимый regression run `.venv\Scripts\python.exe -X utf8 -m pytest -q`: **177 passed**, 1 upstream deprecation warning, 36.63 s, exit 0; протокол `final_pytest.txt`.

Численные функции прогнозирования не изменены. На матрице 4×45 `float32` входов исходный и загруженный Booster дали **точно одинаковые значения** (`assert_array_equal`). Tiny training save/load regression также сохраняет точное численное равенство. Полноразмерный реальный HTTP probe на утверждённом bundle завершён: 562496 строк, 11×799×64, даты 2026-08-01–2026-10-03, максимальная абсолютная разница с сохранённым offline CSV **0.0**, повторные POST побитово одинаковы. Результат: `backend_fullsize/benchmark.json`; подробности concurrency — `cache_concurrency_report.md`.

Независимая проверка целостности финального артефакта: **PASS** в пределах явно описанных проверок `review_final_artifact.json`.

## Финальный Docker

Контейнерный прогон завершён с `network_mode=none`. Последний `docker_benchmark.json`: **passed**, 562496 строк, POST **34.208721317 s**, peak cgroup memory **3939459072 bytes**, image **148796116 bytes**, cached build **1.7365938 s**, максимальная абсолютная разница offline/Docker **3.552713678800501e-15**. `docker_command_status.json` подтверждает exit 0 последнего запуска с раздельными stdout/stderr. Время сборки относится к cached layers и не характеризует сборку с нуля.

Независимый `review_docker_artifacts.json`: **passed**. Reviewer проверил реальные bytes образа и forecast CSV, совпадение app/src/model/requirements с рабочими файлами, точную сетку и offline parity. Image ID: `sha256:cba13a7ca44769c2bc65ac85b4ab80ac39927e24edfc699a69533c59af804fa3`. Полный HTTP runtime и cgroup measurements измерял root probe; reviewer не выдаёт их за собственный повторный запрос.

Первый успешный результат сохранён в `docker_benchmark_first.json` (POST 39.597909063 s). Его внешняя PowerShell-обёртка зарегистрировала `NativeCommandError` из-за stderr BuildKit, хотя фактические build/run/parity stages прошли. Повторный запуск с раздельными stdout/stderr дал явный exit 0; финальные численные ресурсы и время приведены по этому последнему прогону.

