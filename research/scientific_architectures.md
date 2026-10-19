# Научные архитектуры: проверенные механизмы и перенос в Nonton

Дата проверки: 19 октября 2026. Это исследовательский обзор и выборочное чтение исходников, а не воспроизведение опубликованных экспериментов. Ни одного обучения или изменения production этой ролью не выполнено. Точные снимки кода, commit, URL и SHA-256 находятся в [manifest.json](source_inspection/manifest.json); реестр библиографии — [science_sources.csv](science_sources.csv).

## 1. Что уже известно локально

Прочитаны `reports/remediation/final_technical_report_ru.md` и `method_evidence.md`. Старый отчёт фиксирует 5 078 нулевых прогнозов среди 7 752 eligible серий, 407 940 положительных дневных оценок, удаляемых порогом, и конфликт метрик при снятии порога. Эти числа этой ролью заново не вычислялись. Официальный ADIDA, SBA, TSB и binary×Gamma уже исследовались. Следовательно, повторный плоский ADIDA не является новой архитектурой. Новизна предлагаемого PoC — обучаемые будущие недельные суммы и отдельное распределение по дням.

Все рекомендации относятся к observed `quantity`, 8 789 комбинациям, 64 дням и 562 496 выходным строкам. Большая панель не создаёт длинную независимую временную историю. Проверять пять официальных метрик и оба варианта SMAPE; уже открытый terminal нельзя объявлять новым независимым тестом.

Дополнительная проверка robustness: Shaohui Ma, Robert Fildes (2022), *The performance of the global bottom-up approach in the M5 accuracy competition: A robustness check*, IJF 38(4):1492–1499, [DOI](https://doi.org/10.1016/j.ijforecast.2021.09.002). [Lancaster](https://eprints.lancs.ac.uk/id/eprint/159736/) подтверждает библиографию и вывод в abstract о необходимости нескольких rolling periods. Повторное использование прежних окон Nonton допустимо для ретроспективного сравнения, но не создаёт untouched test. Подробный дополнительный review — [scientific_review.md](scientific_review.md).

## 2. Темпоральная агрегация и reconciliation

**Библиография.** George Athanasopoulos, Rob J. Hyndman, Nikolaos Kourentzes, Fotios Petropoulos (2017), *Forecasting with temporal hierarchies*, European Journal of Operational Research 262(1):60–74, [DOI](https://doi.org/10.1016/j.ejor.2017.02.046). Авторская запись связывает статью с R-пакетом `thief`. Открыт полный авторский PDF; выборочно прочитаны постановка и обсуждение агрегации, полного численного воспроизведения нет. [Авторская запись](https://fpp.robjhyndman.com/publications/temporal-hierarchies/), [PDF](https://robjhyndman.com/papers/temporalhierarchies.pdf).

Механизм: непересекающиеся суммы на нескольких частотах, отдельные base forecasts и их согласование. Агрегация подавляет быстрые колебания, но сокращает число наблюдений и может скрывать дневную сезонность. Это основание проверить другое представление; гарантии улучшения Nonton нет.

**Наша адаптация.** Для каждого origin задать ровно девять 7-дневных блоков и один 1-дневный остаток. Обучать ожидаемую сумму `V[i,b]` наблюдаемого quantity; восстановить `p[i,t]=V[i,b]*w[i,t]`, где веса неотрицательны и сумма по реальным дням блока равна единице. Веса оценивать только по истории origin: сглаженный профиль дня недели с pooling по складу/категории и заранее заданным fallback. Для остатка вес равен 1; нельзя без объяснения делить его на 7. Если используются календарные недели, возможны две неполные границы: это другая явно фиксируемая схема. Совпадение сумм — проверяемый инвариант, а не метрика качества. Это самостоятельная адаптация идеи, не точная реплика статьи.

## 3. ADIDA и intermittent demand

Konstantinos Nikolopoulos, Aris A. Syntetos, John E. Boylan, Fotios Petropoulos, Vassilios Assimakopoulos (2011), *An aggregate-disaggregate intermittent demand approach (ADIDA) to forecasting: an empirical proposition and analysis*, JORS 62(3):544–554, [DOI](https://doi.org/10.1057/jors.2010.32). DOI и год подтверждены [университетской записью](https://research.bangor.ac.uk/en/publications/an-aggregate-disaggregate-intermittent-demand-approach-adida-to-f/). Полный текст статьи здесь не прочитан; детали существующего StatsForecast ADIDA описаны в старом `method_evidence.md`, не заявлены как новая проверка исходника.

Агрегировать редкий сигнал, прогнозировать на укрупнённой шкале и дезагрегировать — правдоподобное уменьшение разреженности. Оно одновременно теряет момент продажи. Ключевой эксперимент — сравнить обучаемый block-volume с прежним ADIDA и daily LightGBM на одинаковых ключах. Нельзя объявить снижение числа нулевых прогнозов выигрышем без Bias, WAPE, SMAPE, RMSE и RMSLE. Условное среднее может давать мелкие положительные прогнозы на многих нулевых днях, ухудшая SMAPE.

## 4. Cross-sectional reconciliation и MinT

Shanika L. Wickramasuriya, George Athanasopoulos, Rob J. Hyndman (2019), *Optimal forecast reconciliation for hierarchical and grouped time series through trace minimization*, JASA 114(526):804–819, [DOI](https://doi.org/10.1080/01621459.2018.1448825). [Авторская запись](https://robjhyndman.com/publications/mint/) подтверждает цель минимизации суммарной среднеквадратической ошибки при несмещённых base forecasts. Это не минимизация официального Bias или SMAPE Nonton.

Пусть `b` — bottom-series, `S` — суммирующая матрица и `y=S b`. Для невырожденных матриц линейный MinT имеет вид `y_rec=S(S'W^-1 S)^-1 S'W^-1 y_hat`. `W` относится к ошибкам базового прогноза, а не к ковариации самих продаж. Текущий исходник библиотеки использует эквивалентную вычислительную форму через линейное решение; не следует копировать формулу с пропущенным обратным `W`.

Выборочно прочитан официальный [methods.py](https://github.com/Nixtla/hierarchicalforecast/blob/56cc4fac0c5c7b4ff33884d4a8a929f3cd8f03ec/hierarchicalforecast/methods.py):

| Метод | Реализация и допущение | Осмысленный Nonton PoC |
|---|---|---|
| BottomUp | `S` умножается на bottom forecasts; дополнительных верхних сигналов нет | Контроль арифметики и согласованности |
| TopDown | Исторические/прогнозные пропорции; проверяется strict hierarchy | Только дерево total→warehouse→article; пересечение warehouse и article не является деревом |
| MinTrace `ols`/`wls_struct` | Без оценки полной эмпирической ковариации | Небольшие независимые деревья, сравнение с BottomUp |
| `wls_var`/`mint_cov`/`mint_shrink` | Требуются insample actual и fitted forecasts; shrinkage стабилизирует covariance | Только после получения законных residuals; никакого fit по будущему holdout |
| ERM | Обучаемая reconciliation-матрица, возможна регуляризация | Отложить: ещё одна стадия настройки при короткой истории |

В коде MinTrace по умолчанию `nonnegative=False`. Обычная линейная проекция может дать отрицательные значения; обнуление отдельных уровней нарушает coherence. Неотрицательное constrained reconciliation — отдельная вычислительная задача. Для 8 789 рядов одна плотная float64 матрица содержит 77 246 521 элементов, около 589 MiB без агрегатов, копий и solver workspace. Для всех уровней расход больше; нельзя считать это полным замером RAM. Начинать с warehouse blocks и диагональных весов. Полная совместная product×warehouse covariance не приоритетна.

## 5. Цензурирование продаж: где меняется target

Adam J. Mersereau (2015), *Demand Estimation from Censored Observations with Inventory Record Inaccuracy*, Manufacturing & Service Operations Management 17(3):335–349. **Исходный DOI корректен:** [10.1287/msom.2015.0520](https://pubsonline.informs.org/doi/abs/10.1287/msom.2015.0520?journalCode=msom). Проверены издательская библиография и abstract; полный алгоритм статьи не реконструирован. Статья рассматривает bias оценки скрытого спроса при неточных inventory records. Она не разрешает подменять будущие observed sales оценкой latent demand.

Yangyang Wang, Jiawei Gu, Li Long, Xin Li, Li Shen, Zhouyu Fu, Xiangjun Zhou, Xu Jiang, *FreshRetailNet-50K: A Stockout-Annotated Censored Demand Dataset for Latent Demand Recovery and Forecasting in Fresh Retail*, [arXiv:2505.16319](https://arxiv.org/abs/2505.16319), v1 2025, просмотренная v5 18.06.2026. Подтверждены hourly data, stockout annotations и двухстадийная постановка. Это preprint; журнал не установлен. [Официальный baseline](https://github.com/Dingdong-Inc/frn-50k-baseline).

Исходник baseline раскрывает важное отличие: SSA ожидает фиксированные 90 train + 7 eval дней (`reshape(...,97,3)`), использует discount/precipitation eval-периода и считает средние дневные WAPE/WPE/MAE **после фильтра `stock_hour6_22_cnt==0`**. Recovery entrypoint восстанавливает часы 6:22 внутри 30-дневных блоков и суммирует до суток. Это не проверка всех observed-sales дней на 64-дневном Nonton horizon. Наличие будущих погодных/ценовых данных допустимо только если их доступность на origin доказана; слепой перенос создаст leakage. Погодные данные этой ролью не скачивались.

Практический ограниченный перенос: исторические availability summaries, отдельно от target, с cutoff-time проверкой. Не заявлять истинный объём потерянных продаж по одному дневному остатку. Recovery с hourly masks отвергнуть при отсутствии эквивалентной разметки; внешние проценты улучшения не переносить.

## 6. NHITS: один прямой нейросетевой challenger

Cristian Challu, Kin G. Olivares, Boris N. Oreshkin, Federico Garza Ramirez, Max Mergenthaler Canseco, Artur Dubrawski (2023), *NHITS: Neural Hierarchical Interpolation for Time Series Forecasting*, AAAI 37(6):6989–6997, [DOI](https://doi.org/10.1609/aaai.v37i6.25854). [Издатель](https://ojs.aaai.org/index.php/AAAI/article/view/25854) связывает статью с Nixtla/neuralforecast. Ускорение и точность в статье относятся к её long-horizon benchmark, не LightGBM Nonton.

Прочитан [nhits.py](https://github.com/Nixtla/neuralforecast/blob/6c11accfbcfdd62a40ef69a7c81e3d9c7f272682/neuralforecast/models/nhits.py) и выборочно BaseModel. NHITSBlock выполняет Max/AvgPool по истории и exogenous windows, MLP выдаёт backcast и forecast knots; interpolation восстанавливает h прогнозных значений. Блоки вычитают backcast из residual history и складывают forecast components. Это временная multiscale decomposition, не cross-sectional coherence 8 789 серий. Есть historic/future/static covariates; default loss MAE. MAE на разреженном сигнале тяготеет к условной медиане и не обещает устранения нулей. Никакого механизма stockout recovery здесь нет.

Минимальная гипотеза: общий NHITS `h=64`, `input_size=128`, 3 маленьких stacks, по одному block, hidden 128, только известный календарь, один seed и ≤300 optimizer steps для первого отсева; это предлагаемый бюджет, не выполненный опыт. На первом development origin те же 8 789 рядов предпочтительнее произвольной удобной подвыборки. Если память ограничивает, зафиксировать stratified series subset до просмотра качества, а результат явно назвать subset PoC. Отдельно сравнить полную обучающую историю, фактические fit/inference RAM/time и неизменяемые prediction keys. По первой оценке не проводить большой loss/architecture search.

## 7. TiDE: оригинал и поддерживаемая реализация различаются

Abhimanyu Das, Weihao Kong, Andrew Leach, Shaan Mathur, Rajat Sen, Rose Yu, *Long-term Forecasting with TiDE: Time-series Dense Encoder*, [arXiv:2304.08424](https://arxiv.org/abs/2304.08424), оригинальный [google-research/tide](https://github.com/google-research/google-research/tree/3ef52111c1fabc301880818f5a547570e926a76b/tide). [Google Research](https://research.google/pubs/long-horizon-forecasting-with-tide-time-series-dense-encoder/) указывает TMLR 2023, но заголовок страницы «Long Horizon...» и список авторов на ней отличается: пропущен Shaan Mathur. Для состава авторов принят оригинальный README и arXiv; DOI TMLR не придуман.

Прочитаны оригинальные `models.py`, `train.py`, `data_loader.py` и maintained Nixtla `tide.py`. Оригинал — TensorFlow residual MLP encoder/decoder, time-feature projection, temporal decoder и linear skip из history непосредственно в horizon, MSE training через GradientTape. Scaler fit выполняется на train range. Оригинальный README поддерживает global known-future covariates, предупреждает об отсутствии произвольных static attributes; при этом есть embedding индекса ряда. Оригинальный requirements фиксирует TensorFlow 2.10.1, numpy 1.21.6, pandas 1.3.5. Nixtla TiDE — отдельная PyTorch реализация с historic/future/static covariates и default MAE; она не эквивалентна исходному experiment config по умолчанию.

TiDE отложить за NHITS: добавление второй runtime-family не даёт отдельного доказательства пользы. Если NHITS PoC не помещается в бюджет, оригинальный старый TensorFlow stack не является простым обходом.

## 8. Совместимость и решение по bounded PoC

Проверка `importlib.metadata` в `.venv` сохранена в `source_inspection/local_versions.json`: Python 3.12.10, numpy 2.5.4, pandas 3.0.6; torch, neuralforecast, hierarchicalforecast, StatsForecast, Lightning и TensorFlow в этом окружении не установлены. Это не инвентаризация всех других venv проекта. На проверенном commit pyproject HierarchicalForecast 1.5.3 допускает pandas>=2.1, NeuralForecast 3.3.0 — pandas>=1.3.5 и torch>=2.9.1. Формальное отсутствие upper bound не доказывает runtime compatibility. Установка и import-smoke не выполнены; любые библиотечные challenger требуют отдельного окружения и pin/freeze. Требования FRN numpy1.23.5/pandas1.5.3 и TiDE1.21.6/1.3.5 конфликтуют с production pins.

Приоритет: (1) обучаемый weekly volume + historical weekday allocation; (2) небольшая cross-sectional aggregate/disaggregate модель или blockwise OLS/WLS; (3) один NHITS только после проверки hardware и отдельного окружения. Для каждого — сначала один заранее выбранный development cutoff, явный лимит времени/RAM, затем четыре прежних development окна при наличии полезного сигнала. Цена повторного выбора на тех же окнах раскрывается. Scorer и production threshold не менять. Stockout recovery и full dense MinT не запускать как первые PoC. Исследовательский вывод не является разрешением заменить incumbent: ни один внешний источник не устанавливает превосходство на Nonton.
