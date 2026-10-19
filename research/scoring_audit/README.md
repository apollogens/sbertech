# Аудит scoring и model selection

Начать с [итоговой рекомендации](final_recommendation_ru.md), затем [пересмотренной политики](revised_model_selection_policy.md). Старый five-metric gate не является конкурсной целью. Локальный rank и minmax предпочитают разных challengers; production сохраняется до разрешения объективных неоднозначностей.

Обязательные результаты: [scoring audit](scoring_objective_audit.md), [per-fold matrix](per_fold_candidate_metrics.csv), [Pareto](pareto_frontier.csv), [rank sensitivity](weighted_rank_sensitivity.csv), [normalization sensitivity](normalization_sensitivity.md), [catalog provenance](catalog_provenance_audit.md), [independent verification](independent_verification.md). Дополнительно доступны per-series, sparse, warehouse и horizon diagnostics, source/input hashes и полный реестр151NPZ.

Воспроизведение из D:/SberTech, без обучения:

```powershell
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/reviewer_a_scoring.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/reviewer_c_verify.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/catalog_selection_audit.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/catalog_training_features.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/catalog_survivor_sensitivity.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/run_scoring_analysis.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/reviewer_a_rank_crosscheck.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/summarize_scoring_audit.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/finalize_audit_report.py
```

Запускать последовательно. Зависимости текущей `.venv` достаточны. Скрипты читают исходные данные по указанным в audit путям; raw CSV не копируются и внешним сервисам не передаются. Все новые выходы — в этой папке, старые saved forecasts и release не перезаписываются.
