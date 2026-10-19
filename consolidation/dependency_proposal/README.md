# Предложение разделения зависимостей

19 октября 2026. Это подготовленный набор файлов, **ещё не миграция корневых manifests**. Root requirements, Dockerfile и существующая `.venv` не менялись. Locks реально разрешены `uv 0.12.6`, Python target 3.12, `--universal`, с ограничениями всех прежних установленных версий. Новое окружение не создавалось и пакеты не устанавливались. Доступность Ruff 0.17.1 и deptry 0.25.1 проверена через `pip index versions`.

| Lock | Windows | Linux | Назначение |
|---|---:|---:|---|
| requirements.lock | 23 | 22 | API и offline inference, без psutil |
| requirements-training.lock | 24 | 23 | runtime + psutil для training/benchmark entrypoints |
| requirements-dev.lock | 38 | 36 | training + pytest/httpx/coverage/Ruff/deptry |
| requirements-research.lock | 32 | 31 | training + matplotlib; тестовые инструменты не включены |

Счётчики не включают pip. В universal locks `tzdata` условна для Windows/emscripten; в dev `colorama` условна для Windows. Runtime имеет семь прямых корней: numpy, pandas, lightgbm, fastapi, starlette, uvicorn, python-multipart. `src.train` сам не импортирует psutil, но реальные training/benchmark entrypoints его используют.

**Изменений версий прежних пакетов: 0** во всех четырёх locks. Новый dev tooling добавляет ruff 0.17.1, deptry 0.25.1, requirements-parser 0.13.1, tomli 2.5.0. Все четыре закреплены; дальнейшее обновление не предусмотрено этой миграцией. ML pins остаются numpy 2.5.4, pandas 3.0.6, lightgbm 4.7.0. Hashes и машинная проверка — `resolution_summary.json`.

`baseline-constraints.txt` — ограничения воспроизводимой генерации, а не файл для установки всех пакетов. Пример генерации (аналогично для training/dev/research):

```powershell
uv pip compile consolidation/dependency_proposal/requirements.txt -c consolidation/dependency_proposal/baseline-constraints.txt --python-version 3.12 --universal --no-header --no-annotate -o consolidation/dependency_proposal/requirements.lock
```

Statistical benchmark сознательно остаётся изолированным: `reports/remediation/statsforecast_requirements.lock` содержит pandas 2.3.3 и не совместим с manifest-based serving, ожидающим pandas 3.0.6. Не объединять этот lock с основными группами. Historical файл сохранён без изменений.

## Следующий шаг после разрешения root

1. Root после regression gate переносит подготовленные manifests/locks в корень, сохраняя пути относительных `-r` включений. Затем создаётся новая `.venv_consolidated`; исходная `.venv` сохраняется для rollback.
2. Установить dev lock в новую среду. Зафиксировать inventory, `pip check`, отсутствие изменения ML-версий. Не обновлять pip или остальные пакеты без отдельного основания.
3. Ruff сначала запускать с выбранным узким набором правил ошибок импортов/синтаксиса; сохранить полный вывод, затем исправить доказанные проблемы. Hash-protected preprocessing нельзя автоматически форматировать или менять без пересборки совместимого artifact contract.
4. Deptry запускать по каноническим src/app и используемым CLI, исключая исторические research, external clones, extracted bundles и среду. Явно зарегистрировать first-party src/app; runtime и training/development requirements анализировать с соответствующим scope. Uvicorn запускается CLI, python-multipart обеспечивает FastAPI upload; допустимые точечные DEP002 exceptions для этих двух пакетов должны объясняться этим контрактом. Не отключать целиком анализ неизвестных/missing зависимостей. Импорт starlette уже объявлен явно.
5. Отдельную чистую runtime-среду установить только по requirements.lock. Проверить отсутствие pytest/httpx/psutil и успешные bundle loading, offline/API inference. Новый dev env не доказывает минимальность runtime.
6. Docker менять последовательно отдельным gate root; проверить Linux closure 22 пакета и системный libgomp1. Сделать image inspection, реальный build/run и parity; сокращение образа или ускорение пока не установлены.

Все последующие проверки должны использовать только явно выбранный новый Python, а не случайный `python` из PATH. Если research нужен вместе с тестами, можно установить два соответствующих locks в одной выделенной среде: их общие версии совпадают. Это не повод расширять production lock.
