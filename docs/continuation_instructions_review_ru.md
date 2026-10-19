# Независимая проверка постоянных инструкций

Дата: 20 октября 2026. Проверяющий: отдельный native агент `continuation_review`. Проверяющий не писал четыре проверяемых документа и не изменял runtime, модели или тесты. Проверка ограничена текущими исходниками, файлами свидетельств и лёгкими исполнимыми проверками; повторные обучение, полноразмерный inference и Docker не запускались.

**Результат: PASS для содержания инструкций.** Проверены `AGENTS.md`, `docs/CODEX_PROJECT_MASTER_PROMPT.md`, `docs/CODEX_RESUME_PROMPT.md`, `docs/PROJECT_STATUS.md` и журнал продолжения. Существенных неподтверждённых утверждений или противоречий между ними не выявлено. Временный статус публикации и статус самого review следует обновить после фактического окончания соответствующих операций; этот PASS не подтверждает будущий commit/push.

## Что проверено

- Все шесть локальных Markdown-ссылок четырёх документов разрешаются. Дополнительно проверено существование 20 явно перечисленных основных источников: README, матрицы требований/допущений, scorer, consolidated architecture/release/review/manifest receipts, 180-day report, integration selection/provenance и training runner, execution log.
- Все десять настоящих subcommand `test`, `audit`, `train`, `backtest`, `score`, `predict`, `validate`, `package`, `serve`, `docker` исполнены с `--help`: каждый завершился кодом 0. Опции примеров сопоставлены с `src/cli.py`; Docker image/reference selection — с `consolidation/docker_verify.ps1`. Полезные нагрузки примеров не запускались.
- Master и resume prompts написаны по-английски; предпочтение русского общения закреплено во всех соответствующих правилах. Resume ведёт к реальным AGENTS/master/status/log и не содержит застывших цифр тестов.
- `config/runtime.json` действительно выбирает `../model` / `nonton-v1`; corrected D/W/S/A и `equal4:P1` доступны через отдельный bundle. Прочитаны runtime strategy map, оба source-binding контракта, API lifespan/validators, Dockerfile, dependency manifests.
- Описаны точные шесть incumbent bound files и ссылка на девять candidate RUNTIME_SOURCES; запрещено скрывать drift простым обновлением hashes. `.gitattributes` сохраняет исходные bytes. Frozen release и новая Git-публикация разграничены.
- История используется целиком при минимуме 180 календарных дней; corrected membership зависит от переданных sales, включая quantity=0. Полный output grid, порог после смеси, несовместимость encoder, отсутствие integer rounding, API cache/worker и будущий stock описаны в соответствии с кодом.
- Полный scope 238 и извлечённый package scope 222 не суммируются. Master правильно отличает default `test` от явной команды с 16 historical integration tests; зависимость одного historical теста от ignored cache раскрыта. Private CSV и отдельные требования backtest/Docker не объявлены входящими в свежий clone.
- Свежий `consolidation/continuation_tests.log` содержит **238 passed, 1 warning in 48.92s**. Проверяющий прочитал лог, но не выдаёт исполнение этой команды root за свой повторный запуск. Исторические package/Docker/raw-component результаты подтверждаются соответствующими receipts и логами; документы явно называют их прежними измерениями.
- В начале проверки обнаружена текущая синтаксическая ошибка `tests/test_api.py`: один пробел перед начальным module docstring, единственное отличие от frozen ZIP. Root исправил ровно один байт; последующая независимая `compile(...)` текущего файла прошла. Модели/прогнозная логика этим исправлением не затрагивались.
- Сохранены научные ограничения: reused origins, terminal diagnostic, отсутствие нового untouched test, небольшой выигрыш относительно corrected D, отсутствие полного четырёхоконного incumbent180 сравнения и один подтверждённый внешний пользовательский repository. Component training честно назван research workflow, CLI train — incumbent-only.

## Границы заключения

Этот документ подтверждает согласованность прочитанных инструкций с текущими файлами и перечисленными исполненными проверками. Он не заменяет новый release acceptance при изменении runtime/dependencies и не является внешней сертификацией моделей. Remote HEAD и полнота LFS-публикации должны быть проверены root отдельно; статус публикации в `PROJECT_STATUS.md` должен следовать фактическому результату.
