# Владение файлами и порядок интеграции

1. Root: snapshot/baseline; `src/runtime.py`, `src/cli.py`, runtime config, migration/packaging/verification CLI; `app/predictor.py`; README/Docker после regression; итоговые manifests/отчёты.
2. Agent A после read-only аудита: только новые `src/catalog.py`, `src/temporal.py`, `src/ensemble.py`, `src/components.py`, их точечные unit tests. Не изменяет шесть incumbent source-hash файлов, app или locks.
3. Agent C: новые tests dispatcher/config/API стратегии и ML history contract, независимые coverage checks. Не меняет implementation модули и model artifacts.
4. Agent B после runtime regression: dependency split/locks, clean environment и lint configuration; не меняет runtime implementation и Docker одновременно с root. До gate7 — только подготовительные записи.
5. Финальный независимый QA: отдельное исполнение clean tests, scorer/manifest/rollback и полноразмерных API/Docker; review не выдаётся на основании рассказа root.

Тяжёлые fits не запускаются: текущая консолидация сохраняет numerical contracts существующих моделей. Expensive full-size inference/backtest/Docker jobs выполняются последовательно или по согласованию, чтобы latency имела ясную область измерения. Удаления/архивирование и смена dependencies не идут одновременно с Docker build.

Фактическое уточнение делегирования: после интеграции root передал Agent C реализацию `src/cli.py`, `tests/test_cli.py`; Agent A — production-like backtest и проверку ML-выходов. Agent C выполнял peer QA runtime/cleanup/ML/Docker с раскрытием собственного авторства CLI. Agent B отдельно проверял Docker/API/CLI, которые он не реализовывал. Ни один авторский аудит не называется внешней независимой экспертизой.
