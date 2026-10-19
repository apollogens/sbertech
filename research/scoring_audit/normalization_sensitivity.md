# Чувствительность к нормализации

Все оценки ниже — локальные диагностические значения на сохранённых прогнозах, не балл реального leaderboard. Средние считаются после нормализации отдельно на каждом из четырёх development origins. Нормализация средних сырых метрик дала бы другую задачу. Terminal исключён из сводок, но его строки доступны в исходных таблицах.

Основной объединённый набор: 17 прежних методов и 6 новых режимов, incumbent учитывается один раз. Всего 23 метода с полными пятью окнами. Ещё два старых режима z0.5 есть только на двух development origins; они включены в all_available и исходные таблицы, но не конкурируют по среднему двух окон с методами на четырёх. Результаты all_available на каждом origin отражают фактически разный pool. Точный порядок имён сохранён в `candidate_pools.json`.

## Rank на union23: executable SMAPE, прямой порядок, исходный argsort

| model | score | delta_vs_incumbent | wins | folds |
|---|---|---|---|---|
| weekly_direct_shape_z0.25 | 0.251705 | -0.050568 | 4 | 4 |
| two_part_gamma_z0.25 | 0.265341 | -0.036932 | 3 | 4 |
| lgb_l2_z0.25 | 0.277841 | -0.024432 | 3 | 4 |
| article_topdown_z0.25 | 0.286364 | -0.015909 | 2 | 4 |
| weekly_allocation_z0.25 | 0.292614 | -0.009659 | 2 | 4 |
| incumbent | 0.302273 | 0.000000 | 0 | 4 |
| mean28 | 0.411364 | 0.109091 | 0 | 4 |
| lgb_l1 | 0.436932 | 0.134659 | 0 | 4 |
| lgb_l1_z0.25 | 0.440909 | 0.138636 | 0 | 4 |
| mean90 | 0.444318 | 0.142045 | 0 | 4 |
| tsb | 0.460795 | 0.158523 | 0 | 4 |
| tsb_official | 0.461364 | 0.159091 | 0 | 4 |
| sba_official | 0.559091 | 0.256818 | 0 | 4 |
| adida_official | 0.561364 | 0.259091 | 0 | 4 |
| seasonal56 | 0.583523 | 0.281250 | 0 | 4 |
| article_topdown | 0.626136 | 0.323864 | 0 | 4 |
| last | 0.632955 | 0.330682 | 0 | 4 |
| two_part_gamma | 0.642045 | 0.339773 | 0 | 4 |
| weekly_direct_shape | 0.661932 | 0.359659 | 0 | 4 |
| tweedie_raw | 0.678977 | 0.376705 | 0 | 4 |
| lgb_l2 | 0.682955 | 0.380682 | 0 | 4 |
| zero | 0.751136 | 0.448864 | 0 | 4 |
| weekly_allocation | 0.788068 | 0.485795 | 0 | 4 |

## Состав пула и определение SMAPE

| pool | smape_definition | model | score | delta_vs_incumbent | wins | folds |
|---|---|---|---|---|---|---|
| all_available | executable | article_topdown_z0.25 | 0.282623 | -0.015009 | 2 | 4 |
| all_available | executable | incumbent | 0.297633 | 0.000000 | 0 | 4 |
| all_available | executable | weekly_allocation_z0.25 | 0.293561 | -0.004072 | 2 | 4 |
| all_available | executable | weekly_direct_shape_z0.25 | 0.249669 | -0.047964 | 4 | 4 |
| all_available | written | article_topdown_z0.25 | 0.259896 | -0.058570 | 3 | 4 |
| all_available | written | incumbent | 0.318466 | 0.000000 | 0 | 4 |
| all_available | written | weekly_allocation_z0.25 | 0.465909 | 0.147443 | 0 | 4 |
| all_available | written | weekly_direct_shape_z0.25 | 0.384138 | 0.065672 | 0 | 4 |
| architecture7 | executable | article_topdown_z0.25 | 0.418750 | 0.050000 | 2 | 4 |
| architecture7 | executable | incumbent | 0.368750 | 0.000000 | 0 | 4 |
| architecture7 | executable | weekly_allocation_z0.25 | 0.370833 | 0.002083 | 1 | 4 |
| architecture7 | executable | weekly_direct_shape_z0.25 | 0.310417 | -0.058333 | 3 | 4 |
| architecture7 | written | article_topdown_z0.25 | 0.168750 | -0.116667 | 4 | 4 |
| architecture7 | written | incumbent | 0.285417 | 0.000000 | 0 | 4 |
| architecture7 | written | weekly_allocation_z0.25 | 0.600000 | 0.314583 | 0 | 4 |
| architecture7 | written | weekly_direct_shape_z0.25 | 0.414583 | 0.129167 | 0 | 4 |
| focus4 | executable | article_topdown_z0.25 | 0.620833 | 0.079167 | 1 | 4 |
| focus4 | executable | incumbent | 0.541667 | 0.000000 | 0 | 4 |
| focus4 | executable | weekly_allocation_z0.25 | 0.441667 | -0.100000 | 3 | 4 |
| focus4 | executable | weekly_direct_shape_z0.25 | 0.395833 | -0.145833 | 4 | 4 |
| focus4 | written | article_topdown_z0.25 | 0.120833 | -0.254167 | 4 | 4 |
| focus4 | written | incumbent | 0.375000 | 0.000000 | 0 | 4 |
| focus4 | written | weekly_allocation_z0.25 | 0.900000 | 0.525000 | 0 | 4 |
| focus4 | written | weekly_direct_shape_z0.25 | 0.604167 | 0.229167 | 0 | 4 |
| learned_only | executable | article_topdown_z0.25 | 0.371154 | -0.005769 | 2 | 4 |
| learned_only | executable | incumbent | 0.376923 | 0.000000 | 0 | 4 |
| learned_only | executable | weekly_allocation_z0.25 | 0.353846 | -0.023077 | 2 | 4 |
| learned_only | executable | weekly_direct_shape_z0.25 | 0.295192 | -0.081731 | 4 | 4 |
| learned_only | written | article_topdown_z0.25 | 0.217308 | -0.082692 | 3 | 4 |
| learned_only | written | incumbent | 0.300000 | 0.000000 | 0 | 4 |
| learned_only | written | weekly_allocation_z0.25 | 0.546154 | 0.246154 | 0 | 4 |
| learned_only | written | weekly_direct_shape_z0.25 | 0.420192 | 0.120192 | 0 | 4 |
| legacy17 | executable | incumbent | 0.277344 | 0.000000 | 0 | 4 |
| legacy17 | written | incumbent | 0.308594 | 0.000000 | 0 | 4 |
| union23 | executable | article_topdown_z0.25 | 0.286364 | -0.015909 | 2 | 4 |
| union23 | executable | incumbent | 0.302273 | 0.000000 | 0 | 4 |
| union23 | executable | weekly_allocation_z0.25 | 0.292614 | -0.009659 | 2 | 4 |
| union23 | executable | weekly_direct_shape_z0.25 | 0.251705 | -0.050568 | 4 | 4 |
| union23 | written | article_topdown_z0.25 | 0.240909 | -0.061364 | 3 | 4 |
| union23 | written | incumbent | 0.302273 | 0.000000 | 0 | 4 |
| union23 | written | weekly_allocation_z0.25 | 0.451705 | 0.149432 | 0 | 4 |
| union23 | written | weekly_direct_shape_z0.25 | 0.371023 | 0.068750 | 0 | 4 |

В `weighted_rank_sensitivity.csv` сохранены все 86 352 строки: 5 origins, разные пулы, оба порядка, обе версии SMAPE и семь правил ties. Варианты ties: точный исходный `np.argsort`, стабильный ordinal, average/min/max/dense и average после округления метрики до 6 знаков. Последние шесть — диагностические альтернативы, не подтверждённые настройки организатора. Dense также делится на n−1 для изоляции эффекта присвоения рангов; это не отдельный официальный алгоритм. Для точного исходного варианта NumPy версия фиксирована; равные значения не получают автоматически общий ранг. Перестановка списка может менять результат; без стабильной сортировки это не обязательно простое правило «первый выигрывает» для любого размера.

Пулы: legacy17, architecture7, focus4, union23, learned_only, все leave-one-out варианты union23 (incumbent всегда сохранён), каждая пара incumbent–candidate и all_available. Это анализ чувствительности к выбранному окружению, не голосование сценариев и не независимые репликации. Дубликаты массивов удалены из основных сравнений; считать их отдельными участниками было бы искусственным изменением ранга.

## Minmax относительно last-value baseline

| origin | model | score | delta_vs_incumbent | clipped_metrics |
|---|---|---|---|---|
| 2025-09-14 | article_topdown_z0.25 | 0.853554 | 0.002365 | nan |
| 2025-09-14 | incumbent | 0.851189 | 0.000000 | nan |
| 2025-09-14 | weekly_allocation_z0.25 | 0.852164 | 0.000975 | nan |
| 2025-09-14 | weekly_direct_shape_z0.25 | 0.850931 | -0.000259 | nan |
| 2025-11-17 | article_topdown_z0.25 | 0.823222 | -0.006789 | nan |
| 2025-11-17 | incumbent | 0.830010 | 0.000000 | nan |
| 2025-11-17 | weekly_allocation_z0.25 | 0.836008 | 0.005998 | nan |
| 2025-11-17 | weekly_direct_shape_z0.25 | 0.833134 | 0.003123 | nan |
| 2026-01-20 | article_topdown_z0.25 | 0.824083 | -0.002954 | nan |
| 2026-01-20 | incumbent | 0.827038 | 0.000000 | nan |
| 2026-01-20 | weekly_allocation_z0.25 | 0.831808 | 0.004771 | nan |
| 2026-01-20 | weekly_direct_shape_z0.25 | 0.830944 | 0.003906 | nan |
| 2026-03-25 | article_topdown_z0.25 | 0.834622 | -0.003106 | nan |
| 2026-03-25 | incumbent | 0.837727 | 0.000000 | nan |
| 2026-03-25 | weekly_allocation_z0.25 | 0.836418 | -0.001310 | nan |
| 2026-03-25 | weekly_direct_shape_z0.25 | 0.836239 | -0.001488 | nan |

Пять метрик делятся на метрики сохранённого last-прогноза того же origin, значения выше 1 обрезаются. Это **не** масштабирование по минимуму/максимуму текущего пула. Поэтому удаление кандидата не меняет minmax других методов при неизменном baseline; в отличие от rank, добавление слабого метода не меняет их значения. Если baseline-метрика равна нулю, нулевой model error даёт 0, любой ненулевой — 1. Дополнительно рассчитан mean28 как альтернативный диагностический reference, а не признанный официальный baseline.

`minmax_sensitivity.csv` содержит вклад изменения каждой метрики в delta суммарной оценки; `clipped_metrics` показывает, где clipping скрывает величину ухудшения. Например, улучшение метрики, уже обрезанной до 1 и остающейся выше baseline, не изменит score. Нельзя интерпретировать неизменный score как отсутствие изменения качества.

## Что означает Парето

`pareto_frontier.csv` показывает доминирование на каждом origin для обеих версий SMAPE; дополнительно дана устойчивость к допуску 1e−10, чтобы не называть различие порядка roundoff содержательным преимуществом. `pareto_dominance_pairs.csv` перечисляет все пары доминирования. При положительных весах улучшение всех компонент монотонной нормализации — достаточное условие не ухудшить scalar score, но не необходимое. Строгое улучшение raw metric может быть скрыто clipping.

Если `S(c)=Σ w_j N_j(m_j(c))`, достаточно `Σ w_j [N_j(m_j(c))−N_j(m_j(i))]<0`. Отдельные слагаемые могут быть положительными. Поэтому `all_mean_metrics_improve` отсеивает и модели с лучшим weighted objective. Оно сохраняется как диагностика, а не заменяет конкурсную цель. Точный численный counterexample проверен Reviewer A в `reviewer_a_scoring.json`.
