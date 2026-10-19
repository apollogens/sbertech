# Состояние Nonton

Актуализация: 20 октября 2026. Этот файл отражает текущую работу; frozen release evidence хранится отдельно.

## Постоянные факты

Активен `nonton-v1`: `config/runtime.json` → `../model`. `equal4:P1` и corrected D/W/S/A доступны через `bundles/equal4-rc1` и общий `src.runtime` / CLI / API. Три Booster используются совместно. Веса, порог .25 и прогнозная логика в продолжении работы не меняются.

Рабочие инструкции: [AGENTS.md](../AGENTS.md), [master prompt](CODEX_PROJECT_MASTER_PROMPT.md), [resume prompt](CODEX_RESUME_PROMPT.md). Канонические source/data/artifact ограничения описаны там; текущий прогресс ниже не является вечным регламентом.

## Инвентаризация задач

| Статус | Область | Подтверждение / следующий шаг |
|---|---|---|
| COMPLETED AND VERIFIED | Консолидация runtime/CLI/API, dependency split, оба Docker, 180-day backtest, rollback и frozen ZIP | `consolidation/final_release_report_ru.md`, raw JSON и независимые review |
| COMPLETED AND VERIFIED | Восстановление синтаксиса `tests/test_api.py` | Удалён ровно один начальный пробел; файл снова побайтово совпадает с frozen ZIP |
| COMPLETED AND VERIFIED | Повторная общая проверка текущего дерева | 238 passed, 48.92 с; `consolidation/continuation_tests.log`; pip check, Ruff и deptry также прошли |
| COMPLETED AND VERIFIED | Четыре постоянных файла инструкций | Independent consistency review PASS: `docs/continuation_instructions_review_ru.md`; все 10 CLI help-команд исполнены, ссылки и факты проверены |
| IN PROGRESS | Публикация `https://github.com/apollogens/sbertech` | `origin` и LFS настроены; staging начат, commit/push ещё не подтверждены |
| OBSOLETE | Старое утверждение, что ensemble не прошёл общий API/Docker | Исторический `integration/final_decision_ru.md` предшествует завершённой consolidation; веса и научные ограничения остаются релевантны |
| NOT STARTED | Новое обучение/новый untouched test | Не являются задачей продолжения; новых labels нет |
| BLOCKED | Полное четырёхоконное incumbent180 сравнение сохранённых весов | Однозначно привязанные incumbent TXT доступны лишь для двух origins; финальные веса не подставлять в прошлое |

## Проверенная ранее поставка

- `consolidation/nonton_consolidated_verified.zip`: 136818696 байт, 237 members, SHA-256 `d2306a62b61e7817ccaaa7c2036e4d6019995df72e7a737dc16b73f3a7466803`.
- `release_manifest.json`: 236 файлов; `release_package.json`, `package_validation.json`, `independent_package_review.json` — взаимосвязанные receipts. Все пути этих receipts находятся в `consolidation/`.
- Предыдущий полный scope: 238 passed; извлечённый package scope: 222 passed. Это разные области, числа не суммируются. В начале продолжения свежий запуск остановился на IndentationError в test_api; после исправления текущий полный scope снова дал 238 passed за 48.92 с, с одним прежним предупреждением Starlette/httpx.
- Четыре raw компонента и пять P1 стратегий воспроизведены точно; численные различия Docker/offline <=1.07×10⁻¹⁴. CSV CLI использует LF вместо прежних CRLF.
- Оба финальных Docker прошли network none, 4 CPU/6 GiB, repeat/error/cache/filter/JSON/restart. Исторические измерения POST: incumbent 11.306 с, equal4 21.868 с; cgroup peaks 1325481984 / 4691660800 байт. Startup load в POST не входит. Это ранее выполненная приёмка, не измерение этой сессии.
- Clean runtime/dev установки и pip check ранее прошли; версии численных библиотек сохранены. В текущем продолжении зависимости не удаляются и не обновляются.

## Ограничения и сохранность

Equal4 даёт небольшой выигрыш против corrected D на пяти средних метриках четырёх повторно используемых development origins при 180-дневном входе. Нового untouched test нет; terminal остаётся diagnostic. Полного аналогичного сравнения incumbent на четырёх origins нет. Serving использует всю переданную историю >=180 дней; прежнее обучение моделей не превращается в rolling-180 training.

В Git будут исключены приватные sales/stock, окружения, cache, сторонние clones и generated extraction copies. LFS обязателен для крупных model/evidence/archive объектов. Fresh clone без приватных данных не может самостоятельно повторить historical backtest/Docker upload probe; данные нужно предоставить отдельно. Тесты основного runtime не требуют исходных training CSV после получения LFS fixtures.

Новая Git-публикация добавляет инструкции и Git metadata к рабочему дереву после frozen release. Старый ZIP и его manifest не переписываются ради совпадения с новой `.gitignore`/документацией. Rollback snapshot и прежние ZIP/NPZ/веса сохраняются.

## Ближайшее действие

Проверки текущего дерева и инструкций завершены. Preflight staged files не нашёл high-confidence token/private-key patterns, приватных input paths или oversized обычных Git blobs; 20 runtime/API sources совпали с frozen ZIP побайтово. Осталось создать первый commit в `main`, выполнить авторизованный push и сверить remote HEAD/LFS. До такой сверки публикация не считается завершённой. Выполненные шаги и изменения — [журнал продолжения](continuation_execution_log.md).
