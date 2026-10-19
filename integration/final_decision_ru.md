# Финальное решение по ансамблю и поставке Nonton

**Выпущенная архитектура остаётся nonton-v1.** Реализованы и исполнены ансамбли, округление и catalog-corrected модели; они поставляются как проверенный экспериментальный код и изолированный bundle. Production `src/`, `app/`, `model/`, исходные submission и прежние ZIP не заменялись. Гарантированное превосходство или конкурсное место не заявляется.

## Внешние источники и перенос

Однозначно найден один пользовательский внешний GitHub-проект: [filipp880/forecast-64-v1](https://github.com/filipp880/forecast-64-v1), commit `f8a8c6e60edaf12af2fd351e290c35e6875afea0`, локально `C:/Users/apollo/AppData/Local/Temp/forecast-comparison-7371efa0b4b14184a05e39ed9dc127b8`. Пользователь подтвердил этот URL и приблизительный Temp-путь в ходе работы. Второй источник из первоначального задания по целевому поиску не установлен и в уточнении не назван. **Интеграция двух проектов не заявляется.** M5/Favorita — дополнительные исследовательские клоны, не подстановка второй пользовательской загрузки.

Реальный source pipeline смешивает .3 hurdle+.7 LightGBM после обратного преобразования цели, затем clip/threshold/np.rint; hurdle использует жёсткий gate p>=.5, вопреки комментарию о произведении p×magnitude. В Git tracked tree нет лицензии. Защищённый код не копировался: независимо реализованы общая выпуклая смесь и half-even postprocessing. `source_DA70` — только адаптация fixed-mixture формы к Nonton daily/article, не воспроизведение чужой hurdle модели. Входы уже в шкале observed quantity, повторный expm1 не применяется.

Source AST fixtures и собственный engine реально исполнены; четыре политики совпали на10010конечных неотрицательных значениях. Дополнительные M5 key-merge/mean и Favorita CSV-format/clipping fixtures проверены, но чужой clip1000 и формат .4f автоматически не переносились. Полные paths/лицензии/обязательства: `source_inventory.md`, `source_analysis.md`, `source_license_audit.md`, `ensemble_reconstruction.md`, `source_audit/transfer_review.md`.

Общая научная основа forecast combination проверена по Wang, Hyndman, Li, Kang, [Forecast combinations: an over 50-year review](https://doi.org/10.1016/j.ijforecast.2022.11.005). Она не доказывает полезность нашей смеси. Ни published результат, ни внешний репозиторий не заменяют Nonton validation.

## Исправление исторического каталога

Output catalog и feature catalog разделены. На каждом **INNER** origin берутся лишь ID, уже встреченные в sales к этой дате, включая строки quantity=0. История обрезается до origin до snapshot/агрегации; future ID не добавляет нулевых колонок в warehouse averages. Идентичность категорий — независимые от будущего bounded SHA256 codes int32 с проверкой коллизий. Unknown output IDs получают deterministic0; финальный grid11×799×64 сохраняется. Категории товаров не используются, future popularity/realized quantity не инициализируют cold start.

Raw first-seen повторно проверен; stock-onlyIDs на ранних внутренних origins существуют и сознательно не включены в консервативную sales-only политику. Это потеря доступной информации, не future leak. Никакого ранее официально датированного fixed ID catalog не найдено. Ключи исторического evaluation сохраняются прежними, а будущие ID используются только для проекции output и оценки, не predictive features. Оговорка о реально неизвестном организаторском forecast catalog остаётся.

Исправленные D/W/S/A обучены заново на одинаковой новой политике. Старые NPZ не перезаписаны. Разницу correctedD и прежнего incumbent нельзя выдавать за чистое качество архитектуры: меняются catalogue handling и categorical encoding. Воспроизводимый отчёт и before/after coverage — `catalog_leakage_resolution.md`, `catalog_audit/` и `review/legacy_comparison.csv`.

## Архитектура и веса

Три обучаемых Booster дают четыре представления: D — daily direct; W — weekly totals+историческая weekday allocation; S — те же weekly totals+форма D; A — article totals+исторические warehouse shares. S переиспользует D и W без повторного inference. Цель observed sales, future stock и future allocation shares не используются. Weekly horizon64=9×7+1. Все прогнозы выравниваются по date/warehouse/article, полный ключевой hash хранится с NPZ.

Смесь yhat=Σw_k×yhat_k, w>=0, Σw=1. Фиксированные варианты — equal4, D/A75:25,50:50,25:75, D/S50:50 и source-derived D/A70:30. Constrained learned-weight challenger выбирает лишь один из трёх D/A весов по первым двум origins; зафиксирован DA50:P1. Высокоразмерного stacking и подбора индивидуальных параметров товаров нет. Изменение состава компонентов/порогов после результатов не выполнялось.

Выполнены15исторических fits,215явных candidate×origin прогнозов и20raw component прогнозов. Дополнительные3Booster образуют финальный экспериментальный standalone bundle. Одна первоначальная failedattempt до любых метрик сохранена как `experiments_failed_encoding.txt`; runtime correction ограничила диапазон кодов. Новых untouched labels не появилось.

## Что показали качество и округление

Средние development показатели и локальные scores десяти P1 механизмов:

| candidate | smape | wape | rmse | bias | rmsle | rank_score | rank_delta | minmax_score | minmax_delta |
|---|---|---|---|---|---|---|---|---|---|
| D:P1 | 165.307351 | 85.934280 | 0.775270 | 82.790578 | 0.307108 | 0.474265 | 0.000000 | 0.835703 | 0.000000 |
| W:P1 | 164.479906 | 88.737427 | 0.788993 | 77.481101 | 0.312606 | 0.334559 | -0.139706 | 0.837850 | 0.002147 |
| S:P1 | 164.845778 | 87.156173 | 0.779062 | 82.104055 | 0.308079 | 0.310294 | -0.163971 | 0.836700 | 0.000997 |
| A:P1 | 165.778829 | 84.615851 | 0.776560 | 83.008267 | 0.304896 | 0.483824 | 0.009559 | 0.834815 | -0.000888 |
| equal4:P1 | 165.025618 | 85.727716 | 0.771056 | 81.286398 | 0.305681 | 0.272059 | -0.202206 | 0.832863 | -0.002840 |
| DA75:P1 | 165.384929 | 85.258220 | 0.771735 | 82.465140 | 0.305594 | 0.381618 | -0.092647 | 0.833869 | -0.001834 |
| DA50:P1 | 165.496788 | 84.829998 | 0.770750 | 82.417313 | 0.304683 | 0.377941 | -0.096324 | 0.833167 | -0.002536 |
| DA25:P1 | 165.623983 | 84.618271 | 0.772363 | 82.521822 | 0.304434 | 0.400735 | -0.073529 | 0.833431 | -0.002272 |
| DS50:P1 | 165.045934 | 86.242836 | 0.774018 | 82.111348 | 0.306766 | 0.330882 | -0.143382 | 0.834839 | -0.000864 |
| source_DA70:P1 | 165.401403 | 85.153586 | 0.771332 | 82.433354 | 0.305361 | 0.353676 | -0.120588 | 0.833629 | -0.002074 |

Изменения всех пяти метрик относительно corrected D:P1:

| candidate | smape | wape | rmse | bias | rmsle |
|---|---|---|---|---|---|
| D:P1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| W:P1 | -0.827445 | 2.803147 | 0.013723 | -5.309476 | 0.005498 |
| S:P1 | -0.461573 | 1.221893 | 0.003792 | -0.686522 | 0.000972 |
| A:P1 | 0.471478 | -1.318429 | 0.001290 | 0.217689 | -0.002211 |
| equal4:P1 | -0.281733 | -0.206564 | -0.004214 | -1.504179 | -0.001427 |
| DA75:P1 | 0.077578 | -0.676060 | -0.003535 | -0.325438 | -0.001514 |
| DA50:P1 | 0.189438 | -1.104282 | -0.004520 | -0.373265 | -0.002425 |
| DA25:P1 | 0.316632 | -1.316009 | -0.002907 | -0.268756 | -0.002674 |
| DS50:P1 | -0.261417 | 0.308556 | -0.001252 | -0.679230 | -0.000342 |
| source_DA70:P1 | 0.094052 | -0.780694 | -0.003938 | -0.357224 | -0.001747 |

Округление D, отдельно от эффекта ансамбля (средние четырёх origins):

| candidate | smape | wape | rmse | bias | rmsle | zero_total_eligible | positive_changed_to_zero | signed_series_bias | total_volume | volume_change |
|---|---|---|---|---|---|---|---|---|---|---|
| D:P0 | 182.468082 | 98.274644 | 0.769524 | 57.863331 | 0.301510 | 18.000000 | 0.000000 | 13.692652 | 177067.801898 | 0.000000 |
| D:P1 | 165.307351 | 85.934280 | 0.775270 | 82.790578 | 0.307108 | 5385.250000 | 421146.000000 | -66.725372 | 147292.439187 | -29775.362711 |
| D:P2 | 166.842853 | 81.331923 | 0.792910 | 91.111170 | 0.323522 | 6483.500000 | 483031.250000 | -78.109678 | 135878.250000 | -41189.551898 |
| D:P3 | 166.842853 | 81.331923 | 0.792910 | 91.111170 | 0.323522 | 6483.500000 | 483031.250000 | -78.109678 | 135878.250000 | -41189.551898 |

P0 — continuous; P1 — значения<.25 в0; P2 — np.rint, половины к чётному; P3 — P1 затем P2. P2=P3 при конечных nonnegative inputs, поэтому это aliases, не два успеха. CSV precision отдельно от integer rounding. В исходном output contract нет обязательного целочисленного прогноза: scorer приводит значения к float и проверяет отсутствие NaN/negative. Integer исторические labels сами по себе не оптимизируют смешанную loss. Fixture с дробной целью показывает, что округление может ухудшать точный прогноз.

Изменённые положительные значения, zero-total eligible, signed Bias, общая сумма, дневное/серийное искажение и overhead записаны для каждой стратегии. P4 сравнивает postprocess-before/after averaging; это различные операции. Threshold и rounding в общем случае разрушают weekly/article coherence; rawW/rawS сохраняют свои bucket totals, rawA — article totals. P6 aggregate-preserving integer allocation не вводился: integer output не требуется и его полезность не установлена.

Основной rank universe18зафиксирован до расчётов; точные aliases удаляются один раз по четырём development arrays, не меняя pool по отдельным origins. Evaluator weights50/20/15/10/5, executable/written SMAPE, minmax(last), exact/average ties, direct/reverse ordering, expanded/base/leave-one-out pools раскрыты в `scoring_sensitivity.md` и CSV. Это не точный leaderboard. Четыре development windows использовались неоднократно, последний terminal только diagnostic. Статистическая значимость и будущее превосходство не установлены.

Предварительный quality screen прошли 5 вариантов. Лучший исследовательский вариант — **equal4:P1**: все пять средних development-метрик лучше corrected D:P1, а rank и minmax лучше на4/4origins. Это реальный положительный результат, не объявленный неудачей. Средний minmax улучшается примерно на0.34% относительно corrected D. Его будущая устойчивость не установлена, а стоимость конкретной сериализации и inference заметно выше. Поэтому он сохранён как experimental candidate; решение оставить production — открытое инженерное суждение, не вывод об отсутствии улучшений.

Подробный выбор и every-origin losses — `model_selection.md`, `quality_gates.csv`, `paired_corrected_reference.csv`, `sparse_metrics.csv`, `horizon_metrics.csv`. Одна ухудшившаяся метрика сама по себе не является причиной отказа. Итог определяется неопределённостью переноса, реальной стоимостью и готовностью выпуска, а не требованием Pareto-доминирования.

## Стоимость и границы интеграции

Полный shared-component inference включает все3Booster, allocation и создание keyed frames; key alignment измерен отдельно. Записанные train_seconds повторены в строках вариантов, их нельзя суммировать215раз. Общий sampled RSS относится ко всему процессу origin, а не изолированному модели. Размеры сохранённых текстовых весов по пакетам:

| bundle | txt_bytes |
|---|---|
| 2025-09-14 | 785849597 |
| 2025-11-17 | 788223710 |
| 2026-01-20 | 807380123 |
| 2026-03-25 | 823346603 |
| 2026-05-28 | 809052761 |
| final_experimental | 808013424 |

Времена исторических прогонов:

| origin | train_seconds | component_inference_seconds | key_alignment_seconds | process_peak_rss_bytes |
|---|---|---|---|---|
| 2025-09-14 | 61.003780 | 12.988694 | 0.908918 | 2808532992 |
| 2025-11-17 | 64.741237 | 14.817827 | 0.801036 | 3193401344 |
| 2026-01-20 | 70.848268 | 14.707805 | 0.831503 | 3372417024 |
| 2026-03-25 | 77.812149 | 15.087780 | 0.904759 | 3478614016 |
| 2026-05-28 | 81.947522 | 14.925563 | 0.797232 | 3486687232 |

Большой размер TXT связан с реализацией categorical bitsets при разреженных bounded кодах; это наблюдаемая инженерная стоимость текущей реализации, не теоретическое свойство ансамблей. Оптимизация плотного model-local category mapping возможна отдельно, но в этом цикле ещё один подбор/retrain не выполнялся. Полный experimental180 CSV inference проверяется отдельно, включая model load, все3Boosters и alignment; wrapper не оптимизирован под subset components, поэтому latencyD тоже включает лишние модели. Cached OOF timings не выдаются за serving latency.

Экспериментальный manifest связывает модели, feature schemas, каталоги, runtime sources, dependency versions, weights, postprocessing, источник алгоритмической идеи и hashes. На180дневном входе membership строится только по предоставленным sales CSV; audit/raw train CSV на inference не читаются. Загрузка нового input без обучения проверена, tampered config и TXT отвергаются. Полный equal4 inference на том же180дневном входе занял22.112с против7.651с incumbent, около2.89× медленнее; повтор22.713с, sampledRSS2.240GB. Это отдельные последовательные измерения, не статистический latencybenchmark. Два полных повторных прогноза совпали точно. Подробности и hashes — `experimental_standalone_verification.md` и `release/experimental180/verification.json`. Это isolated standalone candidate, **не новый API/Docker release**.

## Проверенный финальный выпуск

Официальным остаётся исходный `submission.csv` и архив `nonton_solution_remediated_verified.zip`. Новый независимо записанный verification CSV: `integration/release/submission.csv`, SHA-256 `dd8c2b34b1a7900a7392dc427b8eae7116f0f49828693942c925d47342f61dc1`. Отличие от исходного≤4.992e−9 из-за float formatting; исходный CSV не заменён. Оба покрывают562496строк,64дня2026-08-01—2026-10-03,11складов799товаров, без NaN/Inf/negative/duplicate/missing keys, deterministic ordering.

Заново прошли177прежних pytest-проверок и16новых. Host offline/API difference0.0; repeated POST byte-identical, filteredGET/CSV/JSON и error/cache contracts проверены. Docker без сети4CPU/6GiB: POST34.376с, cgrouppeak3810914304байт, offline/container difference≤3.56e−15; restart200health/cache409. CPU, image identity/size и cached build limits документированы в `release_tests.md`, raw benchmarks в `release/`. Cold build не измерялся; speedup не заявляется.

Все409файлов прежнего выпуска,151старый forecast NPZ и cache/panel сохранены; rollback snapshot создан до изменений. Независимый reviewer перепроверяет official metrics и replay экспериментальных весов, source fixtures и temporalcatalog. Его заключение — `independent_verification.md`; финальные hashes и разделение production/experimental — `release_manifest.json`.

## Воспроизведение и защита

Команды из D:/SberTech, последовательно:

```powershell
.venv/Scripts/python.exe -X utf8 integration/source_audit/verify_source_fixtures.py
.venv/Scripts/python.exe -X utf8 -m pytest integration/test_catalog_policy.py integration/test_ensemble_engine.py -q
.venv/Scripts/python.exe -X utf8 integration/run_experiments.py
.venv/Scripts/python.exe -X utf8 integration/analyze_results.py
.venv/Scripts/python.exe -X utf8 integration/independent_verify.py
.venv/Scripts/python.exe -X utf8 integration/train_experimental_final.py
.venv/Scripts/python.exe -X utf8 integration/package_experimental.py
.venv/Scripts/python.exe -X utf8 integration/release/experimental180/verify_standalone.py
.venv/Scripts/python.exe -X utf8 integration/release_probe.py
powershell -NoProfile -ExecutionPolicy Bypass -File integration/docker_verify.ps1
.venv/Scripts/python.exe -X utf8 integration/finalize_reports.py
```

Повторное обучение перезаписывает толькоintegrationмодели/результаты; production не затрагивается. Source fixture требует указанного локального source checkout. Полноценный отрыв от этой машины проверен для productionконтейнера; experimental bundle для inference использует только собственные файлы и входныеCSV, source checkout ему не нужен.

Судьям следует представить работающий проверенный релиз, доказанное исправление temporal feature catalog в экспериментах, честные per-origin tradeoffs и реальный источник postprocessing. Нельзя утверждать «интегрировали два GitHubрешения», «доказали superiority на новомtest», «rounding обязателен», «новый ensemble прошёл API/Docker» или «гарантировали первое место». Техническая воспроизводимость эксперимента и будущая прогнозная точность — разные утверждения.
