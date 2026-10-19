# Инвентаризация внешних решений

Дата: 19 октября 2026. Проверяющий: агент A/C. Production не изменён; чужие setup/train и pickle не запускались.

Уточнение пользователя в ходе работы: подтверждены URL `https://github.com/filipp880/forecast-64-v1.git` и приблизительный Temp-путь. Это соответствует найденному checkout ниже. Второй отдельный URL/путь в уточнении не указан; заключение о неустановленной второй загрузке сохраняется.

**Требуемая пара пользовательских GitHub downloads не установлена.** Обнаружен один релевантный внешний Nonton-проект и два ранее изучавшихся исследовательских клона. Наличие двух клонов M5/Favorita не доказывает, что пользователь имел в виду именно их. Успешная интеграция двух идентифицированных решений не заявляется.

| Статус | Локальный путь | Remote и владелец | HEAD |
|---|---|---|---|
| Релевантный внешний Nonton | `C:/Users/apollo/AppData/Local/Temp/forecast-comparison-7371efa0b4b14184a05e39ed9dc127b8` | [filipp880/forecast-64-v1](https://github.com/filipp880/forecast-64-v1) | `f8a8c6e60edaf12af2fd351e290c35e6875afea0` |
| Ранее исследованный clone; принадлежность требуемой паре не установлена | `D:/SberTech/research/sources/M5-methods` | [Mcompetitions/M5-methods](https://github.com/Mcompetitions/M5-methods) | `18e4e776cfa1ded3b387fabe008c6c2c44922007` |
| Ранее исследованный clone; принадлежность требуемой паре не установлена | `D:/SberTech/research/sources/Favorita-LenzDu` | [LenzDu/Kaggle-Competition-Favorita](https://github.com/LenzDu/Kaggle-Competition-Favorita) | `6c6cf2f7e69ac32ae989cdf348b9bcf272fb78e9` |

Remote и HEAD прочитаны непосредственно через `git remote get-url origin` и `git rev-parse HEAD`. Клоны M5/Favorita уже зафиксированы в `research/competition_solutions.md`, `competition_sources.csv` и `source_snapshot_manifest.json`. Путь rival найден в `reports/comparison_forecast64.md` и заново проверен на диске.

## Область поиска

Проверены hidden `.git/config`, релевантные имена файлов/ZIP и URL в заметках: весь `D:/SberTech` с исключением `.venv`, `.venv_stats`, git objects и binary caches; соседние проектные каталоги `D:/MyProject`, `D:/See`, `D:/FintechPSD`, `D:/LiveProgAuth`, `D:/HTML Basic`, `D:/WebTRAMV`; `C:/Users/apollo/Desktop`, `Downloads`, `Documents`, `OneDrive`, `ThirdParty`; `.git/config` внутри `AppData/Local/Temp` с исключением сред, node_modules и browser/cache directories. Это целевой поиск, не доказательство отсутствия другого репозитория где угодно на компьютере. Каталоги игр/системы и приватная история чатов не сканировались.

В соседних проектах обнаружены unrelated repos AntiDrop, See и WebTRAMV. Их происхождение не подменяет forecasting-source. В Temp найден один relevant forecasting remote — filipp880. Каталоги `C:/Users/apollo/source` и `repos` отсутствуют.

Просмотрены центральные каталоги ZIP без распаковки: `nonton_solution.zip` (62 entries), `nonton_solution_qa_verified.zip` (172), `nonton_solution_remediated_verified.zip` (409) — собственные поставки; `Desktop/выборка/hakaton.zip` (2) — данные, не GitHub-решение. SHA-256 и признаки содержимого записаны в [машинном результате](source_audit/source_fixture_results.json).

## Файлы и исполнимость

У filipp880 точные файлы: `forecast-container/app/models/blend_model.py`, `hurdle_model.py`, `lightgbm_model.py`, `base.py`; вызов — `app/predictor.py`, features — `app/features.py`, обучение — `train.py`, параметры — `model/config.json`. Полный исходный pipeline требует pandas, NumPy, LightGBM, а общий registry импортирует CatBoost при наличии; API использует FastAPI, uvicorn и python-multipart. Диапазоны указаны в `forecast-container/requirements.txt`; новая установка не выполнялась. Проверенные численные методы исполнены через AST с synthetic boosters; это подтверждает механизмы, не новый полный replay внешней модели. Предыдущее full сравнение описано отдельно в `reports/comparison_forecast64.md` и не выдаётся за выполненное сейчас.

M5 A1: ensemble в `Code of Winning Methods/A1/3. code/3. predict/3-1. Final ensemble.py`; шесть 28-дневных CSV совмещаются по `id` и усредняются. Полных весов в доступном A1 нет; чужой pipeline не запускался. Favorita: `Utils.py:make_submission`, `cnn.py`, `seq2seq.py`, `lgbm.py`; README упоминает weighted seed ensembles, но отдельного исполняемого финального combiner в clone нет. Старая Keras/CuDNN и несовместимые API препятствуют воспроизведению без адаптации; `lgbm.py` использует закомментированную `best_rounds`.

Дополнительная идентификация второго конкретного пользовательского проекта требует его пути/URL. Независимая работа с Nonton и явно маркированная реконструкция найденных механизмов возможны без подстановки вымышленного источника.
