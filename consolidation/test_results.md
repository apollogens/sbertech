# Исполненные проверки

Baseline до изменений: 193 passed, 37.61 с. После нового runtime: 219 passed, 37.05 с. После Gate 8 в чистой среде: 237 passed, 48.57 с. Финальная общая команда: **238 passed**, 61.56 с; включает 193 прежних проверки и 45 добавленных. Один Starlette warning о будущем httpx не подавлялся; обновление библиотек не входило в cleanup. Числа разных прогонов не суммируются.

```powershell
.venv_consolidated/Scripts/python.exe -X utf8 -m src.cli test -- tests reports/qa/check_backend_independent.py integration/test_catalog_policy.py integration/test_ensemble_engine.py -q
```

Ruff E9/F и deptry по каноническим src/app: 0 замечаний. Обе новые среды проходят pip check. Чистый runtime содержит 23 пакета Windows без pip, 22 Linux; pytest/httpx/psutil не требуются для serving.

Реальные сохранённые модели дали полный grid 562496 строк. Runtime facade и прежние Windows reference CSV совпали побайтово; отдельное воспроизведение четырёх raw components и пяти P1 стратегий дало maxdiff=0.0. CLI намеренно пишет LF: количества и порядок ключей сохранены, текстовый hash отличается от CRLF reference. Host real CLI и оба настоящих Docker HTTP outputs проверены отдельно от synthetic unit tests.

180-day backtest: 25 новых прогнозов D/W/S/A/equal4, пять historical origins, official primitives, sparse/horizon diagnostics. 25 прежних reference NPZ и official metrics сверены отдельно. Reviewer независимо пересчитал все 25 новых NPZ. Не выполнен квадратичный full official merge на всех панелях; проверены исходные функции метрик и ранее сохранённый merge fixture.

Rollback: 1003 извлечённых файла сверены по SHA-256; старая модель на 562496 строках maxdiff=3.55e−15. Peer QA повторил hashes всего ZIP и всех извлечённых файлов. Доказательства — JSON/логи рядом; Docker measurements — `docker_benchmarks.md`.
