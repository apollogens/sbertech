# Научное и официальное обоснование методов

Дата проверки: 18.10.2026. Роль A — независимое исследование источников и чтение кода. Этот документ обосновывает кандидатов, но не подтверждает их превосходство на Nonton. Источники проверены через сайты издателей, авторов, официальную документацию, PyPI и версионные исходники. Закрытый полный текст не считается прочитанным. Исходные данные, код, модели и production dependencies этой ролью не менялись.

## 1. Окружение и реализация

Проектный интерпретатор .venv: Python 3.12.10, NumPy 2.5.4, pandas 3.0.6, LightGBM 4.7.0. Проверено через importlib.metadata. StatsForecast и MLflow при первичном осмотре отсутствовали. Системный python отличается от .venv.

Официальный PyPI JSON сообщает стабильную StatsForecast 2.1.1 от 16.07.2026, Python >=3.10, Windows cp312 wheel доступен. Важное ограничение — pandas<3.0.0: пакет нельзя добавлять поверх production pandas3.0.6 с сохранением объявленного dependency contract. Предпочтительно отдельное экспериментальное окружение и полный pip freeze. Проверка метаданных не является подтверждением успешной установки. [PyPI2.1.1](https://pypi.org/project/statsforecast/2.1.1/), [версионные зависимости](https://raw.githubusercontent.com/Nixtla/statsforecast/v2.1.1/pyproject.toml).

Предлагаемые команды, не выполненные исследовательской ролью:

    python -m venv .venv_stats
    .\.venv_stats\Scripts\python.exe -m pip install "statsforecast==2.1.1"
    .\.venv_stats\Scripts\python.exe -m pip freeze

Прочитан models.py официального cp312-win_amd64 wheel: SHA-256 wheel e02982a9ad2d869450db35f5a531be5785ea89fa31e5be7f7af191540c018fe5; SHA-256 извлечённого models.py 31228c6522ee6c883b471c407a9f680451ed5b88abcc9df68a1a25ac395455aa. Прочитан также исходник v2.1.1. Ранее просмотренная 2.0.3 не предпочтительна: её scipy<1.16.0 дополнительно расходится с requirements.lock проекта.

## 2. Проверенные первичные источники

| ID | Источник и библиография | Точное основание рассмотреть метод | Ограничение |
|---|---|---|---|
| RES-SBA | A. A. Syntetos, J. E. Boylan (2005), The accuracy of intermittent demand estimates, IJF21(2),303–314; DOI10.1016/j.ijforecast.2004.10.001 | Сравнение SMA, SES, Croston и новой поправки на 3000 intermittent рядах автомобильной отрасли. | Иные данные и меры; не доказательство улучшения пяти метрик Nonton. Прочитаны abstract и доступные section snippets издателя. |
| RES-TSB | R. H. Teunter, A. A. Syntetos, M. Z. Babai (2011), Intermittent demand: linking forecasting to inventory obsolescence, EJOR214(3),606–615; DOI10.1016/j.ejor.2011.05.018 | Вероятность возникновения спроса обновляется каждый период, в том числе после наблюдаемого нуля. | Затухание не обещает исправить underforecast. Stockout и исчезновение спроса различны; несмещённость требует допущений статьи. |
| RES-ADIDA | K. Nikolopoulos, A. A. Syntetos, J. E. Boylan, F. Petropoulos, V. Assimakopoulos (2011), An aggregate–disaggregate intermittent demand approach (ADIDA) to forecasting: an empirical proposition and analysis, JORS62(3),544–554; DOI10.1057/jors.2010.32 | Агрегация времени уменьшает число нулей, но теряет информацию. Исследованы 5000 RAF SKU. | Уровень агрегации важен. Полный PDF веб-инструмент не открыл; проверены университетская запись авторов и официальный код. |
| RES-HURDLE | Cindy Xin Feng (2021), A comparison of zero-inflated and hurdle models for modeling zero-inflated count data, Journal of Statistical Distributions and Applications8,8; DOI10.1186/s40488-021-00121-4 | Hurdle и ZI имеют разные генеративные механизмы; выбор требует проверки соответствия данным. | Статья о count data, не forecasting Nonton и не проверка binary+Gamma. Автор один: «Feng et al.» в стартовом списке неточно. |
| RES-GLOBAL | P. Montero-Manso, R. J. Hyndman (2021), Principles and algorithms for forecasting groups of time series: locality and globality, IJF37(4),1632–1653; DOI10.1016/j.ijforecast.2021.03.004 | Глобальное семейство может воспроизводить локальные прогнозы без требования сходства всех рядов; рассмотрены generalization bounds. | Не гарантирует превосходство конкретного ограниченного LightGBM с данными признаками. |
| RES-M5 | S. Makridakis, E. Spiliotis, V. Assimakopoulos (2022), M5 accuracy competition: Results, findings, and conclusions, IJF38(4),1346–1364; DOI10.1016/j.ijforecast.2021.11.013 | Эмпирический прецедент cross-learning в retail forecasting. | M5: 28 дней и RMSSE; Nonton:64 дня и иной scorer. Нельзя переносить uplift. |
| RES-ACCURACY | R. J. Hyndman, A. B. Koehler (2006), Another look at measures of forecast accuracy, IJF22(4),679–688; DOI10.1016/j.ijforecast.2006.03.001 | Распространённые меры могут вырождаться; выбор меры меняет смысл качества. | Поддерживает диагностику, не замену официальных метрик на MASE. |

Первичные ссылки: [SBA — издатель](https://www.sciencedirect.com/science/article/pii/S0169207004000792), [TSB — издатель](https://www.sciencedirect.com/science/article/pii/S0377221711004437), [ADIDA — университет авторов](https://researchportal.bath.ac.uk/en/publications/an-aggregate-disaggregate-intermittent-demand-approach-adida-to-f/), [Feng — издатель](https://link.springer.com/article/10.1186/s40488-021-00121-4), [global — сайт автора](https://robjhyndman.com/publications/global-forecasting/), [M5 — издатель](https://doi.org/10.1016/j.ijforecast.2021.11.013), [accuracy — сайт автора](https://otext.robjhyndman.com/publications/another-look-at-measures-of-forecast-accuracy/).

FPP3 counts.html теперь перенаправляется на practical.html, раздел13.2. Описаны раздельные SES объёма и интервала в Croston, известная смещённость, отсутствие соответствующей вероятностной модели и обычных аналитических prediction intervals. Не следует автоматически приписывать Croston полноценный count likelihood. [Hyndman, Athanasopoulos, FPP3](https://otexts.com/fpp3/practical.html#time-series-of-counts).

## 3. Официальные SBA/TSB/ADIDA и смысл существующего TSB

Подтверждённый исходником API2.1.1:

    import numpy as np
    from statsforecast.models import CrostonSBA, TSB, ADIDA
    models=[CrostonSBA(), TSB(alpha_d=0.05,alpha_p=0.05), ADIDA()]
    forecasts=[m.forecast(y=np.asarray(history,dtype=np.float64),
                         h=64,fitted=False)["mean"] for m in models]

history — доступная к origin история одной пары, включая наблюдаемые нули. Это рекомендованный вызов, не протокол исполненного бенчмарка. [Официальная документация моделей](https://nixtlaverse.nixtla.io/statsforecast/src/core/models.html), [версионный исходник](https://raw.githubusercontent.com/Nixtla/statsforecast/v2.1.1/python/statsforecast/models.py).

В2.1.1 CrostonSBA() НЕ принимает alpha: _croston_classic использует0.1 для двух SES, _croston_sba применяет0.95. Это встроенная SBA-поправка, не подогнанный множитель Nonton. TSB требует явные alpha_d/alpha_p;0.05 сопоставимо с текущим baseline, но не универсально оптимально. _tsb повторяет последнее произведение двух оценок на весь горизонт. ADIDA использует round(mean observed intervals), затем прогноз агрегата делит на уровень агрегации равными весами. fitted=False исключает ненужные fitted values. Наличие X в общей сигнатуре не доказывает использование регрессоров этими тремя моделями. Требуются edge checks: all-zero, короткий ряд, единственное положительное наблюдение, finite/nonnegative output, порядок колонок.

Первоначальный src/baselines.py: y[:origin+1], последние180 дней; p инициализирован частотой положительных в первых28 днях, size — их средним; далее p обновляется каждый день, size только при y>0, обе alpha=.05. Результат p*size повторён64 раза.

Это содержательно TSB. Ошибка «не затухает на будущих днях» не установлена: будущие нули ещё не наблюдались. Подстановка64 искусственных нулей изменила бы постановку. TSB затухает после новых фактических нулей; frozen-state SES forecast остаётся плоским. Окно180 и batch initialization28 отличаются от upstream, поэтому численное равенство не ожидается. Различать прежний TSB180 и официальный TSB.

Обрезка истории, фиксированная alpha, cold start и потеря старых положительных наблюдений — свойства реализации и гипотезы влияния на качество. Их нельзя объявить причиной underforecast без ablation. Нули вследствие stockout нельзя автоматически считать отсутствием скрытого спроса. SBA/TSB/ADIDA вычислимы на дробных неотрицательных величинах, но их теоретические свойства нельзя автоматически переносить после неизвестного преобразования quantity.

SHA-256 проверенного исходного baselines.py:9625e20b128b3e0e97a4d6b82939021221272cc269aef739f3d6631f3105d90d.

## 4. Two-part mean для дробного quantity

Для Y>=0 и конечного E[Y|X] закон полного ожидания даёт:

    E[Y|X] = P(Y>0|X) * E[Y|Y>0,X].

Разложение справедливо для целых и дробных Y; независимость occurrence/magnitude не требуется. При P(Y>0|X)=0 результат0, положительный компонент там не идентифицируется. Это математический вывод роли A, а не экспериментальный результат Feng или Nonton.

Версионно доступный кандидат: LightGBM4.7 binary на I(Y>0), gamma только на Y>0, прогноз probability*positive_mean без hard threshold. Gamma с log-link применима как модель положительной непрерывной величины. Это two-part mean; не следует называть его воспроизведением count-hurdle likelihood статьи Feng. При отсутствии класса или положительных train examples нужны явные guards; оценивать качество fallback отдельно.

Документация предупреждает: is_unbalance и scale_pos_weight ухудшают individual probability estimates. Для p*m использовать обычный binary loss либо заранее определённую калибровку на отдельном хронологическом наборе. raw_score=True возвращает binary margin; обычный predict уже возвращает probability или Gamma response, поэтому дополнительный exp ошибочен. Tweedie — самостоятельный challenger; для zero-plus-positive continuous сценария исследовать1<p<2. Буквальная Poisson count-модель не соответствует дробному target. [Parameters4.7.0](https://lightgbm.readthedocs.io/en/v4.7.0/Parameters.html), [официальные objectives](https://raw.githubusercontent.com/microsoft/LightGBM/v4.7.0/src/objective/regression_objective.hpp).

p*m оценивает условное среднее, но SMAPE и per-series Bias оптимизируют иные функционалы. Высокий AUC не доказывает forecasting uplift. Binary и Gamma должны обучаться на согласованных origin/horizon features. Регрессия log1p с expm1 не гарантирует среднее исходного масштаба; произвольная поправка недопустима.

## 5. Global forecasting и временная проверка

Сохранить global LightGBM как сильного кандидата. Выразительность глобального семейства в статье Montero-Manso/Hyndman не означает, что любые fixed features и31-leaf model способны восстановить произвольные локальные алгоритмы. M5 служит контекстом, не обещанием лидерства.

Руководство LightGBM связывает num_leaves, min_data_in_leaf и max_depth с переобучением. Текущие31/120/lambda_l2=3 не являются дефектом сами по себе; изменение — эксперимент. Число строк глобальной панели не равно числу независимых периодов. deterministic=True и num_threads помогают внутри окружения, не гарантируют побитовую переносимость между версиями и платформами. [Tuning4.7.0](https://lightgbm.readthedocs.io/en/v4.7.0/Parameters-Tuning.html).

MLForecast CV отделяет cutoff от будущего horizon. Все preprocessing fits и snapshots должны использовать только доступные train observations. План root: origins2025-09-14,2025-11-17,2026-01-20,2026-03-25 — development;2026-05-28 — уже открытый terminal diagnostic. Это план, не подтверждение выполненных folds. Последнее окно нельзя называть untouched после прежнего model selection.31 NPZ не равны31 независимому origin. [MLForecast CV](https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/cross_validation.html), [scikit-learn leakage](https://scikit-learn.org/stable/common_pitfalls.html).

Фиксировать список кандидатов до terminal просмотра; выводить все5 raw metrics на каждом64-дневном окне и дни1–14/36–64. Четыре origins дают ограниченную оценку устойчивости; bootstrap по сериям не создаёт независимые временные режимы.

## 6. Исполненные синтетические проверки scorer

Это фактические численные compatibility cases, не улучшения на исторических данных Nonton.

| Вход | Результат | Следствие |
|---|---|---|
| truth=[0,1],pred=[0,0] | official SMAPE200.0%, prose diagnostic100.0% | Zero/zero exclusion существенно меняет показатель. |
| truth=[0,1],pred=[0,0] | absolute Bias100.0% | Нулевой прогноз объёма даёт100%. |
| truth=[1],pred=[2] | absolute Bias100.0% | Удвоение тоже даёт100%; median absolute Bias100 не доказывает zero forecasts. |
| Равные пять метрик A/B | rankA=0,rankB=1 по всем пяти | Ordinal ranking без average ties; порядок имеет значение. |

Воспроизводимая PowerShell-команда:

    @'
    import numpy as np
    from scripts.official_score import smape_series,bias_abs_series,normalize_rank
    from src.metrics import smape_include_zero_zero
    y=np.array([0.,1.]);p=np.zeros(2)
    print(smape_series(y,p),smape_include_zero_zero(y[:,None],p[:,None]))
    print(bias_abs_series(y,p),bias_abs_series(np.array([1.]),np.array([2.])))
    m=dict.fromkeys(["smape","wape","rmse","bias","rmsle"],1.)
    print(normalize_rank({"A":m,"B":m}))
    '@ | .\.venv\Scripts\python.exe -

SHA-256 scripts/official_score.py:5c83fb1dd256a9636bd27cb7aa9eb978dbe6c76a60f74486ca773523139e1ee2. Внешние статьи не разрешают изменять scorer. Эти примеры не решают конфликт спецификации/evaluator. Сохранять обе SMAPE-формулы, документировать rank ties и уточнять фактический режим организаторов.

## 7. MLflow и целостность артефактов

MLflow signature описывает model inputs/outputs и параметры. В документированных PyFunc/serving paths проверяет схему; extra fields могут игнорироваться, разрешены безопасные преобразования типов. Это не strict hash binding всех файлов, не доказательство provenance ordered catalogs/model weights. [MLflow Model Signatures](https://mlflow.org/docs/latest/ml/model/signatures/).

Локальный manifest без установки сервиса допустим: schema version, ordered feature names/dtypes, ordered category mappings, preprocessing/inference config, SHA-256 файлов, dependency versions, run ID. Проверять до predict и отклонять несовпадения. Manifest, созданный сегодня для старой модели, подтверждает сегодняшнюю упаковку, но не восстанавливает исходный training catalog. Это проектная рекомендация по заданию, не автоматически выполняемая гарантия MLflow. Hash относительно доверенного manifest проверяет целостность; не цифровая подпись, не защита от одновременной злонамеренной замены manifest.

## 8. Решения для root

1. Сохранить release model и submission; сначала воспроизвести baseline и диагностировать причины. Научная роль не проверяла исходный holdout.
2. Бенчмарк: официальные SBA/TSB(.05,.05)/ADIDA2.1.1 в изоляции, прежний TSB180, zero, mean28/90, seasonal56. Различать initialization/window и алгоритм.
3. Binary+Gamma — HYPOTHESIS для дробного неотрицательного target, без threshold и некалиброванного class balancing.
4. Продвижение только по сравнимым пяти метрикам законных окон, resource measurements и независимому review.
5. Ни одна публикация здесь не является LOCALLY VERIFIED IMPROVEMENT Nonton.

research_evidence.csv — реестр исследовательской роли. При объединении с evidence_register.csv сохранить категории и отсутствие local uplift. Независимый reviewer signoff не получен.
