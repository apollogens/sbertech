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

## Дополнение: завершённая проверка GitHub checkout

Позднее в той же сессии проверены обновления `PROJECT_STATUS.md`, execution log и master prompt, helper `consolidation/verify_github_checkout.py` и фактический receipt `consolidation/github_publication_verification.json`. **PASS.** Описанный в предыдущем разделе незавершённый статус публикации относится к первоначальному этапу review; первая runtime-публикация теперь состоялась. Этот абзац проверяет commit `cc8a707110ac6a14d49bb5aa595595ca45ee052e`; последующее документальное обновление должно быть опубликовано и сверено root отдельно.

Независимо, без повторения inference/tests, прочитаны реальные файлы из указанного receipt временного свежего clone. Его HEAD совпал с verified commit; все 20 файлов src/app совпали с текущими исходниками. Скачанный frozen release ZIP повторно захеширован: SHA-256 `d2306a62b61e7817ccaaa7c2036e4d6019995df72e7a737dc16b73f3a7466803`. Реальный журнал fresh-clone тестов содержит `222 passed, 1 warning in 45.02s`.

Повторно захешированы оба полученных CLI CSV и оба исходных приватных CSV. Для каждого прогноза проверены 562496 строк, точное равенство своему LF-нормализованному reference и согласие всех hashes с receipt:

| Прогноз | SHA-256 результата и нормализованного reference |
|---|---|
| nonton-v1 | `ec1423820e9d13689f38b5d9dd2d82b2eb067f7e06fe123fecab9898991d98c3` |
| equal4:P1 | `2d03b46160c62d33f540259b5f4aba94a932e752c10a48ad8efeb77b9bf159a9` |

SHA-256 sales — `925fa8b15ca668b0213e038a5250e289c2d6e76b4f821fe33cf875e3abd23b2a`, stock — `2570c8121ecfadeaa72d98000c4c94ed6745ab4b04e3ae337053efe1f5fddf49`. Helper только скачивает remote/LFS и локально читает приватные CSV; публикации этих входных CSV он не выполняет.

Текст правильно ограничивает результаты: использован существующий dev interpreter; LFS скачан выборочно; полной повторной загрузки научного корпуса, новой clean install или нового Docker acceptance не было. Уточнение о сохранении исторических NPZ/панелей внутри архивов не выдаёт Git-игнорирование рабочих input/cache путей за очистку прежних архивов. Новый пример обучения `bundles/incumbent-next` явно является будущим output и не вложен в active bundle directories. Существенных противоречий в этих изменениях не выявлено.
