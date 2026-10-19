# Протокол финального ограниченного цикла

Фиксация до запуска новых fits и просмотра их метрик, 19.10.2026. Исторические протоколы и прогнозы не переписываются. Все новые результаты — `integration/`; production остаётся nonton-v1 до решения.

## Исправление каталога и компоненты

Первичная сравнительная база — **corrected daily**, заново обученная с sales-known каталогом на каждом INNER training origin. Прежний incumbent остаётся отдельной исторической ссылкой; отличие corrected daily от него смешивает исправление каталога/кодирования и повторное обучение, поэтому не объявляется чистым улучшением модели. Для неизвестных на origin ID — deterministic zero fallback на полном output grid. Изменение метрик при другом наборе ключей не используется как улучшение; все прогнозы сохраняют 8789×64.

Фиксированы три Booster на outer origin: daily direct, weekly totals, article totals; shape повторно использует daily и weekly. По 220 деревьев Tweedie1.3, прежние параметры/seed, четыре потока. Origin-local hash encodings int32 стабильны; category mapping не используется. История и labels только до cutoff. Пять origins прежние, последнее окно диагностическое. Training15 fits, возможен ещё final fit трёх Booster для экспериментального standalone bundle; это не production promotion. Бюджет ручного контроля — до20мин fit и10GB sampled RSS, автоматического abort нет. Тяжёлые jobs выполняются последовательно.

## Ограниченная матрица

Четыре самостоятельных компонента D=daily, W=weekly allocation, S=weekly direct shape, A=article topdown. Ансамбли: равный D/W/S/A; D/A с весами .75/.25, .50/.50, .25/.75; D/S .50/.50. Source-derived дополнительный вариант D/A .70/.30 воспроизводит лишь общий fixed convex blend найденного forecast-64-v1, а не чужую hurdle модель. Если второй source не идентифицирован, его интеграция не заявляется и методы не подставляются.

Для десяти механизмов заранее заданы P0 continuous, P1 threshold<.25, P2 np.rint half-even, P3 threshold затем np.rint. P2 и P3 математически эквивалентны при nonnegative inputs; обе строки сохраняются как абляция, дубликаты не получают отдельных голосов в rank. Дополнительно P4 для equal4 и D/A .5: усреднить thresholded components без повторного порога; для equal4 — усреднить rounded components. Всего43 явных варианта, включая эквивалентные, без нового поиска порога. SOURCE round_int=true соответствует P2, threshold0 соответствует P0 перед округлением; отдельное дублирующее имя не улучшает score.

Constrained learned weights: выбрать из трёх D/A весов (.75/.25,.50/.50,.25/.75) только по первым двум development origins по среднему minmax(last), deterministic tie-break к .5 затем меньшему весу A. Зафиксировать выбранный вес до расчёта селекционных сводок последних двух development origins. Это chronological diagnostic на уже открытых периодах, не unbiased новый holdout. Только P1; новая оптимизация по пяти метрикам/терминалу запрещена. Stacking не выполняется: четырёх переиспользованных origins мало для обоснованного meta-model.

## Оценка и выбор

Первичный executable SMAPE; дополнительно written SMAPE. Пять official metrics, signed Bias, zero-total eligible, changed-positive-to-zero, total/daily/series volume distortion, sparse и horizon diagnostics. Нормализации: фиксированный основной universe — corrected D/W/S/A P1, equal4 P1, три D/A P1, D/S P1, source .7/.3 P1, D/W/S/A P0 и D/W/S/A P2, всего18 методов. Ровно тот же universe на каждом origin; exact numerical duplicates удаляются до rank с явными aliases. Дополнительно focus/base-only pool и pairwise comparisons. Minmax(last) не зависит от состава пула. Ties исходного argsort и average диагностически, оба порядка; все raw metrics обязательны.

Не требуется одновременное улучшение пяти метрик. Promotion может рассматриваться при согласованном улучшении средних executable rank и minmax относительно corrected daily на первых двух и последних двух development origins, не менее3/4 выигранных окон по каждому score; величина ухудшения отдельных метрик и стоимость раскрываются. Это предварительный фильтр, не доказательство generalization. При противоречии scoring interpretations, существенном риске временного каталога, отсутствии воспроизводимости на180-дневном входе или полном serving benchmark promotion запрещена до независимого review. При недостаточных данных о реальной конкурсной нормализации допускается итог «сохранить incumbent, candidate исследовательский». Terminal не выбирает веса и не служит veto.

Для поставки нового candidate обязательны hashes, полный inference180дней, model manifests, key alignment, offline/API/Docker parity и независимая численная проверка. Сохранение incumbent тоже сопровождается новым полным API/Docker/submission прогоном. Нового untouched test не существует; утверждение о будущем превосходстве недопустимо.
