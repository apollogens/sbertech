# Решение о канонической архитектуре

Основание: три read-only аудита и проверенные существующие manifests. Один API и один CLI используют `src.runtime.load_bundle/predict_64`. Active release явно задан конфигурацией и остаётся nonton-v1. Выбор другого versioned bundle не требует изменения Python-кода.

Шесть byte-bound модулей incumbent (`data`, `features`, `baselines`, `predict`, `submission`, `artifacts`) сохраняются без изменения: это реальные общие реализации, а не новые копии. Их веса и manifest сохраняются. Новый dispatcher делегирует им legacy-вызовы, чтобы сохранить численные значения и действующий контракт.

Из экспериментального кода выделяются канонические runtime-only модули: `src.catalog`, `src.temporal`, `src.ensemble`, `src.components`. Они не импортируют `scripts`, `integration`, training или research. Source-bound экспериментальный bundle мигрирует в отдельный формат, который связывает прежние веса и feature contract с новыми runtime sources; parent hashes и проверка эквивалентности сохраняются. Старый bundle/ZIP не перепаковывается задним числом.

`app.predictor` сохраняет transactional cache и публичные monkeypatch/import точки; меняется только импорт общего dispatcher. Разрешены стратегии incumbent, corrected D/W/S/A и equal4:P1. D/W вычисляются один раз для S, не загружаются повторные Booster. Rounding остаётся исследовательской возможностью, production threshold .25 не изменяется.

Политика истории едина и явна: **вся предоставленная история, минимум180календарных дней, cutoff=max(sales.date)**. Будущие stock отсекаются. Она сохраняет алгоритмы и пригодность уже обученных весов; скрытого переключения long_mean на фиксированную180дневную статистику нет. Production-like backtest сам передаёт ровно180дней sales/stock тому же runtime. Его метрики публикуются отдельно от full-history и не выдаются за новый untouched test. Если потребуется постоянно усекать любой вход до180дней и обучать только так, это другой feature contract и отдельный retrain, а не «cleanup».

Сначала runtime и regression, затем dependencies/clean env, затем архивирование доказанно заменённых executable adapters, затем Docker обоих selectable bundles и независимый review. Исторические reports/NPZ/данные/scorer/ZIP не удаляются. Неактивные исследовательские исходники, нужные для old source hashes, доступны через immutable snapshot и прежние ZIP; migration ledger содержит новые пути воспроизведения.
