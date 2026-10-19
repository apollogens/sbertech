# Проверка до и после исправлений

Начальная ревизия без Git commits сохранена pre_audit_snapshot.zip + initial_manifest.json. Implementation diff — changes.diff; пути/hashes — changed_files.json. Исходная main suite68PASS не выявляла новые случаи. После расширения30новыми тестами main98PASS/0FAIL/0SKIP. Результаты не называются улучшением точности: добавлены проверки корректности и fail-fast.

| Воспроизведение | До | После |
|---|---|---|
| Initial10 root regressions | 8FAIL/2PASS | всеPASS |
| CSV body2root cases | 2FAIL/10PASS suite | обаPASS |
| Catalog permutation regression | 1FAIL | 1PASS |
| Independent backend initial | 16PASS/4FAIL | 21PASS/0FAIL |
| Main suite | 68PASS | 98PASS |
| Independent temporal | initial9PASS/1FAIL неверная предпосылка теста | 11PASS, предпосылка заменена измерением |
| All6 frozen real fits | сохранённые веса, заявленное обучение | повторены100.625s,всеSHA exact |
| Current offline output | исходный submission | freshly generated CSV exact equal |
| Full real Docker output | old container_forecast CSV SHA10cd625f…bd8e | final Docker тот жеSHA |

Числа failing до изменений сохранены regressions_before.txt,csv_before.txt,catalog_before.txt и reviewer_backend.md. После каждого fixes воспроизведения повторены, затем затронутые модули, integration и полный feasible regression. Независимые A/B/C signoffs получены. Ни один failing production test не исключён ради итогового verdict.

Затронуты src/data.py (strict validation),src/predict.py (bundle guards),src/submission.py (shape guard),app/validators.py (CSV structure/range). Новые tests:test_qa_regressions.py и4HTTP regressions; QA diagnostics/scripts/docs/dev dependencies. Архитектура, objective,features,threshold,weights и serialized artifacts не изменены; retraining для fixes не требовался, но отдельно выполнено воспроизведение сохранённых6fits. Существующие лучшие artifacts не заменены.

Holdout до/после:SMAPE158.6871617213434%,WAPE80.43006567684449%,RMSE0.8662841487164723,Bias80.5655572662628%,RMSLE0.3126153218811934. Их Δ=0. Mean signed−62.834934485864856%,global signed volume−19.105414359749904%,Δ=0. QA не повысил прогнозную точность и не выдаёт снижение ошибок валидации за прирост моделей.

Для легального реального ввода свежий CSV maxdiff0 относительно исходного submission. Retrained raw final prediction против10-digit CSV maxdiff4.9918806865889565e-09 — только запись; full API17-digit сравнение3.55e-15. Latency before/after не является контролируемым benchmark из-за разных запусков/окружений, ускорение не заявляется. Новая полная проверка CSV добавляет проход; фактический Docker33.77s значительно ниже лимита.

Минимальное исправление CSV оправдано реальным воспроизведением. [Документация pandas.read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html) описывает bad lines прежде всего как строки с избытком полей, поэтому одного on_bad_lines недостаточно для усечённых записей. Использован strict csv.reader с проверкой ширины всего тела; положительные fixtures сохраняют законный quoted multiline/explicit empty CSV.

Исследовательский вывод: minmax/rank sensitivity и sparse underforecast требуют нового заранее фиксированного validation protocol, а не подбора по уже открытому holdout. Новых моделей или гиперпараметров не продвигалось; это сохраняет проверенный baseline и честный статус holdout.
