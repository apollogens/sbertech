# Независимая проверка remediation — роль E

Дата: 18 октября 2026 года. Проверяющий не изменял production-код, модели и исходные CSV. Выполнены только аудиты и разрешённые синтетические fits по два дерева в существующих тестах. Полное обучение не запускалось. Этот отчёт пока удостоверяет исходное состояние; новые изменения требуют отдельной проверки ниже.

## Воспроизведение исходного состояния

Исходный код, тесты и модель извлечены из `original_release.zip` в отдельную временную директорию; SHA-256 каждого `src/`, `app/`, `tests/`, `model/` совпал с `initial_manifest.json`. Конкретный путь и хэши сохранены в `review_frozen_baseline_hashes.json`. Это устраняет влияние параллельного редактирования рабочей директории. Cache, OOF и прежние QA-материалы скопированы отдельно. Исходный API-кэш в рабочей папке не изменялся.

| Проверка | Фактически полученный результат | Сырой протокол |
|---|---|---|
| Существующие pytest и независимые backend-тесты | 119 passed, 0 failed, 0 skipped; одно предупреждение зависимости | `review_pytest_frozen_baseline.txt` |
| Независимый temporal-аудит | 11 PASS, 0 FAIL | `review_temporal_frozen_baseline.txt` |
| Независимый пересчёт 31 OOF по исходному sales | exit 0; максимальное расхождение с сохранёнными метриками/score 5.684341886080802e-14 | `review_metrics_baseline.txt` |
| Настоящая LightGBM через API, синтетическая история 180 дней | 562496 строк, повторный POST детерминирован, будущий stock не влияет, overflow sales/stock → 422 | `review_backend_real_frozen_baseline.txt` |

Настоящий API-запуск на синтетической истории занял 3.9441143 секунды на первый POST. Это не воспроизведение прежнего Docker-бенчмарка на полном сыром входе. Числа 33.77 секунды, 3.754 GB и parity 3.55e-15 на этом этапе заново не проверены; прежние отчёты не превращены в новые измерения.

Панель независимо восстановлена из 1492370 строк исходного sales суммированием 970677 дневных ключей. Получено точное равенство cache-панели размера 943 × 8789; диапазон 2024-01-01–2026-07-31. Ошибка округления при приведении агрегированных quantity к float32 равна 0 на этих данных.

Для incumbent `lgb_tweedie_z0.25`, origin 2026-05-28, прогноз 2026-05-29–2026-07-31:

| Метрика | Независимый результат |
|---|---:|
| SMAPE | 158.6871617213434% |
| WAPE | 80.43006567684449% |
| RMSE | 0.8662841487164723 |
| Официальный средний абсолютный Bias по сериям | 80.56555726626279% |
| RMSLE | 0.3126153218811934 |

Первый temporal-запуск из рабочей директории попал в промежуточное состояние инженерного изменения: новый loader уже требовал manifest, отсутствовавший у прежнего model. Получен `ValueError: Missing or invalid artifact manifest`. Сырой `review_temporal_baseline.txt` сохранён. Это не ошибка frozen baseline и не финальный verdict нового loader. После этого baseline полностью проверялся в изолированной копии.

## Реальное происхождение OOF

Найдены 31 NPZ, а не 31 независимый fold. Каждый содержит только `prediction` и `origin`; в NPZ отсутствуют training-run ID, хэш весов, схема признаков, seed, train cutoff и описание подбора. Сопоставление с `run_pipeline.py`, TXT весами и `experiment_results.csv` воспроизводит:

| Origin | Прогнозный интервал | Outputs | Назначение |
|---|---|---:|---|
| 2026-01-20 | 2026-01-21–2026-03-25 | 12 | Выбор модели и порога |
| 2026-03-25 | 2026-03-26–2026-05-28 | 12 | Выбор модели и порога |
| 2026-05-28 | 2026-05-29–2026-07-31 | 7 | Заявленный заключительный holdout |

На первых двух origins: шесть baselines и по три варианта каждой из двух LightGBM-целей (raw, порог 0.25 и 0.5). Всего восемь пороговых outputs — преобразования четырёх fitted LightGBM-моделей, а не независимые fits. На последнем origin: шесть baselines и выбранный Tweedie с порогом 0.25. Это три непересекающихся временных окна с общей историей обучения и сериями; статистическая независимость наблюдений не доказана.

Код пишет `selection_frozen.json` до вычисления последнего holdout и выбирает incumbent только по первым двум origins. Независимо воспроизведены все 18 baseline outputs, три selected Tweedie OOF и пороговая обработка selection outputs. Веса шести прежних retraining-файлов сверены с прежними originals/manifest существующим аудитором; reviewer не повторял эти шесть больших fits.

В репозитории отсутствуют Git commits (`unborn HEAD`). Поэтому нет независимой неизменяемой истории, доказывающей, что исследователи никогда ранее не смотрели на holdout. JSON `holdout_was_used_for_selection=false` и текущий порядок кода совместимы с заявлением о freeze, но не удостоверяют всю историю работы. С текущего remediation последний интервал уже известен и используется для диагностики: новый выбор по нему следует честно называть адаптацией к известному validation, а не untouched test.

## Официальный scorer и конфликты источников

Прочитан `C:/Users/apollo/Desktop/выборка/markdown hakaton.md`. Python-блок scorer точно совпадает с `scripts/official_score.py` после нормализации внешнего whitespace; AST также совпадает. SHA-256 исходного Markdown: `2739c3b674bcce805aab6e51f94b0f0806b1816d1e03ea172cc5a2eceff73e07`.

1. Разделы 5.2/5.5 считают ошибку (0,0) нулевой; исполняемый `smape_series` полностью исключает такие дни из среднего. Контрпример truth=[0,0,0,1], prediction=[0,0,0,0]: текстовая версия 50%, scorer 200%. Это реальное неустранённое противоречие организаторского документа. Выполненные compatibility fixtures подтвердили обе интерпретации. Изменять scorer для видимого улучшения нельзя.
2. Раздел 5.3 называет minmax режимом по умолчанию, раздел 9 ожидает rank. При фиксированном составе 12 исходных кандидатов на первых двух folds rank даёт лучший средний score `lgb_l2_z0.25` = 0.20681818181818185, тогда как incumbent = 0.22727272727272727. Minmax выбирает incumbent с отрывом всего 0.0013840182451014815. Это существенная зависимость выбора от нормализации; локальный score не следует выдавать за официальный результат конкурса.
3. `normalize_rank` не усредняет ничьи: перестановка двух моделей с одинаковыми метриками меняет их присвоенные ранги. При единственном кандидате все нормализованные метрики равны 0. Полноценный конкурсный rank без остальных участников не воспроизводим.
4. Официальный `validate_submission` выдаёт warnings и не удостоверяет полный уникальный key-grid или отсутствие Inf. Production-контракт должен проверять это отдельно. Успех одного официального валидатора сам по себе недостаточен для приёмки файла.
5. Раздел 4 одновременно требует наблюдавшиеся пары и явно 11 × 799 × 64 строк. Полный декартов grid включает ненаблюдавшиеся пары. Выбранное явное следование размеру раскрыто в существующих docs; двусмысленность официального текста сохраняется.

Доступны исходные sales/stock CSV и Markdown. Архив `hakaton.zip` содержит только эти два CSV. Упомянутый прежними docs отдельный backend-ТЗ DOCX среди фактически обнаруженных материалов проекта и папки выборки не найден; выводы о его точном содержимом не делались. Схемы CSV и действия API проверяются по доступному Markdown и фактическим файлам.

## Первоначальное решение reviewer

Воспроизводимость численных baseline-метрик подтверждена. Подтверждено ограничение исходной связи каталога и весов: прежний loader принимал другой отсортированный article ID без изменения настоящих весов (контролируемая подмена только чтения JSON в существующем temporal-аудите). Его успешный старый тест как раз документирует дефект, а не отсутствие риска.

PASS финальному релизу и новым gates пока не присваивается. Новые engineering, ML comparison, Docker и полный real-input concurrency должны пройти последующую независимую проверку. Ни один научный источник или новый quality uplift настоящим baseline-аудитом не подтверждён.

## Последующая адресная проверка нового кода

Независимо выполнено `.venv/Scripts/python.exe -m pytest tests/test_remediation_backend.py -q`: **34 passed**, exit 0, 3.87 s, одно upstream deprecation warning. Сырой протокол: `review_engineering_targeted.txt`. Проверки используют реальные веса во временных каталогах и отдельные синтетические HTTP fixtures; основная модель в рабочем каталоге на этом этапе ещё ожидала финального manifest.

По чтению `src/artifacts.py` новый контракт хэширует точные байты catalog/config/model, хранит упорядоченные feature names/dtypes и identifier→ID mapping, source hashes preprocessing и dependency versions. С `training_recorded` в files включается `training_record.json`, а при загрузке сверяются его run ID, training-data hashes и model hash. Старым весам автоматически не приписывается доказанное происхождение: default остаётся `reconstructed_unverified`. SHA-256 — контроль согласованности относительно доверенного manifest; он не цифровая подпись и не доказательство первоначального обучения.

Cache review подтверждает точечный характер ремонта: прежняя реализация уже публиковала результат после вычисления под lock и исключала второй POST. Новый код закрывает выдачу внутреннего изменяемого DataFrame, сохраняет metadata одной committed версии, связывает output с исходными upload bytes и model ID и запрещает обычный запуск с несколькими workers. Тесты реально выполняют перекрывающиеся HTTP POST/GET с Event-controlled синтетическим inference, включая injected failure, mutation isolation и restart. Это не full-size concurrency benchmark. Настоящий full-input прогон остаётся отдельным gate.

Двухкомпонентная модель рассмотрена независимо: classifier обучается на `quantity>0`, gamma regression — только на положительных training labels, class weights не заданы, output равен `p*m`. Признаки и labels наследуют cutoff-safe construction. Скрипт `review_two_part_checks.py` выполнил 4 синтетических fits по 2 дерева; при изменении всех будущих y/stock веса обоих компонентов и predictions совпали побитово, output строго равен p*m, probabilities лежат в [0,1], gamma means положительны, all-zero/all-positive training targets явно отклоняются. Результат: `review_two_part_checks.json`, exit 0. Эта проверка удостоверяет проверенные инварианты, не forecasting uplift и не калибровку на настоящих данных.

Пятиточечный protocol корректно называет terminal window ранее открытым diagnostic. Conservative policy «сохранить incumbent при отсутствии убедительного выигрыша» допустима как управленческое решение, но не доказывает оптимальность incumbent и не даёт статистической значимости. Термин «устойчивость по окнам» должен сопровождаться опубликованными per-window comparisons: численный критерий robustness заранее не задан. Выявлено, что первоначальный набор новых challengers пропустил известный rank-sensitive L2; root принял замечание и добавляет L2 как явно маркированный post-start exploratory benchmark. Подмена этого amendment якобы первоначально frozen protocol недопустима.

Промежуточный независимый запуск `review_challenger_metrics.py --partial` проверил 62 уже существовавшие строки experiment matrices. SHA-256 всех соответствующих NPZ совпал, ключи origin и размер 64 × 8789 подтверждены, predictions конечные неотрицательные. Отдельная реализация без `src.metrics` пересчитала пять метрик, пять метрик дней 36–64 и локальный minmax: max расхождение 5.684341886080802e-14. Сырые результаты: `review_challenger_metrics_partial_stdout.txt`, `review_challenger_metrics_partial.csv`. Статус строго `partial_scope_passed`: полная матрица 17 × 5 и выбор по rank ещё не проверены.

Измерение `process_peak_rss_bytes` в learned matrix — максимум RSS процесса с начала всего последовательного запуска, а не отдельно сброшенный peak каждого fit. Для выводов о per-model памяти эти строки недостаточны. `train_seconds=0` у reused weights означает, что этот fit заново в данном запуске не выполнялся; это не нулевая стоимость обучения архитектуры.

## Полная независимая проверка 85 новых outputs

После завершения трёх matrices выполнен `review_challenger_metrics.py`: **85/85 outputs проверены**, 17 фиксированных кандидатов × 5 origins. Все SHA-256 соответствуют сохранённым NPZ. Независимая реализация пяти метрик, метрик дней 36–64 и minmax дала max расхождение **5.684341886080802e-14**. Сырой stdout: `review_challenger_metrics_stdout.txt`; summary и per-output результаты: `review_challenger_verification.json`, `review_challenger_metrics.csv`, `review_challenger_development_summary.csv`. Terminal diagnostic исключён из среднего, по которому сравниваются модели.

Order для rank: исходные 15 candidates из неизменённого `experiment_protocol.json`, затем `lgb_l2`, `lgb_l2_z0.25` из честно опубликованного post-start amendment. Ничьи обрабатываются оригинальной семантикой `np.argsort`, не усредняются.

| Среднее четырёх development windows | Incumbent Tweedie z0.25 | Two-part gamma z0.25 | Разность challenger − incumbent |
|---|---:|---:|---:|
| Локальный официальный rank, fixed17 | 0.277343750 | 0.217968750 | −0.059375000 |
| Локальный minmax | 0.836491305 | 0.834972067 | −0.001519237 |
| SMAPE, % | 165.189967128 | 165.033862917 | −0.156104211 |
| WAPE, % | 86.438310136 | 86.237618224 | −0.200691913 |
| RMSE | 0.775722309 | 0.772024638 | −0.003697670 |
| Bias, % | 83.043671736 | 82.878383391 | −0.165288346 |
| RMSLE | 0.307773172 | 0.306596680 | −0.001176493 |

**Небольшое среднее улучшение challenger действительно измерено.** Называть его отсутствующим неверно. SMAPE лучше на всех четырёх development origins, minmax — на трёх из четырёх. При этом individual Bias хуже на трёх origins и лучше на одном, который определяет снижение среднего; это не устойчивое улучшение Bias каждой fold. Четыре окна не удостоверяют статистическую значимость и не доказывают отсутствие значимости: соответствующее исследование не выполнено.

Ранее открытый terminal diagnostic у challenger: SMAPE 158.674255 против 158.687162, Bias 79.773277 против 80.565557; WAPE 80.432968 против 80.430066, RMSE 0.873155 против 0.866284; minmax 0.838441 против 0.838184. Это опубликованный diagnostic tradeoff. Он **не используется как скрытый veto** в заранее обозначенной development selection.

Reviewer допускает сохранение incumbent как консервативный выбор простоты при малом и неоднородном development gain и увеличении стоимости двух моделей. Такой выбор не означает, что incumbent численно лучший по всем метрикам или official local rank. Нулевые released before/after metrics должны относиться только к сохраняемой архитектуре и совпадающему prediction pipeline; ненулевые улучшения исследовательского challenger сохраняются отдельно. Фактический финальный refit, его provenance, полный API/Docker и итоговый regression suite ещё подлежат проверке перед release signoff.

## Прямые официальные функции на полной сетке и финальный refit

Прямой монолитный `compute_all_metrics` на 562496 строках был остановлен после 565.0274894 секунды wall / 562.6875 секунды CPU, чтобы освободить ресурсы для изолированного полноразмерного API-бенчмарка. Он **не завершён и не PASS**. Причина низкой эффективности — повторные строковые masks по всем строкам для каждой серии. Запись остановки: `review_monolithic_scorer_terminated.json`; незавершённый stdout сохранён отдельно.

Вместо этого выполнена точная композиция **неизменённых оригинальных** `smape_series` и `bias_abs_series` для каждой из 8789 серий, затем предусмотренное scorer среднее; глобальные `wape`, `rmse`, `rmsle` вызваны непосредственно на flattened массивах. Известная полная сетка и её порядок независимо проверены. Это вычисление использует все 562496 значений и не изменяет ни одной метрики. Все пять официальных результатов совпали с baseline выше; eligible=7752, excluded=1037, mean signed Bias=−62.834934485864856%, global signed volume Bias=−19.105414359749904%, median/p90/p95 absolute Bias=100%. Текстовая diagnostic SMAPE=47.08955612112918%, исполняемая official=158.6871617213434%. Артефакты: `review_scoring_full_grid.json`, `review_oof_scoring_composed_stdout.txt`; exit 0.

Финальный выпущенный комплект независимо загружен скриптом `review_final_artifact.py` без повторного обучения и без inference. Проверены настоящие файлы, не только присланный root summary:

- Bundle ID: `9267e65f0ca9e62b636d185fe7731a71b4e24a8b5110fa830701d5beb0d0f50a`.
- Training run ID: `final-20261018T181325Z-cdd29774bb1b`, provenance `training_recorded`.
- SHA-256 весов: `ebc9bafee00b294793f0ef2b01e9b8d1b42825bc461dc7fa4cdb603496fb3b52`.
- Training record SHA-256: `bba2703175623921225193af374deeda158890e27e9766edefa9cf026031b107`.
- Config, catalogs и weights побитово совпали с исходными bytes из `original_release.zip`.
- В manifest включён hash training record; run ID, hashes panel/catalog/selection и actual training source hashes совпали с реальными текущими файлами.
- Проверены 220 деревьев, 1476552 training rows и cutoff 2026-07-31; записанное время fit 22.886229700001422 секунды.

Проверка завершилась exit 0: `review_final_artifact.json`, `review_final_artifact_stdout.txt`. Reviewer не запускал отдельный второй большой fit. Новая запись происхождения относится к новому реально выполненному refit; она не приписывает доказанную историю прежнему обучению. Повторные full-size API и Docker, итоговый regression suite и итоговый signoff остаются отдельным следующим шагом.

## Итоговая регрессия и реальные полноразмерные HTTP outputs

Reviewer самостоятельно выполнил на окончательных source/model файлах:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests reports/qa/check_backend_independent.py -q --junitxml=reports/remediation/final_tests.xml
```

**177 passed, 0 failed, 0 skipped, exit 0, 36.63 секунды.** Единственное предупреждение — upstream Starlette/httpx deprecation, не failed test. Сырые результаты: `final_pytest.txt`, машинный JUnit: `final_tests.xml`. Это окончательный regression run; прежние числа 119 и 34 относятся к ранее явно обозначенному scope. В suite входят реальные subprocess CLI entrypoints, tiny training/pipeline, actual uvicorn startup и negative cases.

Скрипт `review_fullsize_artifacts.py` отдельно прочитал настоящие сохранённые HTTP CSV и сравнил их с offline CSV и выпускным submission. Он не заменяет executed HTTP probe новым mock:

- Все first/second/during/cached CSV побитово одинаковы, SHA-256 `dd8c2b34b1a7900a7392dc427b8eae7116f0f49828693942c925d47342f61dc1`.
- Подтверждена полная уникальная сетка 562496 строк, 11 складов × 799 артикулов × 64 дня, даты 2026-08-01–2026-10-03, finite nonnegative quantities.
- API/offline максимальная абсолютная разница **0.0**, API/released submission **4.9918806865889565e-09**, допустимый предел 1e-7.
- SHA-256 реальных больших входов совпали с probe record, model ID совпал с утверждённым manifest.
- Артефакты 409 concurrent POST и 400 invalid upload проверены; версии 1→2, предыдущий GET во время вычисления и сохранение версии после failed POST подтверждены выполненным probe и его outputs.

В исправленном отдельном probe записаны POST 35.6834571 s, replacement POST 36.1028472 s и sampled process-tree RSS 3278405632 bytes. Reviewer проверил настоящий JSON, input/model hashes, CSV outputs и код измерения; он не делал второй независимый runtime measurement. RSS является суммой launcher и descendants каждые 50 ms, shared pages могут учитываться повторно. Прежние ≈4 MB относились только к Windows launcher и **недействительны как память сервера**; исходный ошибочный benchmark сохранён с явным ограничением.

Результат независимой проверки outputs — exit 0: `review_fullsize_artifacts.json`, `review_fullsize_artifacts_stdout.txt`. Выпускной submission SHA-256 `57cf81142dc312c87230a02d48d9d9714263d50f454dfb8470cd275a872abf0d`.

Дополнительно `review_final_numerical_code.json` подтверждает побитовое сохранение `features.py`, `data.py`, `baselines.py`, `train.py` относительно frozen release и AST-идентичность `predict_panel`/`predict_64`. Вместе с идентичными весами/config/catalogs, воспроизведёнными OOF и настоящим API/offline parity это поддерживает вывод об отсутствии изменения численного forecasting pipeline. Старый temporal-аудит включает expectation о принятии чужого catalog ID и поэтому не выдаётся за повторный final test исправленного manifest; этот исправленный случай проверен актуальными regression tests.

Docker после финальных изменений на момент этой записи ещё ожидается. Окончательный Gate F и release signoff до его проверки не присваиваются.

## Окончательная независимая подпись после Docker

**Вердикт: PASS для проверенного инженерного релиза с сохранённым forecasting pipeline.** Это не утверждение о высокой точности, улучшении качества выпускаемой модели или превосходстве на будущем leaderboard. Выпускной quality delta равен нулю; небольшой measured development gain исследовательского two-part challenger честно сохранён и не приписан выпущенной модели.

Reviewer самостоятельно проверил настоящий Docker CSV и прочитал содержимое реального локального image `nonton-forecast:remediation` посредством отдельного лёгкого Python/hashlib запуска с `--network none`, без inference. После повторного запуска проверка повторена: окончательный Image ID `sha256:5bb1ea1fea5a136cfc54c2a80701baefd1f97d23a50e17d9b1a42b476913faef`. Все `src/*.py`, `app/*.py`, `model/*` и `requirements.lock` внутри image побитово совпали с актуальными локальными файлами. В image действительно присутствуют согласованные manifest и training record, а не старый необязательный loader.

Docker CSV имеет полную уникальную сетку **562496** строк и finite nonnegative quantities; ключи совпали с offline, max абсолютное расхождение **3.552713678800501e-15** при допустимых 1e-7. CSV SHA-256: `10cd625f921ef958a5626ff733005343a5996919963d5e81a183ea18b908bd8e`. Независимые доказательства: `review_docker_artifacts.json`, `review_docker_artifacts_stdout.txt`, exit 0.

Полный HTTP POST и cgroup measurement выполнены отдельным root probe внутри `--network none`, `--memory=6g`, `--cpus=4`. Окончательный запуск: POST **34.208721317 s**, cgroup peak **3939459072 bytes**, размер image **148796116 bytes**. Build **1.7365938 s** использовал cached layers и не является cold-build benchmark. Reviewer независимо подтвердил actual image/forecast bytes и соответствие локальному комплекту; он не выдаёт root runtime measurement за второй лично повторённый полный HTTP benchmark.

Первый полноценный запуск дал POST 39.597909063 s, cgroup peak 3873841152 bytes и cached build 3.41806 s; его benchmark сохранён в `docker_benchmark_first.json`. Вложенные build/HTTP/parity прошли, но внешняя PowerShell-команда с общим перенаправлением stderr вернула NativeCommandError на обычном BuildKit progress. Этот outer exit не объявлен успешным. Повтор с раздельными потоками завершился **exit code 0**, проверенным в `docker_command_status.json`; приняты последние числа выше. Image manifest ID изменился с `sha256:cba13a7ca44769c2bc65ac85b4ab80ac39927e24edfc699a69533c59af804fa3` на указанный окончательный ID, но проверенные source/model/dependency bytes и Docker CSV остались теми же. `review_docker_artifacts.json` и его stdout обновлены повторным реальным исполнением reviewer-скрипта, а не ручной заменой чисел.

| Gate | Независимый статус | Основание и точная граница |
|---|---|---|
| A: baseline | PASS | Frozen source/model hashes, 119 исходных тестов, 11 temporal groups, raw sales reconstruction, 31 OOF и точная композиция официальных метрик |
| B: diagnosis | PASS | Подтверждены 5078 eligible нулевых суммарных прогнозов, механизм threshold и segment/horizon diagnostics; скрытый истинный спрос и причинный stockout не объявляются установленными |
| C: scientific grounding | PASS в опубликованном scope | Первичные methodological/implementation references и ограничения проверены исследовательской ролью и отражены в evidence register; papers не используются как доказательство Nonton uplift |
| D: model comparison | PASS | 85/85 сохранённых outputs, 17 кандидатов, 5 реальных окон, независимый пересчёт всех метрик и честный post-start L2 amendment; неизвестный будущий test отсутствует |
| E: engineering | PASS | Новый traceable bundle, negative integrity regressions, committed snapshot/input identity, реальные full-size outputs и 177 окончательных тестов с CLI entrypoints |
| F: end-to-end | PASS | Действительно проверенный image, offline/API/submission/Docker parity, complete-grid CSV, network-none full HTTP и ресурсный лимит |
| G: independent review | PASS | Независимый reviewer воспроизвёл baseline, challengers, actual artifact hashes, full-size outputs, image bytes и окончательный suite; неподтверждённые исторические/статистические утверждения отвергнуты |

В проверенном объёме открытых подтверждённых release-blocking P0/P1 не найдено. Остаточные ограничения не скрыты:

- Ранее открытый terminal не untouched test; историческое отсутствие прежнего tuning по нему не доказано неизменяемым журналом. Статистическая значимость небольшого challenger gain не установлена.
- Противоречия official prose/executable SMAPE и minmax/rank остаются внешними неразрешёнными вопросами; точная executable compatibility сохранена, обе SMAPE показаны отдельно.
- Кэш поддерживается одним процессом/экземпляром. Несколько контейнеров за балансировщиком и нестандартные скрытые worker launchers не поддерживаются.
- Learned experiment peak RSS — накопительный максимум процесса; отдельный per-fit peak не измерен. Старый launcher-only RSS недействителен; Windows RSS и Docker cgroup memory — разные показатели.
- CLI-проверки удостоверяют опубликованные success/negative cases и настоящие entrypoints, а не все возможные комбинации каждого некорректного входа. Неизменённый поставленный scorer сохранён буквально, включая его предупреждения и особенности ошибок.
- Нет данных для финансовой экономии или гарантии leaderboard. Высокий baseline WAPE/Bias сохраняется, что ограничивает пригодность для решений об управлении запасами.

Подпись reviewer E относится к указанным model/image/source hashes и исполненному scope. Архив поставки, если он сформирован позже, должен содержать именно этот комплект и не является автоматически проверенным лишь по имени файла. Разделы выше фиксируют этапы проверки; окончательный статус определяется этой подписью и приведёнными актуальными доказательствами.
