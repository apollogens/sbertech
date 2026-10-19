# Исследование архитектуры Nonton — 19.10.2026

**Решение: сохранить nonton-v1.** Исполнены десять обучений, 30 прогнозов кандидатов и пять сравнений incumbent. Ни один кандидат не прошёл заранее записанный консервативный критерий замены; частичные улучшения и ухудшения раскрыты численно. Production-файлы, прежний submission и архив выпуска сохранены.

- [Итоговый отчёт и решение](final_architecture_decision.md): все пять метрик, изменения, причины выбора, стоимость и неопределённость.
- [Независимая проверка](independent_review.md): 35 прогнозов, 15 replay, cutoff и 409 SHA-256.
- [Протокол](experiment_protocol.json), [план](experiment_plan.md), [уточнения контроля ресурсов](protocol_clarification.md).
- [Результаты экспериментов](experiment_results.csv), [изменения development](development_deltas.csv), [горизонты](horizon_analysis.md), [разреженный спрос](sparse_demand_analysis.md).
- [Реестр доказательств](evidence_register.csv), [конкурсные решения](competition_solutions.md), [научные методы](scientific_architectures.md), [реконструкция кода](architecture_reconstruction.md), [лицензии](source_licenses.md).
- [Карточки архитектур](architecture_cards.md), [пригодность данных](nonton_transfer_feasibility.md), [научный review](scientific_review.md), [материал защиты](presentation_evidence_ru.md).

Команды выполняются из `D:\SberTech`:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/architecture_experiments.py
.\.venv\Scripts\python.exe -X utf8 research/summarize_architectures.py
.\.venv\Scripts\python.exe -X utf8 research/independent_architecture_review.py
.\.venv\Scripts\python.exe -X utf8 research/audit_sparse_artifacts.py
.\.venv\Scripts\python.exe -X utf8 research/build_evidence_register.py
.\.venv\Scripts\python.exe -X utf8 research/capture_environment.py
.\.venv\Scripts\python.exe -X utf8 -m pytest tests reports/qa/check_backend_independent.py -q
```

Первый вызов повторяет обучение и перезаписывает только исследовательские результаты; независимый review восстанавливает прогнозы из уже сохранённых TXT без обучения. Никаких установок зависимостей для этих команд не требуется. Исходники внешних проектов сохранены изолированно, их setup/train не выполнялись и в production они не подключены. Новые neural/hierarchical библиотеки в production не устанавливались.

Исследование не создаёт нового untouched holdout. Сравнения на ранее открытом terminal — диагностика. Новая Docker-сборка и выпуск challenger не выполнялись; для текущего проекта заново прошли 177 тестов, прежние Docker/API проверки остаются историческими свидетельствами.
