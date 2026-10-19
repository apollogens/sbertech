# Итог ремедиации Nonton

**PASS в проверенном инженерном объёме.** Выпуск сохраняет прежнее качество прогнозирования и устраняет подтверждённые проблемы целостности артефактов, диагностируемости/изоляции кэша и CLI. Новые методы реально исследованы и испытаны. Небольшой средний development-выигрыш challenger признан; он не вошёл в serving по раскрытому tradeoff. Победа на leaderboard, высокая бизнес-точность и финансовый эффект не заявляются.

Дата завершения проверок: 18.10.2026, Москва. Корневой агент — PRINCIPAL ML REMEDIATION ARCHITECT; independent reviewer E подписал конкретный model/image/source комплект (`independent_verification.md`). Git HEAD отсутствует; контроль revision выполнен immutable snapshot и SHA-256, а не придуманным коммитом.

| Gate | Итог | Исполненные доказательства |
|---|---|---|
| A — baseline | PASS | Исходный snapshot: 119 тестов, 11 групп временного аудита, 31 OOF на трёх origins, исходные sales и официальные функции метрик |
| B — diagnosis | PASS | Диагностика всех серий, частоты, объёма, остатков и сегментов; 5 078 eligible нулевых прогнозов; ablation порога и горизонты |
| C — sources | PASS | Первичные источники и официальные реализации; научные принципы и локальные результаты разделены в evidence_register.csv |
| D — comparison | PASS | 17 кандидатов × 5 реальных 64-дневных окон = 85; независимый пересчёт; четыре development-окна и открытый terminal; явное дополнение L2 |
| E — engineering | PASS | Новый журнал обучения и строгий manifest, отказоустойчивый кэш, реальные CLI; 177 тестов, без ошибок и пропусков |
| F — end-to-end | PASS | Полный grid 11 × 799 × 64; API/offline/submission parity; настоящий Docker с --network none, 6 GiB и 4 CPU |
| G — independent review | PASS | Reviewer E независимо проверил baseline, 85 прогнозов, файлы модели и image, полноразмерные выходы и финальные тесты |

## Принятый комплект

- Модель: `nonton-v1`, Tweedie 1.3, 220 деревьев, 45 признаков, threshold 0.25.
- Training run: `final-20261018T181325Z-cdd29774bb1b`; 1 476 552 строки, cutoff 2026-07-31; обучение заняло 22.886230 с.
- Bundle ID: `9267e65f0ca9e62b636d185fe7731a71b4e24a8b5110fa830701d5beb0d0f50a`.
- Веса SHA-256: `ebc9bafee00b294793f0ef2b01e9b8d1b42825bc461dc7fa4cdb603496fb3b52`; новые weights/config/catalog побитово совпали с сохранёнными исходными. Manifest и training record новые и относятся к реально выполненному refit.
- Docker image: `sha256:5bb1ea1fea5a136cfc54c2a80701baefd1f97d23a50e17d9b1a42b476913faef`; 148796116 байт. Сборка заняла 1.736594 с и использовала кэш слоёв; это не замер холодной сборки.
- Submission: 562 496 строк, 2026-08-01–2026-10-03, полный grid 11 × 799 × 64; исходный файл сохранён. Локальная поставка: `nonton_solution_remediated_verified.zip`; состав и SHA-256 — `delivery_manifest.json`.

## Числа до и после

На 2026-05-29–2026-07-31 (7 752 eligible Bias-серии) выпущенный refit имеет **те же** SMAPE 158.687161721%, WAPE 80.430065677%, RMSE 0.866284149, Bias 80.565557266%, RMSLE 0.312615322. Разница каждой метрики релиза равна нулю; Bias изменился на 0 п.п. и 0% относительно исходного. Основания: побитово одинаковые weights/config/catalog, неизменённый численный pipeline и независимая end-to-end проверка (`before_after_metrics.csv`).

Исследовательский binary×Gamma с прежним threshold 0.25 улучшил средние всех пяти метрик на четырёх development-окнах. Bias: 83.043671736 → 82.878383391%, разница -0.165288346 п.п. (-0.199038% относительно incumbent). Однако Bias хуже в трёх отдельных окнах из четырёх; значимость среднего выигрыша не установлена. Средний inference — 6.269053 с против 2.967773 с; требуются два Booster вместо одного. Полное основание консервативного выбора — `final_model_decision.md`. Открытый terminal не использован как скрытое veto выбора.

## Полноразмерный runtime

| Проверка | Фактический результат |
|---|---:|
| Локальный HTTP POST | 35.683457с |
| Замещающий HTTP POST | 36.102847с |
| Concurrent POST / invalid upload | 409 / 400 |
| GET во время replacement / failed POST | Старая целая версия / сохранена версия2 |
| API/offline max abs | 0 |
| Server process-tree peak RSS | 3278405632байт |
| Docker HTTP POST | 34.208721с |
| Docker cgroup memory peak | 3939459072байт |
| Docker/offline max abs | 3.5527136788e-15 |

Windows RSS — сумма процесса запуска и дочерних процессов с опросом каждые 50 мс; общие страницы могут учитываться дважды. Cgroup — другой показатель, включающий память и кэш контейнера. Первая оценка около 4 МБ измеряла только launcher и признана недействительной. Оба JSON сохранены; приняты исправленные результаты. Память каждого fit отдельно не измерялась: в learned experiments сохранён накопительный максимум RSS процесса, который нельзя выдавать за память каждого алгоритма.

Первый внешний запуск PowerShell с перенаправлением `2>&1` получил NativeCommandError на обычном сообщении BuildKit, хотя вложенные build, HTTP и parity завершились успешно. Повтор того же Docker-script с раздельными stdout/stderr завершился с exit code 0 (`docker_command_status.json`). Это ошибка захвата вывода оболочкой; сырой первый лог сохранён. В таблице приведён последний успешный прогон, первый benchmark сохранён отдельно.

## Что остаётся неизвестным или ограниченным

1. Историческая хронология tuning не доказана Git-history; terminal уже открыт. Пять rolling-origin окон не являются пятью независимыми статистическими репликациями, нового untouched test нет.
2. ТЗ и executable SMAPE расходятся на (0,0): 47.089556121% против 158.687161721% на исходном holdout. Исполняемый scorer сохранён; текстовый diagnostic хранится отдельно. Обработка одинаковых рангов и неоднозначность minmax/rank требуют разъяснения организаторов; они не устранены нашим выбором.
3. Высокие WAPE/Bias и ошибка sparse сохраняются. Истинный неограниченный спрос и причинное влияние stockout не восстановлены. Анонимизированной quantity не приписано физическое count-distribution.
4. Поддерживается один процесс/worker и один экземпляр. После restart кэш пуст. Distributed cache, несколько контейнеров и скрытые custom worker launchers не поддерживаются.
5. Проверена точная опубликованная CLI matrix, а не все возможные повреждения любого входа. Неизменённый official scorer сохраняет warnings-only validator и собственное поведение ошибок. Подробности `cli_test_report.md`.
6. Ресурсы измерены на этой машине/запусках. Полная отдельная peak memory каждого fit, холодная сборка, будущие данные, финансовый эффект и место leaderboard не измерены.

Открытых подтверждённых release-blocking P0/P1 в проверенном объёме не найдено. Эти ограничения остаются частью приёмки; PASS инженерной поставке не означает доказанную высокую точность продаж.

## Воспроизведение

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests reports/qa/check_backend_independent.py -q
.\.venv\Scripts\python.exe -X utf8 scripts/remediation_diagnose.py
.\.venv\Scripts\python.exe -X utf8 scripts/remediation_experiments.py
.\.venv\Scripts\python.exe -X utf8 scripts/remediation_l2.py
.\.venv_stats\Scripts\python.exe -X utf8 scripts/remediation_statistical.py
.\.venv\Scripts\python.exe -X utf8 scripts/remediation_compare.py
.\.venv\Scripts\python.exe -X utf8 scripts/remediation_report.py
.\.venv\Scripts\python.exe -X utf8 scripts/remediation_backend_probe.py --model-dir model
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remediation_docker.ps1
```

Исходные пользовательские CSV нужны локально; в архив поставки они не входят. Production lock — `requirements.lock`; benchmark lock — `reports/remediation/statsforecast_requirements.lock`. Прежние QA-скрипты пишут исторические отчёты: их воспроизводят в snapshot-копии. Новые скрипты не меняют исходные CSV. Утверждения с источниками, числами и проверкой — `evidence_register.csv`; материал презентации — `presentation_evidence_ru.md`.
