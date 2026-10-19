# Финальный цикл ансамблей Nonton

Production сохранён: **nonton-v1**. Исследовательский кандидат — **equal4:P1**, равная смесь daily, weekly, weekly-direct-shape и article с итоговым порогом .25. На четырёх переиспользованных development окнах он улучшает все пять средних метрик относительно catalog-corrected daily reference и оба локальных score на4/4окнах. Будущее превосходство не установлено; sparse categorical serialization текущей реализации велика.

Основной отчёт — [final_decision_ru.md](final_decision_ru.md), точный выбор — [model_selection.md](model_selection.md), независимые численные проверки — [independent_verification.md](independent_verification.md), гарантии текущего API/Docker — [release_tests.md](release_tests.md). Новые code/weights не подключены к production POST.

Полная матрица — [per_origin_metrics.csv](per_origin_metrics.csv), отдельные rounding/ensemble представления — [rounding_ablation.csv](rounding_ablation.csv) и [ensemble_experiments.csv](ensemble_experiments.csv). Сравнение с corrected reference, horizons, sparse, rank/minmax и volume distortion находятся рядом. [Протокол](experiment_protocol.md) сохраняет исходную фиксацию; последующий runtime encoding fix отдельно описан в `catalog_audit/encoding_runtime_fix.md`.

Экспериментальный standalone bundle: `models/final_experimental/`; его manifest связывает три Booster, feature/source/catalog contracts, веса, postprocessing, dependencies и adapter hash. Для нового входа не нужны исходные train CSV, audit first-seen metadata, OOF или внешняя сеть. Минимум180календарных дней sales; stock обрабатывается общей документированной очисткой. Все official output IDs остаются в grid, отсутствующие в текущем input получают zero fallback.

```powershell
.venv/Scripts/python.exe -X utf8 integration/experimental_predict.py --bundle integration/models/final_experimental --sales path/to/sales.csv --stock path/to/stock.csv --candidate equal4:P1 --output experimental_forecast.csv
```

`nonton_experimental_verified.zip` содержит код и финальные экспериментальные модели для извлечения в отдельный каталог; cache, private train CSV и historical OOF в него не включены. Установить зависимости из включённого `requirements.lock` следует до автономного inference. Model kind experimental, он не является заменой production release. Проверенная production-поставка — прежний `nonton_solution_remediated_verified.zip`, новый Docker tag для её повторной проверки — `nonton:integration-verified`.

Один требуемый пользовательский source определён: `filipp880/forecast-64-v1`, pinned commit в [source_inventory.md](source_inventory.md). Второй source не установлен. M5/Favorita считаются supplementary research, не выдаются за найденную пару. Нелицензированный внешний код не копировался; фиксированная смесь и half-even независимо реализованы и проверены против inspected source fixtures.

Полные команды обучения, оценки, проверки источников и контейнера — в итоговом отчёте. Экспериментальные scripts перезаписывают только свои выходы в `integration/`; production и прежние исследования сохранены.
