# Проверка ML-контрактов консолидации

Проверяющий: агент C. Проверка 19 октября 2026. Проверены исходный feature contract, новые чистые модули и dispatcher/API на synthetic Boosters. Итоговые real-model/backtest результаты публикуются отдельными release probes. Этот документ не является разрешением promotion.

## Информационная политика

`src.features.snapshot` срезает `y` и `stock` до origin перед вычислением статистик. Все окна ограничены 180 днями или меньше, кроме `long_mean`, который использует всю предоставленную историю. Поэтому прежние TXT нельзя объявлять обученными на фиксированных 180 днях: финальные training snapshots могли содержать больше истории. Сохранение политики «вся предоставленная история, минимум 180 календарных дней» не меняет feature algorithm. Постоянное усечение всех входов до 180 дней потребовало бы отдельного feature contract и проверки обучения.

Production-like backtest должен передавать тому же serving runtime ровно последние 180 календарных дней. Его метрики нужно отличать от прежних full-history результатов. Это проверяет существующие веса при коротком input, но не превращает их в модели, обученные только на коротком input, и не создаёт untouched holdout.

## Каталог и encoder

Incumbent использует фиксированный отсортированный catalog и ordinal categories; corrected components используют стабильные bounded SHA-256 int32 categories. Их feature arrays внешне похожи, но кодировка несовместима. Правильное решение — отдельные versioned loaders, config/schema и manifests; замена encoder у incumbent недопустима.

Новый `src.catalog` требует explicit first-observed membership и не содержит чтения research CSV. Membership определяется сырыми sales-строками, включая quantity=0. При 180-дневном input ID без sales-строк в этих днях становится unknown для corrected predictor, даже если был известен раньше. Это ограничение входной информации, а не разрешение читать полный исторический first_seen. Output catalog остаётся полным; unknown output ID получает 0. Stock-only ID не входит в sales-only feature catalog.

## Временная и иерархическая арифметика

`src.temporal.BUCKETS` задаёт [1,8), [8,15), …, [57,64), [64,65), то есть 9 семидневных блоков и один день. W делит предсказанные totals историческими weekday weights; S делит те же totals формой D, с uniform fallback при нулевой массе. A агрегирует товары по складам и использует только исторические сглаженные warehouse shares. D/W вычисляются один раз для S; всего ensemble требует три разных Booster, не четыре.

Raw W/S сохраняют weekly totals, raw A сохраняет article totals. Threshold .25 применяется после convex average и может нарушить когерентность. Integer rounding не нужен для output contract и не должен включаться при cleanup. Все компонентные массивы проверяются на конечность и неотрицательность, итог — на полный grid.

Новый `src.ensemble` формирует independent expected grid, metadata identity origin/horizon/catalog SHA-256 и keyed alignment. При `expected_identity` несовпадение attrs отвергается; model bundle identity добавляется dispatcher. Наличие одинаковых строковых ключей само по себе не доказывает совместимость моделей.

## Границы исходного аудита

Оригинальный official scorer не изменялся агентом C. Существующие 13 metrics tests и дополнительные QA cases сравнивают официальный и локальный scoring, включая исключение zero-zero из executable SMAPE и series absolute Bias. Численное совпадение migrated real-model output и новые 180-day per-origin metrics должен подтвердить отдельный executed probe. Unit tests с synthetic Booster не заменяют этот результат.

Для новой схемы добавлен `tests/test_unified_runtime.py`: legacy delegation, selected components/shared calls, полный output, неизвестный ID=0, .25 boundary без rounding, минимум180, row permutation, future-stock invariance, zero-sales membership, feature mismatch и actual component path через HTTP/cache. Дополнительно проверены aliases D/W/S/A, загрузка только требуемых моделей, относительные config paths независимо от cwd, отказ от ensemble strategy с incumbent bundle и corrupted origin/horizon/catalog metadata.

Выполнено `.venv/Scripts/python.exe -m pytest tests/test_unified_runtime.py -q`: **20 passed**, одна deprecation warning FastAPI/TestClient о httpx. Модели в этих тестах synthetic и только реализуют `feature_name/predict`; feature construction, membership, component sharing, keyed ensemble, dispatcher, API validators и cache — настоящие. Обучение не вызывалось. Полноразмерные TXT и Docker этой командой не проверялись.

## Выполненная проверка сохранённых результатов и исходной арифметики

Дополнительный проверяющий — агент A, автор четырёх извлечённых runtime-модулей и 180-day runner. Это повторная исполнимая авторская проверка, **не полностью независимый аудит авторства**. Отдельный финальный QA агента C не заменяется этим разделом. Команда: `.venv/Scripts/python.exe -X utf8 consolidation/verify_ml_outputs.py`; машинное свидетельство — `consolidation/ml_output_review.json`. Нового обучения и model inference эта команда не выполняет.

Из `consolidation/legacy_source.zip` прочитаны исходные функции. AST `weekly_frame`, `weekday_weights`, `allocate_buckets`, `warehouse_shares`, `stable_codes`, `expand_to_output` совпал с новыми runtime-функциями. SHA256 всех шести incumbent source-bound файлов и официального scorer совпал с pre-merge manifest. Это более сильное свидетельство сохранения формул, чем совпадение одного среднего score, но не полная проверка всех путей исполнения.

Независимо от backtest runner заново рассчитаны все пять official-метрик для **10 сохранённых прогнозов**: D/W/S/A/equal4 на origins 2025-09-14 и 2026-03-25. Прямо вызваны исходные `smape_series`, `bias_abs_series`, `wape`, `rmse`, `rmsle`; runner-функция metrics не используется. Все NPZ имеют заявленный origin, history_days=180, форму (64,8789), конечные неотрицательные числа; ожидаемая сетка содержит 562496 уникальных ключей. Максимальное отличие метрик от CSV — 5.56×10⁻¹⁷. Все development-средние дополнительно вычислены заново из per-origin CSV, максимальное отличие — 5.56×10⁻¹⁷. Полный квадратичный scorer merge не запускался.

Отдельный `backtest_180/reference_validation.json` фиксирует проверку origin/key hash всех 25 прежних full-history NPZ и согласие их пересчитанных метрик с прежним experiment CSV до 5.69×10⁻¹⁴. Новый `metrics.csv` содержит 399 строк с all/sparse/dense/horizon группами; paired CSV — 189 строк. Сохранены 25 новых component/ensemble NPZ. Incumbent 180-day inference выполнен только для двух однозначно привязанных исторических TXT; три отсутствующих origin не заменены финальными весами. Сравнение двухоконного incumbent mean с четырёхоконным mean corrected-моделей недопустимо; число origins явно приведено в таблицах.

Проверена фактическая цепочка источников: исторические TXT загружаются только после проверки artifact SHA256, совпадения cutoff и feature names. До построения панели sales/stock обрезаются по [origin−179, origin]; stock очищается прежним `clean_stock`. Membership формируется только из переданных sales, включая нулевые строки. `asof_panel` отрезает будущую историю и неизвестные категории перед snapshot/агрегацией. Article snapshot сохраняет правило unknown stock при неполноте агрегата. Хеш-коды после snapshot остаются int32, порядок features проверяется отдельно для daily/article и weekly. Output catalog используется для проекции результата, без добавления будущих ID в predictive statistics. `long_mean` по serving-входу из 180 дней намеренно отличается от full-history обучения; это раскрытый distribution shift, не новый training protocol.

Real-model CSV replay `consolidation/regression/result.json` подтверждает byte-identical CSV для incumbent и equal4 относительно pre-consolidation output на 562496 строках. Максимальное числовое отличие после чтения CSV — 3.56×10⁻¹⁵. Одного совпадения смеси недостаточно для проверки каждого компонента: ошибки могли бы взаимно сократиться. Поэтому дополнительно выполнена описанная ниже проверка четырёх raw-компонентов.

**Real-weight component replay выполнен отдельно до запуска тяжёлой Docker-проверки.** Два последовательных отдельных процесса выполнили inference на одном и том же 180-дневном входе: исходный `predict_components` из полностью восстановленного `consolidation/rollback_verified_complete` с исходным loader и проверкой старого manifest, затем канонический `predict_component_frames` с новым runtime loader. Membership явно вычислен только по этим sales; input SHA256 совпадают. Все четыре raw keyed-компонента D/W/S/A содержат по 562496 значений и совпадают точно: максимальное отличие **0.0**, key hashes совпадают. Все пять доступных P1-стратегий, включая equal4, также совпали точно после комбинации и threshold. Два сохранённых NPZ даже имеют одинаковый SHA256 `e19fb9c76e3c7f7fdf765981c5cc7eb41a755147dbed212fc85b8bf04256d231`.

Исполнимый probe — `consolidation/component_replay.py` с `--old` и отдельным `--root` для старого процесса; результаты — `component_replay_old.npz`, `component_replay_new.npz`, `component_replay_result.json`, ссылка также добавлена в `ml_output_review.json`. Обучение и изменения src не выполнялись. Это real-weight parity на одном финальном 180-дневном input, не повторный component replay на всех исторических origins. Указанный выше исходный пробел ограниченного обзора устранён в этой области.

На одинаковом 180-дневном входе equal4 сохраняет небольшое улучшение пяти средних development-метрик относительно corrected D. Окна повторно использовались; terminal не участвует в выборе. Новых признаков будущего или изменений encoder incumbent при этой проверке не выявлено. Это свидетельство соблюдения исследованного контракта, без утверждения полного отсутствия всех возможных утечек, статистической значимости или superiority над incumbent на четырёх 180-day origins.
