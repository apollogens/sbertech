"""Create final Russian audit decision from reproducible numerical outputs."""
from pathlib import Path
import json
import hashlib
import pandas as pd
import numpy as np
OUT=Path(__file__).resolve().parent
FOCUS=['incumbent','weekly_allocation_z0.25','weekly_direct_shape_z0.25','article_topdown_z0.25']
KEYS=['smape','wape','rmse','bias','rmsle']
def table(frame):
    def fmt(x):return f'{x:.9f}' if isinstance(x,(float,np.floating)) else str(x)
    return '\n'.join(['| '+' | '.join(map(str,frame.columns))+' |','|'+'|'.join(['---']*len(frame.columns))+'|']+['| '+' | '.join(fmt(x) for x in row)+' |' for row in frame.itertuples(index=False,name=None)])
def write(name,text):(OUT/name).write_text(text,encoding='utf-8')
def run():
    x=pd.read_csv(OUT/'per_fold_candidate_metrics.csv');rank=pd.read_csv(OUT/'weighted_rank_sensitivity.csv');norm=pd.read_csv(OUT/'minmax_sensitivity.csv')
    rs=pd.read_csv(OUT/'development_rank_summary.csv');ns=pd.read_csv(OUT/'development_minmax_summary.csv')
    selected=rs[(rs.pool=='union23')&(rs.order=='forward')&(rs.smape_definition=='executable')&(rs.tie_policy=='official_argsort')]
    f=selected[selected.model.isin(FOCUS)][['model','score','delta_vs_incumbent','wins']].rename(columns={'score':'rank_mean','delta_vs_incumbent':'rank_delta','wins':'rank_wins'})
    mm=ns[(ns.smape_definition=='executable')&(ns.baseline=='last')&ns.model.isin(FOCUS)][['model','score','delta_vs_incumbent','wins']].rename(columns={'score':'minmax_mean','delta_vs_incumbent':'minmax_delta','wins':'minmax_wins'})
    comp=f.merge(mm,on='model');comp.to_csv(OUT/'focus_objective_comparison.csv',index=False)
    perrank=rank[(rank.pool=='union23')&(rank.order=='forward')&(rank.smape_definition=='executable')&(rank.tie_policy=='official_argsort')&(rank.role=='development')&rank.model.isin(FOCUS)][['origin','model','score','delta_vs_incumbent']]
    perrank.to_csv(OUT/'focus_per_fold_rank.csv',index=False)
    # Quantify scenario sensitivity, preserving exact order/tie definitions.
    filtered=rs[rs.smape_definition=='executable']
    sensitivity=filtered[filtered.model.isin(FOCUS)].groupby('model').agg(min_mean_delta=('delta_vs_incumbent','min'),max_mean_delta=('delta_vs_incumbent','max'),scenarios=('score','size'),better_scenarios=('delta_vs_incumbent',lambda z:int((z < -1e-12).sum())))
    sensitivity.to_csv(OUT/'focus_rank_sensitivity_range.csv')
    horizon=pd.read_csv(OUT/'horizon_candidate_metrics.csv');hh=horizon[(horizon.origin!='2026-05-28')&horizon.model.isin(FOCUS)&(horizon.horizon=='36_64')].groupby('model')[KEYS].mean()
    hh=hh.subtract(hh.loc['incumbent']);hh.to_csv(OUT/'focus_long_horizon_deltas.csv')
    pareto=pd.read_csv(OUT/'pareto_frontier.csv');pf=pareto[(pareto.pool=='union23')&(pareto.smape_definition=='executable')&(pareto.role=='development')&pareto.model.isin(FOCUS)][['origin','model','is_frontier','is_frontier_tol1e10','dominated_by']]
    focus_mean=x[(x.role=='development')&x.model.isin(FOCUS)].groupby('model')[KEYS].mean();focus_delta=focus_mean.subtract(focus_mean.loc['incumbent'])
    write('final_recommendation_ru.md','''# Итог независимого аудита оценки и выбора модели

**Прежний критерий замены слишком строг для конкурсной цели: улучшение всех пяти средних метрик не является обязательным условием лучшего weighted score. Текущее исследование не доказало предпочтительность incumbent по фактической цели конкурса.**

Production `nonton-v1` сохраняется как временный инженерный выбор. Локальные численные результаты указывают на разных претендентов при разных допустимых прочтениях правил. Реальная конфигурация leaderboard не установлена, ранний temporal catalog действительно содержит будущие ID, независимого нового периода нет. Поэтому автоматическая замена модели также не обоснована.

Дата оценки: 19.10.2026, Europe/Moscow. Новых обучений: **0**. Старые модели, forecasts, submission, reports и архивы не изменялись. Этот отчёт уточняет вывод прежнего исследования, не переписывая его frozen protocol или исторические отчёты.

## Какова подтверждённая цель

Проверен исходный `C:/Users/apollo/Desktop/выборка/markdown hakaton.md`. Python-блок §9.2 совпадает с `scripts/official_score.py` по тексту и AST. Scorer задаёт веса SMAPE=.50, WAPE=.20, RMSE=.15, Bias=.10, RMSLE=.05. Rank использует ordinal ranks через `np.argsort`, делённые на n−1; равенства не усредняются. Minmax делит на метрики baseline и обрезает значения выше 1. Это не candidate-pool minmax.

Текст §9 ожидает rank; §5.3 и default CLI описывают minmax. Без baseline CLI переключается в rank. Как именно запущен реальный leaderboard, из этих файлов не следует. Executable SMAPE исключает дни (0,0) из среднего внутри ряда, письменная формула включает нулевые слагаемые. Для truth=[0,0,0,1], prediction=[0,0,0,0] получаются 200% и 50%. Противоречие не разрешено нашим предпочтением; обе версии пересчитаны.

Полный разбор: [scoring_objective_audit.md](scoring_objective_audit.md). Точные hashes:

- scorer: `5c83fb1dd256a9636bd27cb7aa9eb978dbe6c76a60f74486ca773523139e1ee2`;
- ТЗ: `2739c3b674bcce805aab6e51f94b0f0806b1816d1e03ea172cc5a2eceff73e07`;
- cached panel: `39e0563d6f79791ac08d8a81f26dafcc66ab392715023eb665d04acfa4a9aa8e`.

## Что пересчитано

Все 151 NPZ: 85 remediation, 35 architecture и 31 legacy OOF. После точной численной дедупликации — 119 forecasts, 25 имён методов; 23 имеют все пять origins, два старых z0.5 — только два окна. Происхождение каждого массива и aliases — `prediction_inventory.csv`, `prediction_aliases.csv`, независимый `reviewer_c_unique_forecasts.csv`. Метрики не брались из старых сводок: они повторно вычислены из labels и прогнозов исходными scalar/global функциями scorer.

Development origins: 2025-09-14, 2025-11-17, 2026-01-20, 2026-03-25, каждый с 64 последующими днями. Terminal 2026-05-28 давно открыт: его значения опубликованы, но исключены из выбора и development averages. Target-окна попарно не пересекаются, однако общие ряды и обучение делают ошибки зависимыми. Четыре окна не дают основания для утверждения статистической значимости.

## Какие кандидаты предпочтительны условно

Ниже сравнение средних **локальных** scores после отдельной нормализации каждого development origin. Rank использует union23 с точным порядком из `candidate_pools.json` и исходным `np.argsort`; minmax — last-value baseline того же origin. Меньше лучше; delta относительно incumbent. Это не прогноз конкурсного места.

'''+table(comp)+'''

При executable SMAPE + rank `weekly_direct_shape_z0.25` лучше incumbent во всех четырёх development окнах и имеет лучший средний rank среди union23. Среди architecture7 и focus4 лидер тот же; исходный/обратный порядок не меняют этих средних победителей. Но состав пула и правила ties могут менять конкретные scores и сравнения, а истинные участники неизвестны. Проверены также пары, learned-only, leave-one-out и legacy17; все значения сохранены, сценарии не трактуются как статистические репликации.

При executable SMAPE + minmax(last) средний лидер union23 — `article_topdown_z0.25`: выигрыш у incumbent в трёх окнах из четырёх. `weekly_direct_shape_z0.25`, напротив, имеет худший средний minmax и выигрывает лишь два окна. Поэтому нельзя выбирать один лучший challenger, молча подменив нормализацию.

Письменная SMAPE меняет выбор: средний union23 rank предпочитает `article_topdown_z0.25`, а minmax(last) — `lgb_l1_z0.25`. Это анализ последствий документированного противоречия, не разрешение поменять scorer. Полные таблицы — [normalization_sensitivity.md](normalization_sensitivity.md), `weighted_rank_sensitivity.csv`, `minmax_sensitivity.csv`.

Per-origin rank ключевых кандидатов:

'''+table(perrank)+'''

Диапазон средних rank-разниц по всем проверенным сценариям с executable SMAPE (разные пулы, оба порядка, семь вариантов ties):

'''+table(sensitivity.reset_index())+'''

У direct shape средняя разница отрицательна во всех 378 сценариях, где кандидат присутствует. Это устойчивость к проверенным локальным настройкам, а не 378 независимых экспериментов или вероятность победы в конкурсе. У allocation и article есть сценарии с изменением знака. Диапазоны разных моделей охватывают разные наборы парных пулов, поэтому не являются общей шкалой качества.

## Почему отдельные метрики расходятся

Изменения средних development метрик относительно incumbent (SMAPE/WAPE/Bias — п.п.):

'''+table(focus_delta.reset_index())+'''

Weekly allocation улучшает SMAPE и Bias **4/4**, одновременно ухудшая WAPE, RMSE и RMSLE **4/4**. Direct shape улучшает SMAPE/Bias **4/4**, WAPE хуже **4/4**, RMSE/RMSLE хуже **3/4**. Article top-down ухудшает SMAPE **4/4**, улучшает WAPE/RMSLE **4/4**, а RMSE/Bias — лишь **2/4**. Отбор только по средним скрывал бы неоднородность последних двух показателей.

Разложение по рядам показывает: у weekly allocation восстановление ранее нулевых прогнозов даёт в среднем −0.593437 п.п. полного SMAPE и −4.531729 п.п. Bias, но +1.741150 п.п. WAPE. При этом sparse-сегмент сам по себе даёт +0.036604 п.п. SMAPE; общий выигрыш SMAPE приходит от regular-сегмента, а не от универсального исправления sparse-demand. У direct shape sparse вклад SMAPE почти нулевой (−0.002068 п.п.), тогда как regular даёт −0.531514 п.п. У article top-down большая часть WAPE-выигрыша связана с рядами, у которых incumbent уже прогнозировал ненулевую сумму (−2.265008 п.п.); восстановление нулевых прогнозов добавляет +0.359539 п.п. WAPE.

Данные по каждому из 131835 сравнений рядов, числу улучшенных/ухудшенных рядов, 11 складам, sparse/regular и горизонту сохранены. Подробности и правильные знаменатели — [tradeoff_diagnostics.md](tradeoff_diagnostics.md). Вклады MSE/MSLE не выдаются за аддитивные изменения RMSE/RMSLE.

Дни 36–64: средние изменения, также описательные:

'''+table(hh.reset_index())+'''

Pareto-статус на каждом development origin:

'''+table(pf)+'''

Нахождение на Pareto-фронте не удостоверяет победу, а отсутствие полного доминирования не является основанием отклонять модель по weighted objective. Все five-metric deltas и dominators опубликованы, включая допуск для roundoff.

## Каталог: подтверждённый риск, а не только оговорка

На первых трёх origins по sales и sales∪stock известны 788, 792 и 793 артикула из799; все799 известны с 2026-03-25. Полный декартов grid добавляет соответственно121,77,66 ключей с неизвестным тогда article ID. Их будущий truth —46,16,395 единиц. Количество пар, ещё не встречавшихся при известных отдельных ID, учитывается отдельно; отсутствие комбинации не равнозначно неизвестному ID.

ТЗ требует11×799 и называет ID анонимными, но отдельный независимо датированный fixed ID catalog до ранних origins не найден. Фактический каталог получен из full-history sales. Это законно доступная история на финальном origin, но future-derived information для раннего backtest. На earliest training origin2024-06-28 наблюдались10 складов/560артикулов=5600декартовых ключей; full grid добавляет3189. Исключение будущих ID меняет pooled warehouse_mean и числовое кодирование article_id. Это влияет на train examples и признаки сохранившихся рядов, даже если будущая продажа не подставлялась напрямую.

У пороговых сравниваемых методов forecasts по неизвестным IDs уже нулевые, поэтому простое обнуление не исправляет проблему и не меняет их метрики. На общем known-only наборе8668 пар направления tradeoff сохраняются: allocation ΔSMAPE−0.841896/WAPE+3.102634; direct shape−0.544150/+1.443393; article+0.534820/−1.911909. Это чувствительность **сохранённых** прогнозов, не модель, переобученная с правильным каталогом. Точный cutoff-valid fit остаётся непроверенным.

Доказательства: [catalog_provenance_audit.md](catalog_provenance_audit.md), first-observed таблица каждого ID/пары,80 cutoff×training-origin проверок признаков. Риск относится ко всем прежним и новым моделям, не используется как выборочное veto challenger.

## Что нужно для замены релиза

1. Уточнить у организаторов фактическую нормализацию, baseline, tie handling, определение SMAPE(0,0), состав truth keys и известность фиксированного ID catalog. До этого нет единственного надёжно восстановленного aggregate objective.
2. Зафиксировать цель и допустимые потери по вторичным метрикам; Pareto оставить диагностикой. При rank приоритет проверки — direct shape, при minmax(last) — article top-down. Не оптимизировать ещё один набор весов/порогов на уже открытых окнах.
3. При отсутствии доказательства заранее известного fixed catalog повторить контролируемую оценку с origin-valid IDs/признаками. Нынешний аудит моделей не переобучает.
4. Проверить зафиксированный выбор на новом законно доступном периоде, не использованном для разработки. Если нового периода не будет, честно ограничить вывод ретроспективным компромиссом и обосновать принятый риск.
5. Измерить полный inference (для direct shape — обе модели), память, детерминированность и полноразмерную offline/API/Docker parity. Эти engineering gates не заменяются локальным rank.

Пересмотренная политика: [revised_model_selection_policy.md](revised_model_selection_policy.md). **Итог: доказанного преимущества incumbent по конкурсу нет; временно сохранить его до разрешения перечисленных вопросов.** Значения scores поддерживают дальнейшую проверку challengers, но не автоматическую promotion. Старый отчёт корректен как запись выполнения осторожного gate; его нельзя читать как доказательство оптимальности incumbent по конкурсной функции.
''')
    c=json.loads((OUT/'reviewer_c_verification.json').read_text(encoding='utf-8'));a=json.loads((OUT/'reviewer_a_rank_crosscheck.json').read_text(encoding='utf-8'))
    write('independent_verification.md','''# Независимая проверка аудита

Дата:19.10.2026. Root и три native reviewers выполняли разные проверки; ни один не обучал forecasting модели. Под независимостью здесь понимается отдельное исполнение расчётов, а не независимая внешняя организация или blinded оценка.

- **Reviewer A — официальный scorer и normalization:** исходный Python-блок ТЗ совпадает с `official_score.py`; проверены SMAPE00, global/per-series метрики, baseline0/clipping, rank ties, полный небольшой merge fixture и CLI fallback. Исполнение `reviewer_a_scoring.py`, результат `reviewer_a_scoring.json`, объяснение `scoring_objective_audit.md`.
- **Reviewer A — независимая нормализация:** из таблицы Reviewer C, без использования root scores, вычислены 1360 строк для трёх пулов, двух SMAPE и двух порядков. С root сравнены 680 rank-строк (max error 8.33e−17) и 680 minmax-строк (max error 1.11e−16). Скрипт `reviewer_a_rank_crosscheck.py`, JSON и `reviewer_a_score_crosscheck.csv`. Победители rank/minmax и per-origin tradeoffs воспроизведены.
- **Reviewer B — temporal validity:** самостоятельно прочитаны raw sales и stock; установлены first-observed ID/пары, известность на каждом cutoff и влияние на features. Проверены 120 NPZ и 80 cutoff×train-origin состояний. Target-окна не перекрываются; независимость ошибок этим не устанавливается. Скрипты `catalog_selection_audit.py`, `catalog_training_features.py`, `catalog_survivor_sensitivity.py`; результаты `catalog_selection_result.json`, соответствующие CSV и два отчёта B.
- **Reviewer C — integrity и official metrics:**151NPZ,119уникальных численных forecasts;120/120хешей совпали с историческими CSV; все пять исходных scalar/global evaluator функций и written SMAPE заново вычислены. Max CSV error1.1368683772161603e−13.409/409 файлов прежнего выпуска совпадают, ZIP SHA и CRC проверены. Скрипт `reviewer_c_verify.py`, `reviewer_c_verification.json` и таблицы.
- **Root — полный сравнительный анализ:**119канонических массивов пересчитаны ещё раз; каждая строка соединена с независимой таблицей C по нормализованному точному пути и сравнена по шести метрикам. Результат `root_reviewer_c_crosscheck.json`. Выполнены86 352 rank-сценарных строки, per-origin paired deltas, Pareto, горизонты, sparse/warehouse и series contributions.

Ограничения: полный562496-row dataframe merge не выполнялся для каждого из151NPZ; вместо этого применены исходные series/global primitives к всем8789столбцам, а merge semantics проверены fixture. NPZ не хранит ключи столбцов, порядок опирается на замороженный cache/catalog contract. Legacy OOF hashes текущие, не аутентифицированы старой matrix. Rank чувствителен к составу пула и unresolved ties; разные сценарии не являются независимыми наблюдениями. Ни training с исправленным каталогом, ни новый untouched test, ни новая Docker parity не выполнялись.

Сохранность релиза подтверждена hash `b56525b5144d77aa7411922db790fe519452e7d5ba33d6dd2fedb7006398325a` для `nonton_solution_remediated_verified.zip`. Новые материалы находятся только в `research/scoring_audit`; старые отчёты сохранены как исторические.
''')
    write('README.md',r'''# Аудит scoring и model selection

Начать с [итоговой рекомендации](final_recommendation_ru.md), затем [пересмотренной политики](revised_model_selection_policy.md). Старый five-metric gate не является конкурсной целью. Локальный rank и minmax предпочитают разных challengers; production сохраняется до разрешения объективных неоднозначностей.

Обязательные результаты: [scoring audit](scoring_objective_audit.md), [per-fold matrix](per_fold_candidate_metrics.csv), [Pareto](pareto_frontier.csv), [rank sensitivity](weighted_rank_sensitivity.csv), [normalization sensitivity](normalization_sensitivity.md), [catalog provenance](catalog_provenance_audit.md), [independent verification](independent_verification.md). Дополнительно доступны per-series, sparse, warehouse и horizon diagnostics, source/input hashes и полный реестр151NPZ.

Воспроизведение из D:/SberTech, без обучения:

```powershell
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/reviewer_a_scoring.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/reviewer_c_verify.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/catalog_selection_audit.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/catalog_training_features.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/catalog_survivor_sensitivity.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/run_scoring_analysis.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/reviewer_a_rank_crosscheck.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/summarize_scoring_audit.py
.\.venv\Scripts\python.exe -X utf8 research/scoring_audit/finalize_audit_report.py
```

Запускать последовательно. Зависимости текущей `.venv` достаточны. Скрипты читают исходные данные по указанным в audit путям; raw CSV не копируются и внешним сервисам не передаются. Все новые выходы — в этой папке, старые saved forecasts и release не перезаписываются.
''')
if __name__=='__main__':run()
