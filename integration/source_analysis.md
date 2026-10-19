# Проверка реального алгоритма внешнего Nonton

Дата: 19 октября 2026. Источник [filipp880/forecast-64-v1](https://github.com/filipp880/forecast-64-v1/tree/f8a8c6e60edaf12af2fd351e290c35e6875afea0), commit `f8a8c6e60edaf12af2fd351e290c35e6875afea0`. Хеши 11 прочитанных файлов — `source_audit/source_fixture_results.json`.

## Исполняемый путь

`sales + stock CSV → app/features.py:build_panel → make_features(cutoff, h=1..64, lookback=180) → app/models/blend_model.py:predict → inverse_target → app/models/base.py:postprocess_forecast → app/predictor.py:predict → main.py CSV response`.

`build_panel` агрегирует продажи по date/warehouse/article, берёт максимальный stock в день, заполняет пропущенные продажи нулём и переносит stock вперёд. Сетка строится по наблюдавшимся парам, не по полному декартову каталогу. Атрибуты категорий выбираются `groupby(KEY).first()` до исторической фильтрации — при прямой ретроспективной адаптации нужен отдельный as-of audit. Признаки: warehouse/article/category/characteristic, средние за 7/14/28/56/90 дней, доля нулей, давность продажи, stock и календарь/горизонт. Будущие realized targets не нужны при inference.

В `BlendForecastModel.fit` обе ветви обучаются на одинаковых срезах. Hurdle классифицирует факт положительной продажи и регрессирует положительную величину; LightGBM регрессирует `log1p(quantity)`. Внешний `target_transform` blend — `none`. В inference LightGBM сначала возвращается через `expm1` в исходную шкалу, hurdle уже в исходной шкале. Затем глобальное `w=0.3` смешивает два массива одной features frame. Это фиксированная выпуклая сумма, без meta-model, без horizon/series weights, без OOF-learning весов. Значение `weight_hurdle` программно ограничено [0,1]. Перенос в Nonton требует собственного key alignment, поскольку source полагается на общий порядок features frame.

## Существенное расхождение комментария и кода

В начале `blend_model.py` hurdle назван `P(продажа > 0) × Poisson-величина`. Реальный `HurdleForecastModel.predict` возвращает **magnitude при probability >= gate, иначе 0**. Default gate=0.5; умножения на вероятность в этом методе нет. Fixture с probability `[.49,.5,.9]` и magnitude `[10,10,10]` дал `[0,10,10]`, а не `[4.9,5,9]`. Комментарий не заменяет исполненный код.

Фактическая формула: `H(x)=I[p(x)>=0.5]*m(x)`, `F(x)=0.3*H(x)+0.7*expm1(L(x))`. После смеси `clip>=0`, optional strict threshold `<t`, optional `np.rint`. В сохранённом config: threshold=0, round_int=true. Округляются отдельные daily predictions после смеси. Ни warehouse-, ни temporal-суммы не сохраняются. Нет top-down reconciliation или quantile ensemble.

## Валидация и применимость

Сохранённый config указывает strict holdout origin 2026-05-28, early stopping origin 2026-03-25; журнал и ранее выполненное сравнение требуют отличать этот holdout от refit модели. `reports/comparison_forecast64.md` уже обнаружил, что backtest финальной refit модели по прежним срезам не является OOF. Заявление source docstring о доминировании на восьми срезах не принято как независимое доказательство. Source SMAPE включает (0,0) в среднее, наш executable official scorer исключает; прежние README-цифры прямо несопоставимы.

Nonton может независимо реализовать общую выпуклую сумму и half-even rounding, не копируя файлы без лицензии. Применение весов .3/.7 к двум собственным forecasting candidates — **адаптация фиксированной формулы**, не воспроизведение hurdle+log-LGBM. Полный source pipeline с его observed-pair grid, permissive input handling и pickle не переносится. Улучшение точности требует отдельного измерения после исправления historical catalog.

## Дополнительные исследовательские клоны

M5 A1 действительно читает 6 CSV (recursive/nonrecursive × store/store-category/store-department), делает left merge по sample IDs и равное среднее; финальный combiner не округляет целые и не задаёт threshold. Это не два типа нового ансамбля Nonton и не доказательство, что M5 входит в указанную пользователем пару. Favorita `Utils.make_submission` делает `expm1`, clip [0,1000], затем `to_csv(float_format='%.4f')`; это форматирование до четырёх знаков при сериализации, а не integer rounding. Точных weights README-ансамбля в репозитории не установлено. Верхний clip=1000 не обоснован для Nonton.
