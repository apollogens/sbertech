# Независимая численная проверка нормировки

Reviewer A, 19 октября 2026. Команда: `.venv\Scripts\python.exe research/scoring_audit/reviewer_a_rank_crosscheck.py`. Источник — независимо пересчитанный `reviewer_c_metrics.csv`; используются только remediation и architecture. `current_tweedie_z0.25` канонизирован в `incumbent`; до удаления дублей проверены одинаковые SHA канонического массива и совпадение пяти метрик плюс written SMAPE. Получено 23 кандидата × 5 origins. Обучения нет, terminal не участвует в приведённых средних.

Нормировки вызваны напрямую из `scripts/official_score.py`: rank и minmax относительно сохранённого last на том же origin. Рассчитаны union23, architecture7, focus4; executable/written SMAPE; лексикографический прямой/обратный порядок. Файл `reviewer_a_score_crosscheck.csv`: 1360 строк, включая отдельно обозначенный открытый terminal. `reviewer_a_score_development_means.csv` содержит средние только четырёх development origins; `reviewer_a_score_winners.csv` — победителей по каждому сценарию. JSON фиксирует SHA источника и скрипта.

После завершения независимого расчёта сопоставлены 680 строк rank с root `weighted_rank_sensitivity.csv`, policy=`official_argsort`: максимальное расхождение 8.33×10⁻¹⁷, PASS. Дополнительно сопоставлены 680 строк minmax с root `minmax_sensitivity.csv`, baseline=`last`, по origin+SMAPE definition+model; повторения наших pools/orders допускаются через merge many-to-one. Максимальное расхождение 1.11×10⁻¹⁶, PASS. Это отдельная реализация отбора/канонизации и вызовов исходной нормировки, использующая независимые метрики C.

| Диагностика среднего development score | union23 | architecture7 | focus4 |
|---|---|---|---|
| executable rank | weekly_direct_shape_z0.25, 0.251705 | weekly_direct_shape_z0.25, 0.310417 | weekly_direct_shape_z0.25, 0.395833 |
| executable minmax(last) | article_topdown_z0.25, 0.833870 | тот же | тот же |
| written rank | article_topdown_z0.25, 0.240909 | article_topdown_z0.25, 0.168750 | article_topdown_z0.25, 0.120833 |
| written minmax(last) | lgb_l1_z0.25, 0.715440 | article_topdown_z0.25, 0.846239 | article_topdown_z0.25, 0.846239 |

Обратный порядок не меняет указанных средних победителей. Разные absolute rank scores разных pools напрямую сравнивать как качество модели нельзя. Эти локальные scores не равны реальному leaderboard.

Для union23 executable rank incumbent=0.302273, weekly_allocation_z0.25=0.292614, weekly_direct_shape_z0.25=0.251705, article_topdown_z0.25=0.286364. Но executable minmax(last) соответственно 0.836491, 0.839100, 0.837812, 0.833870: обе weekly модели хуже incumbent по этому локальному критерию. Следовательно, выбор функции нормировки практически меняет оценку компромисса.

Победители отдельных development origins union23 executable rank: 2025-09-14 weekly_direct_shape_z0.25; 2025-11-17 article_topdown_z0.25; 2026-01-20 two_part_gamma_z0.25; 2026-03-25 weekly_direct_shape_z0.25. Единого победителя каждого окна нет. Для minmax(last) direct shape выигрывает первое окно, article topdown остальные три.

Проверка raw метрик из C подтверждает: weekly_allocation_z0.25 улучшает SMAPE/Bias в 4/4 development окнах, но ухудшает WAPE/RMSE/RMSLE в 4/4. Weekly_direct_shape_z0.25 улучшает SMAPE/Bias в 4/4, ухудшает WAPE в 4/4, RMSE/RMSLE в 3/4. Article_topdown_z0.25 ухудшает SMAPE в 4/4, улучшает WAPE/RMSLE в 4/4, RMSE/Bias — в 2/4. Поэтому преимущество weekly в локальном rank не является улучшением всех метрик, а среднее превосходство article по RMSE/Bias не является стабильностью этих двух метрик на каждом origin.

Результат поддерживает отказ от Pareto dominance как единственного критерия и одновременно не обосновывает автоматическую смену serving: критерий, состав участников и SMAPE трактовка меняют победителя, а окна повторно использованы.
