# Финальная консолидация Nonton

**Один проект и один runtime поставлены; активным остаётся nonton-v1. equal4:P1 — технически проверенный selectable release candidate.** Веб-API, CLI и Docker используют общий inference; четыре corrected представления доступны через отдельный versioned bundle. Консолидация не переобучала модели и не изменяла их численные прогнозы.

Объединены собственные production и integration реализации Nonton. Подтверждён один внешний GitHub-проект filipp880/forecast-64-v1, commit f8a8c6e60edaf12af2fd351e290c35e6875afea0; его tracked tree не содержит лицензии. Чужой код не перенесён. Самостоятельно реализованы общая выпуклая смесь и half-even исследовательский postprocessing. Второй пользовательский репозиторий не установлен; интеграция двух внешних проектов не заявляется.

Общие catalog, temporal allocation, component inference и ensemble вынесены в src. Исторические paths стали тонкими adapters; 6 заменённых release-инструментов архивированы. Данные, официальный scorer, все прежние модели/NPZ/ZIP сохранены. Подробный ledger и migration_log описывают каждый путь. Legacy scripts/predict.py также делегирует единому CLI.

| Инженерный показатель | До | После |
| --- | --- | --- |
| runtime_packages_windows_excluding_pip | 33 | 23 |
| explicit_regression_cases | 193 | 238 |
| separate_component_boosters | 3 | 3 |
| duplicate_release_adapters_active | 6 | 0 |
| legacy_helper_file_lines | 425 | 250 |

Число строк относится только к четырём старым helper-файлам; общий объём проекта вырос из-за новых стратегий, проверок и отчётов. Сокращение dependencies означает выделение runtime, а не удаление возможностей обучения/тестирования. Из runtime убраны certifi, colorama, httpcore, httpx, iniconfig, packaging, pluggy, psutil, Pygments, pytest; они остаются в соответствующих dev/training группах. Runtime сохраняет numpy/pandas/lightgbm, FastAPI/Starlette/Uvicorn, multipart и разрешённые transitive dependencies. Версии прежних библиотек не обновлялись.

Чистые runtime и dev установки проходят pip check. **238 тестов прошли**, включая все 193 прежних. Ruff/deptry: 0 замечаний. Реальные четыре raw компонента и все пять P1 стратегий совпали с frozen реализацией точно (maxdiff=0). Host CLI совпадает численно; новый serializer явно использует LF вместо прежнего CRLF. Оригинальный submission.csv не заменён; новый `consolidation/submission.csv` валиден: 562496 строк, 64 дня 2026-08-01—2026-10-03, 11 складов, 799 товаров, полное покрытие без duplicate/NaN/Inf/negative.

Production-like backtest завершён на пяти origins с ровно 180 днями входных sales/stock. Средние по четырём development origins, меньше лучше:

| Кандидат | SMAPE | WAPE | RMSE | Bias | RMSLE |
| --- | --- | --- | --- | --- | --- |
| Corrected D:P1 | 165.307454 | 85.931055 | 0.775274 | 82.795357 | 0.307112 |
| equal4:P1 | 165.027991 | 85.723702 | 0.771062 | 81.284307 | 0.305680 |

Выигрыш equal4 против corrected D небольшой, но присутствует во всех пяти средних. Это прежние повторно используемые окна. Incumbent historical TXT однозначно сохранились лишь для двух origins, поэтому полного четырёхоконного сравнения incumbent/equal4 при одинаковом 180-day input нет. Terminal diagnostic не участвует в выборе. Политика serving — вся переданная история, минимум 180 дней; сокращение входной истории в backtest не выдаётся за эффект cleanup.

| Docker | image ls | inspect.Size, байт | POST, с | Повтор, с | cgroup peak, байт | max \|offline−API\| |
| --- | --- | --- | --- | --- | --- | --- |
| nonton-v1 | 619MB | 143563315 | 11.306 | 11.506 | 1325481984 | 3.55e-15 |
| equal4 | 1.43GB | 147131116 | 21.868 | 20.934 | 4691660800 | 1.07e-14 |

Оба финальных образа проверены без сети, 4 CPU/6 GiB: cache/filter/JSON/repeat/error/restart пройдены. Лимиты конкурса соблюдены. POST включает валидацию CSV, признаки, prediction, alignment и сериализацию; загрузка весов происходит при startup и в POST не включена. Startup отдельно не измерен. Candidate заметно тяжелее. Сравнения скорости с прежними измерениями не являются статистическим benchmark. Новый ensemble теперь проверен через общий API и Docker; это техническая готовность кандидата, не доказанная победа по качеству.

Манифесты связывают preprocessing, encoder, признаки, численные зависимости и веса. Повреждённые artifacts/config отвергаются. Старые manifests сохранены; новый runtime contract имеет отдельную identity. External preregistration и новое untouched test не заявляются. Executable/written SMAPE и rank/minmax uncertainty остаются раскрыты. Survivorship output catalog и неизвестный организаторский catalog полностью историческим replay не устраняются. Авторы runtime/CLI участвовали в peer review с раскрытием ролей; это отдельные агентские проверки, не внешняя сертификация.

Артефакты: `consolidation/nonton_consolidated_verified.zip`, `release_manifest.json`, `release_package.json`, `submission.csv`; candidate weights — `bundles/equal4-rc1`; runtime selection — `config/runtime.json`. Rollback отдельно: `pre_merge_snapshot.zip` и `pre_merge_manifest.json`, проверены 1003 извлечённых файла и старый полноразмерный inference. Точные инструкции — rollback_plan.md; архив извлекается в новую пустую папку. Для переключения только модели достаточно nonton-v1 config и перезапуска API без переобучения.

```powershell
.venv_consolidated/Scripts/python.exe -m src.cli test
.venv_consolidated/Scripts/python.exe -m src.cli predict --sales sales.csv --stock stock.csv --output forecast.csv
.venv_consolidated/Scripts/python.exe -m src.cli serve --model-dir bundles/equal4-rc1 --strategy equal4:P1
.venv_consolidated/Scripts/python.exe -m src.cli docker test --image nonton:consolidated-v1 --strategy nonton-v1
.venv_consolidated/Scripts/python.exe -m src.cli docker test --image nonton:consolidated-equal4 --strategy equal4
```
