# Проверка реальных CLI

Финальный независимый запуск:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests reports/qa/check_backend_independent.py -q --junitxml=reports/remediation/final_tests.xml
```

Результат: **177 passed, 0 failed, 0 skipped**, 36.63 с; одно upstream предупреждение Starlette/httpx. Сырые выводы — `final_pytest.txt`, машинный протокол — `final_tests.xml`. Из них 20 — subprocess CLI cases, 36 — новые backend regressions, 2 — новые ML correctness cases; остальные 119 — прежние основная и независимая backend suites. Повторного запуска вместо результата не подразумевается.

## Entry points и выполненный scope

Все CLI cases запускают настоящий Python-процесс по абсолютному пути скрипта из чужого временного cwd; импорт helper вместо команды не используется.

| Назначение | Настоящий entry point | Выполненные проверки |
|---|---|---|
| Аудит | `scripts/audit_inputs.py` | Реальные CSV → JSON; счётчик строк; иной cwd; отсутствующие файлы; help/неизвестная опция |
| Обучение | `scripts/train_final.py` | Реальный tiny fit, повторный fit с побитово одинаковыми весами; новый traceable manifest/record; отсутствующие файлы; invalid selection; rounds=0; help/опции; отдельный полный финальный fit на реальной панели |
| Backtest | `scripts/backtest_baselines.py` | Реальная панель NPZ → 18 записей; иной cwd; отсутствующий cache; help/опции |
| Оценка | `scripts/official_score.py` | Настоящий `--truth/--submissions/--method rank/--output` → leaderboard; help/неизвестная опция; независимые numerical/compatibility fixtures отдельно |
| Упаковка | `scripts/package_model.py` | Настоящий legacy bundle → явно reconstructed_unverified; missing files; help/опции; существующий manifest проверяется, не переподписывается |
| Прогноз | `scripts/predict.py` | Реальные временные CSV/model → полный tiny grid; повтор byte-identical; иной cwd; отсутствующие входы; обязательные аргументы/help/опции |
| Проверка submission | `scripts/validate_submission.py` | Успех на созданном grid; отрицательная quantity → exit2; missing file; иной cwd; help/опции |
| Весь pipeline | `scripts/run_pipeline.py` | Настоящие исходные CSV за 600 дней, `--refresh --rounds 2 --work-dir TEMP` → audit/cache/OOF/selection/model/manifest/submission; загрузка итогового bundle; missing source; rounds=0 без создания выходов; help/опции |
| API startup | `python -m uvicorn app.main:app` | Реальный HTTP `/health` из чужого cwd; missing bundle → startup failure; завершение процесса. Настоящий полноразмерный HTTP — отдельный probe |

Tiny subprocess fits выполняют формулы и запись артефактов, но не служат оценкой качества больших данных. Финальное обучение на реальной панели выполнено отдельной настоящей командой `scripts/train_final.py --output-dir reports/remediation/retrained_model`: 1 476 552 training rows, 220 итераций, 22.886230 с. Run ID и hashes — `model/training_record.json`; веса/config/catalog независимо сравнены с snapshot и совпали побитово.

## Изменения CLI и границы утверждений

Аудит, train, backtest, predict и validate получили явные пути и defaults от корня проекта. Pipeline получил `--work-dir`; invalid rounds отклоняются до вычислений. Собственные CLI возвращают exit2 с русским сообщением при проверенных ошибках; argparse также использует exit2. API startup failure возвращает ненулевой код uvicorn. Официальный scorer сохранён без изменений: его warnings-only validator, обработка ties и ошибка при произвольном повреждённом файле не заменялись внутренней версией.

Проверены перечисленные случаи, а не все возможные повреждения каждого CSV/NPZ. Детальные invalid dates/ranges/headers/schema/mapping/corruption покрыты production API/offline tests; это отдельно от subprocess scope. Полный `run_pipeline --refresh` с 220 деревьями на всех исходных данных в этой ремедиации не повторялся: полный финальный fit и все новые исторические challengers исполнялись раздельными entry points. Нельзя выдавать tiny pipeline за такой повторный большой запуск.

Источники: [Python argparse](https://docs.python.org/3/library/argparse.html), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/). Независимый reviewer исполнил финальный suite; локальные исходники тестов — `tests/test_remediation_cli.py`, `tests/test_remediation_backend.py`, `tests/test_remediation_models.py`.
