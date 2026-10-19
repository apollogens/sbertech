"""Build Russian remediation findings from executed measurements only."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
import numpy as np

OUT=ROOT/'reports/remediation'
KEYS=['smape','wape','rmse','bias','rmsle']
CMD=r'.\.venv\Scripts\python.exe -X utf8'


def md(frame):
    columns=list(frame.columns)
    def value(v):
        return f'{v:.6f}' if isinstance(v,(float,np.floating)) else str(v)
    return '\n'.join(['| '+' | '.join(columns)+' |','|'+'|'.join(['---']*len(columns))+'|']+
                     ['| '+' | '.join(value(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)])


def write(name,text):
    (OUT/name).write_text(text.strip()+'\n',encoding='utf-8')


def run():
    table=pd.read_csv(OUT/'experiment_matrix.csv')
    base=pd.read_csv(OUT/'baseline_metrics.csv')
    ablation=pd.read_csv(OUT/'postprocessing_ablation.csv')
    summary=pd.read_csv(OUT/'candidate_summary.csv')
    dev=table[table.role=='development']
    selected='current_tweedie_z0.25'; challenger='two_part_gamma_z0.25'
    b=dev[dev.model==selected].set_index('origin'); c=dev[dev.model==challenger].set_index('origin')
    measured=[]
    for period,old,new in [('Четыре development-окна: среднее',b[KEYS].mean(),c[KEYS].mean()),
                           ('2026-05-29–2026-07-31: открытое diagnostic',table[(table.model==selected)&(table.role=='terminal_diagnostic')].iloc[0],table[(table.model==challenger)&(table.role=='terminal_diagnostic')].iloc[0])]:
        for k in KEYS:
            measured.append(dict(period=period,metric=k,before=float(old[k]),after=float(new[k]),difference=float(new[k]-old[k]),relative_difference_pct=float(100*(new[k]/old[k]-1)),decision='challenger not promoted'))
    pd.DataFrame(measured).to_csv(OUT/'challenger_before_after_metrics.csv',index=False)
    comparison=b[KEYS+['local_minmax_score','fixed_local_rank_score']].add_suffix('_incumbent').join(c[KEYS+['local_minmax_score','fixed_local_rank_score']].add_suffix('_challenger'))
    comparison.to_csv(OUT/'paired_development_comparison.csv')
    chosen=base.iloc[-1]
    sparse=pd.read_csv(OUT/'series_diagnostics_fold3.csv')
    sparse_mask=sparse.freq_180<.1
    sparse_eligible=sparse_mask&(sparse.actual_total>0)
    frequency_share=100*sparse.loc[sparse_mask,'actual_total'].sum()/sparse.actual_total.sum()
    raw=ablation[(ablation.fold==3)&(ablation.stage=='nonnegative_before_threshold')].iloc[0]
    transformed=ablation[(ablation.fold==3)&(ablation.stage=='serialized_oof_after_threshold')].iloc[0]
    write('statistical_diagnosis.md',f'''
# Диагностика ошибки и недопрогноза

Проверяемый исходный период: 2026-05-29–2026-07-31, origin=2026-05-28. Все пороги сегментов ниже служат описанию; маршрутизации моделей по будущим labels нет. Подробные данные всех 8 789 серий каждого из трёх исходных окон — `series_diagnostics_fold*.csv`, сегменты — `bias_by_segment.csv`, горизонты — `horizon_quality.csv`.

## Что воспроизведено

Из 7 752 серий с положительным фактом ровно 5 078 получили нулевой прогноз суммарно за 64 дня: 65.505676%. У 6 498 signed Bias отрицателен, у 1 254 положителен; точного равенства объёмов нет. Глобальный недопрогноз объёма составляет 19.105414%, средний signed Bias серий −62.834934%. Это разные агрегаты: масса мелких серий получает такой же вес в официальном Bias, как крупная серия.

Медиана, p75, p90 и p95 абсолютного Bias равны 100%. На этих конкретных данных ровно 100% получены у 5 078 eligible нулевых прогнозов, а случаев точного двойного объёма с абсолютным Bias=100% не найдено. Само значение 100% без такого подсчёта этого не доказывало бы.

Диагностические пороги near-zero суммарного прогноза явно заданы: 1e−8, 0.001, 0.1 и 1. Для первых трёх число eligible рядов равно 5 078; для ≤1 — 5 131. Эти пороги не используются для обучения или исправления прогноза.

## Главный воспроизводимый механизм: порог обнуления

Сохранённый Tweedie без порога имеет положительный прогноз на каждом дневном ключе. Минимум на holdout {chosen.raw_min:.12f}; скрытой обратной шкалы или произвольного множителя нет. После nonnegative clipping порог 0.25 удаляет 407 940 положительных дневных значений, {chosen.threshold_removed_volume:.6f} прогнозируемого объёма. Финальный OOF совпал с повторным расчётом выбранных весов побитово. Отдельный выпускной CSV хранится с округлением %.10g; новый full HTTP/Docker parity проверяет допустимую численную разницу.

{md(ablation[ablation.fold==3][['stage',*KEYS,'zero_daily_fraction','global_signed_volume_bias_pct']])}

Удаление порога уменьшает Bias на {raw.bias-transformed.bias:.6f} п.п. ({100*(raw.bias/transformed.bias-1):.6f}% относительно исходного), но ухудшает SMAPE на {raw.smape-transformed.smape:.6f} п.п. и WAPE на {raw.wape-transformed.wape:.6f} п.п. Поэтому это измеренный компромисс, а не общее улучшение. В первых двух окнах действует тот же механизм (`postprocessing_ablation.csv`).

Программная ошибка масштабирования, несовпадение порядка feature names или использование будущего stock не подтверждены. Отсутствие криптографической связи весов и каталога было отдельным реальным риском, но нет доказательства, что в данном baseline каталог фактически был неверным.

## Разреженные ряды и остатки

Историческая частота положительной продажи <10% за 180 дней: {int(sparse_mask.sum())} серий, {int(sparse_eligible.sum())} eligible, {frequency_share:.6f}% фактического объёма holdout. Среди eligible sparse {int((sparse_eligible&(sparse.predicted_total==0)).sum())} получили суммарный нулевой прогноз. Их средний абсолютный Bias={sparse.loc[sparse_eligible,'absolute_bias_pct'].mean():.6f}%; у остальных eligible={sparse.loc[(~sparse_mask)&(sparse.actual_total>0),'absolute_bias_pct'].mean():.6f}%. Sparse составляет примерно половину eligible рядов, но лишь 7.50% объёма; это объясняет разницу series-weighted и volume-weighted картины ошибки, не весь причинный механизм спроса.

Исходный threshold подавляет малые expected-volume estimates. Непороговый mean-прогноз распределяет объём по многим дням без наблюдаемой продажи; исполняемый SMAPE сильно штрафует такие false positives. L1 уменьшает WAPE, но усиливает Bias. Это наблюдаемый конфликт целей, согласующийся с различием mean/median losses; по одному датасету не установлено физическое распределение спроса.

Stock отсутствует во многих ключах; спорные дубли и 57 отрицательных измерений исходной политикой исключаются, а не заменяются нулём. Частые исторические нулевые остатки ассоциированы с большой ошибкой, но не доказывают причинный stockout или величину потерянного спроса. Неизвестный будущий stock нигде не подставляется. Категории sales не входят в 45 model features; исторические category labels в диагностике выбраны по известным до origin строкам.

## Горизонт и испытанные методы

У исходной модели Bias дней 1–14=78.926952%, дней 36–64=84.552356%. Короткие горизонты имеют иной набор zero-actual серий, поэтому разные SMAPE нельзя интерпретировать как чистую монотонную кривую горизонта.

Выполнены SBA, официальный TSB, ADIDA из StatsForecast 2.1.1; они сохранились бенчмарками, не вошли в serving. Все 18 сочетаний 3 методов × 6 поведенческих fixtures прошли проверку finite/nonnegative/shape; fixtures включают all-zero, дробные значения, один positive, новую активность, длинный нулевой хвост и короткую историю. Такие fixtures подтверждают поведение кода, но не идентифицируют истинный спрос. Исходный TSB .05/.05 с инициализацией первых 28 дней содержательно корректен и оставлен отдельно от реализации библиотеки.

Двухкомпонентный binary × positive-only gamma и L1 реально обучены на каждом из пяти cutoff. Вероятности оценены Brier, log loss и reliability bins (`probability_calibration.csv`, `probability_reliability.csv`); post-hoc probability calibration не подбиралась. p*m — оценка условного среднего при корректно оценённых компонентах, не автоматический оптимум SMAPE. Корректность будущих boundaries независимо проверена. Итоговое решение и небольшой средний выигрыш кандидата раскрыты в `final_model_decision.md`.

Воспроизведение: `{CMD} scripts/remediation_diagnose.py`; затем `scripts/remediation_experiments.py`, `scripts/remediation_l2.py`, отдельным `.venv_stats\\Scripts\\python.exe scripts/remediation_statistical.py`, `scripts/remediation_compare.py`. Источники и ограничения методов: `method_evidence.md`, `evidence_register.csv`.
''')
    costs=summary.set_index('model')
    speed_ratio=costs.loc[challenger,'inference_seconds']/costs.loc[selected,'inference_seconds']
    size_ratio=costs.loc[challenger,'model_bytes']/costs.loc[selected,'model_bytes']
    write('final_model_decision.md',f'''
# Решение о модели и выпуске

Решение PRINCIPAL ML REMEDIATION ARCHITECT: **сохранить прежний Tweedie power=1.3, 220 итераций, threshold=0.25** и выпустить заново обученный проверяемый bundle. Это осознанный выбор простоты и стоимости при небольшом и неоднородном выигрыше challenger. Утверждение «новые методы вообще ничего не улучшили» неверно. Замену качества в релизе не заявляем.

## Протокол и результаты

Пять полных последовательных 64-дневных окон, origins: 2025-09-14, 2025-11-17, 2026-01-20, 2026-03-25, 2026-05-28. Первые четыре — retrospective development; последнее — ранее открытая диагностика. Каждый обучаемый метод использует labels не позже своего cutoff. Известный прежний L2 добавлен открытым post-start amendment; исходный JSON не переписан. Всего **17×5=85** сравнений, independently checked. Все пять сырых метрик, sparse и дни 36–64, file hashes и стоимости: `experiment_matrix.csv`. Fixed-set rank не предсказывает rank среди неизвестных участников.

Средние четырёх development-окон:

{md(summary[['model',*KEYS,'fixed_local_rank_score','local_minmax_score']])}

Двухкомпонентный кандидат с прежним порогом — лучший по среднему fixed17 rank ({costs.loc[challenger,'fixed_local_rank_score']:.9f} против {costs.loc[selected,'fixed_local_rank_score']:.9f}) и minmax ({costs.loc[challenger,'local_minmax_score']:.9f} против {costs.loc[selected,'local_minmax_score']:.9f}). Minmax лучше в трёх окнах из четырёх, SMAPE — во всех четырёх. Средний Bias лучше на {costs.loc[selected,'bias']-costs.loc[challenger,'bias']:.6f} п.п., но индивидуально хуже в трёх окнах из четырёх. Это локально измеренный небольшой средний выигрыш; его статистическая значимость и перенос на новые периоды не установлены. Нельзя объявлять его статистически незначимым без соответствующего исследования.

Кандидат требует два Booster вместо одного; измеренный средний inference {costs.loc[challenger,'inference_seconds']:.6f} с против {costs.loc[selected,'inference_seconds']:.6f} с ({speed_ratio:.3f}×), суммарные веса {costs.loc[challenger,'model_bytes']:.0f} против {costs.loc[selected,'model_bytes']:.0f} байт ({size_ratio:.3f}×). Эти стоимости и неоднородность Bias на development — основания консервативного сохранения incumbent. Вначале зафиксирован общий принцип предпочитать простоту при недостаточной определённости; универсальный численный порог такого tradeoff не был задан, поэтому решение является инженерным суждением, а не механическим доказательством оптимальности.

На terminal получены небольшое улучшение Bias (80.565557→79.773277%) и SMAPE (158.687162→158.674255%), но ухудшение WAPE/RMSE и обоих локальных scores. Это публикуется как диагностика; terminal не служит скрытым veto выбора. Для дней 36–64 terminal Bias 84.552356→83.768484%, однако устойчивого улучшения дальнего Bias на development нет (лучше в двух окнах из четырёх). В итоговом сохранённом релизе дальние метрики не изменены.

## Принятие и отклонение

- Приняты: versioned SHA-256 contract, traceable retraining record, защита mutable cache и version/input/model identity, failure/concurrency coverage, CLI paths/errors/integration.
- SBA, TSB и ADIDA: приняты как исполняемые научно обоснованные бенчмарки, отклонены для serving по измеренному многокритериальному сравнению.
- L1: WAPE лучше во всех четырёх development-окнах, Bias и SMAPE хуже; не принят.
- Непороговый Tweedie: Bias лучше, SMAPE/WAPE хуже; не принят как универсальное исправление.
- Binary×Gamma: небольшой средний локальный выигрыш признан, кандидат сохранён для дальнейшей проверки, в поставку не включён по явному tradeoff стоимости/сложности/неоднородности. Порог .25 исследован как прежняя политика, не как новый поиск по holdout.
- Прежний L2: ranking-sensitive конкурент, средний rank лучше incumbent, но средний minmax хуже; не доказано общее преимущество и не принят. Не заявляется, что incumbent минимизирует официальный rank среди всех известных моделей.

## Что изменилось численно в релизе

`before_after_metrics.csv` фиксирует по всем пяти метрикам **разницу 0** на 2026-05-29–2026-07-31 (7 752 eligible Bias-серии). Веса, config и catalogs нового refit побитово совпали с исходными (`final_refit_parity.json`); этот результат не приписывает старому обучению новое происхождение. Новое обучение зарегистрировано отдельно с фактическими hashes panel/catalog/selection и train sources. `challenger_before_after_metrics.csv` отдельно хранит ненулевые исследовательские differences, `paired_development_comparison.csv` — каждый development origin.

Релиз не является доказанной высокоточной системой управления запасами: WAPE=80.430066%, absolute Bias=80.565557%. Прогнозируются наблюдаемые продажи, не восстановленный спрос. Данных о финансовом эффекте и месте leaderboard нет.

Воспроизведение сравнения: `{CMD} scripts/remediation_compare.py`; исполнения — `remediation_experiments.py`, `remediation_l2.py`, `remediation_statistical.py` в соответствующих lock-средах. Научная обоснованность: `method_evidence.md`, первичные ссылки и точные пределы утверждений в `evidence_register.csv`. Независимый вердикт численного сравнения: `review_challenger_verification.json` (85/85); reviewer согласен с conservative retention при раскрытом выигрыше и tradeoff, см. `independent_verification.md`.
''')
    register=pd.read_csv(OUT/'research_evidence.csv').fillna('Не применимо')
    updates={
        'RES-HURDLE':('scripts/remediation_experiments.py','p*m выполнен binary×positive-only Gamma; не count-hurdle likelihood','Испытано как two-part mean; не принято в serving','review_two_part_checks.json; review_challenger_verification.json'),
        'RES-TWOPART':('scripts/remediation_experiments.py','4dev minmax .836491304828→.834972067486; Bias хуже3/4 individual windows','Небольшой средний выигрыш признан; не принято по явному tradeoff','review_challenger_verification.json'),
        'RES-GLOBAL':('scripts/remediation_experiments.py','Global Tweedie/L1 и two-part оценены на5 origins; исходный global сохранён','Принцип применён; превосходство global над всеми local моделями не заявлено','review_challenger_verification.json'),
        'RES-M5':('scripts/remediation_compare.py','Nonton результаты85 записей; результат M5 не переносился','Только методологический контекст; отдельный M5-подобный метод не внедрялся','method_evidence.md; independent_verification.md'),
        'RES-ACCURACY':('scripts/remediation_diagnose.py','Official SMAPE158.687162%; prose47.089556%; definitions не изменены','Предостережение о метриках учтено; спор ТЗ остаётся','review_scoring_full_grid.json'),
        'RES-STATS':('scripts/remediation_statistical.py','StatsForecast2.1.1 в .venv_stats;15 benchmark rows +18 behavior checks','Установлен в изоляции; выполнен; оставлен benchmark','review_challenger_verification.json; statistical_behavior_checks.csv'),
        'RES-LGBM':('scripts/remediation_experiments.py','LightGBM4.7.0; fixed220 rounds; L1, Tweedie, binary, Gamma выполнены','Официальные objectives использованы; winner не объявлен по документации','review_challenger_verification.json'),
        'RES-CV':('scripts/remediation_compare.py','5 origins×64дня,85 записей;4development+открытый terminal','Cutoff-safe rolling-origin выполнен; независимость окон/untouched не заявлены','review_challenger_verification.json; review_two_part_checks.json'),
        'RES-SIGNATURE':('scripts/package_model.py --model-dir model','Manifest bind schema/mappings/config/weights/code/dependencies; fresh run training_recorded','Локальный контракт реализован и проверен; MLflow не добавлялся','review_final_artifact.json'),
        'RES-TSB-LOCAL':('scripts/remediation_experiments.py','Прежний TSB на5 окнах;terminal Bias66.147479%; SMAPE178.519098%','Сохранён benchmark; formula error не установлен','review_challenger_verification.json'),
        'RES-SCORER':('scripts/remediation_diagnose.py','Official primitives full562496grid совпали;monolithic run остановлен через565с','Совместимость подтверждена; конфликт с prose/rank ties не разрешён','review_scoring_full_grid.json; review_monolithic_scorer_terminated.json'),
    }
    for claim,(command,numbers,status,review) in updates.items():
        mask=register.claim_id==claim
        executable=r'.\.venv_stats\Scripts\python.exe -X utf8 ' if claim=='RES-STATS' else CMD+' '
        register.loc[mask,'local_reproduction_command']=executable+command
        register.loc[mask,'local_numerical_evidence']=numbers
        register.loc[mask,'acceptance_status']=status
        register.loc[mask,'reviewer_signoff']=review
        register.loc[mask,'validation_period']='2026-10-18; временные окна/ограничения см. experiment_matrix.csv'
    for claim, model in [('RES-SBA','sba_official'),('RES-TSB','tsb_official'),('RES-ADIDA','adida_official')]:
        if claim in set(register.claim_id):
            mask=register.claim_id==claim
            register.loc[mask,'local_reproduction_command']=r'.\.venv_stats\Scripts\python.exe -X utf8 scripts/remediation_statistical.py'
            row=table[(table.model==model)&(table.role=='terminal_diagnostic')].iloc[0]
            register.loc[mask,'local_numerical_evidence']='terminal: '+', '.join(f'{k}={row[k]:.9f}' for k in KEYS)+'; все5окон experiment_matrix.csv'
            register.loc[mask,'validation_period']='5×64 дня; origins 2025-09-14…2026-05-28'
            register.loc[mask,'acceptance_status']='Испытан; оставлен benchmark, не принят в serving'
            register.loc[mask,'reviewer_signoff']='Независимый review_challenger_verification.json:85/85'
    def evidence(claim,category,fix,problem,title,owner,url,technical,limitations,command,numbers,period,status,review):
        return dict(zip(register.columns,[claim,category,fix,problem,title,owner,'Дата проверки 2026-10-18',url,technical,limitations,command,numbers,period,status,review]))
    local=[
        evidence('LOCAL-BASELINE','OFFICIALLY DOCUMENTED IMPLEMENTATION','Повторное вычисление метрик (воспроизводимость, не улучшение качества)','Предыдущий QA требовал независимого воспроизведения','Официальный scorer из предоставленного ТЗ','Организаторы Nonton','C:/Users/apollo/Desktop/выборка/markdown hakaton.md','SMAPE zero-zero exclusion и absolute Bias сохранены','Это reproducibility, разница quality=0',CMD+' scripts/remediation_diagnose.py','158.6871617213434;80.43006567684449;.8662841487164723;80.5655572662628;.3126153218811934','2026-05-29–2026-07-31','Baseline воспроизведён','review_metrics_baseline.txt'),
        evidence('LOCAL-THRESHOLD','LOCALLY VERIFIED IMPROVEMENT','Контролируемая ablation порога; изменение НЕ принято','5078 eligible нулевых прогнозов','LightGBM Parameters','LightGBM maintainers','https://lightgbm.readthedocs.io/en/stable/Parameters.html','Tweedie model predicts expected nonnegative target; external threshold alters predictions','Bias ниже ценой худших SMAPE/WAPE; не общий uplift',CMD+' scripts/remediation_diagnose.py','Без порога Bias57.948579; с порогом80.565557; удалённый объём30517.941043','2026-05-29–2026-07-31','Диагностика принята; снятие порога отклонено','independent_verification.md; baseline exact OOF checks'),
        evidence('LOCAL-TWOPART','LOCALLY VERIFIED IMPROVEMENT','Binary×positive-only Gamma: небольшой средний development gain','Ограниченное качество sparse','LightGBM Parameters; conditional expectation identity','LightGBM maintainers','https://lightgbm.readthedocs.io/en/stable/Parameters.html','p*m равно оценке условного среднего для неотрицательного Y','Не SMAPE optimum; Bias хуже3/4 dev; значимость не установлена; 2.1x cost',CMD+' scripts/remediation_experiments.py','dev minmax .836491304828→.834972067486; Bias83.043671736→82.878383391','4dev×64 дня; terminal отдельно','Локальный средний выигрыш признан; serving не принят','review_challenger_verification.json:85/85; review_two_part_checks.json'),
        evidence('ENG-ARTIFACT','OFFICIALLY DOCUMENTED IMPLEMENTATION','Versioned SHA-256 contract и traceable run','Loader принимал другой sorted catalog','hashlib; MLflow signatures','Python Software Foundation; MLflow','https://docs.python.org/3/library/hashlib.html','SHA-256 проверяет bytes; локальный manifest связывает weights/schema/mappings/config/code/dependencies','Не цифровая подпись; старое происхождение не восстанавливается',CMD+' -m pytest tests/test_remediation_backend.py -q','36 новых backend regression checks; final refit bytes identical','2026-10-18','Принято; fullsize/Docker отдельные gates','independent_verification.md'),
        evidence('ENG-CACHE','OFFICIALLY DOCUMENTED IMPLEMENTATION','Consistent snapshot, defensive copies, identities, single worker','Mutable frame и отсутствие диагностической версии','threading Lock; FastAPI workers','Python Software Foundation; FastAPI','https://fastapi.tiangolo.com/deployment/server-workers/','Workers имеют отдельную память; lock/cache рассчитан на один процесс','Несколько контейнеров/custom launchers запрещены deployment policy',CMD+' scripts/remediation_backend_probe.py','См. backend_fullsize/benchmark.json (после исполнения)','2026-10-18','Принято при подтверждённом fullsize probe','independent_verification.md; cache_concurrency_report.md'),
        evidence('ENG-CLI','OFFICIALLY DOCUMENTED IMPLEMENTATION','Настраиваемые пути, exit2 и реальные subprocess tests','Неполное покрытие и cwd-dependent CLI','argparse documentation','Python Software Foundation','https://docs.python.org/3/library/argparse.html','Entry points проверяются subprocess и реальным uvicorn','run_pipeline full real-data retrain не подменён helper-only тестом; scope см. cli_test_report.md',CMD+' -m pytest tests/test_remediation_cli.py -q','19 CLI cases plus2 model tests passed initial combined21','2026-10-18','Принято в проверенном scope','reviewer final suite'),
    ]
    pd.concat([register,pd.DataFrame(local)],ignore_index=True).to_csv(OUT/'evidence_register.csv',index=False)
    write('presentation_evidence_ru.md',f'''
# Измеренная история для презентации

1. Мы начали с работающего решения, сохранили его и независимо воспроизвели пять метрик на 562 496 ключах. Исходный Bias — 80.565557%, WAPE — 80.430066%. Это не показательная высокая точность.
2. Причина значительной части series-level недопрогноза воспроизводима: порог 0.25 превращает прогноз 5 078 из 7 752 положительных по факту серий в полный ноль. Он удаляет 30 517.94 единицы прогнозируемого объёма. Однако его снятие ухудшает главные SMAPE/WAPE, поэтому простого универсального исправления нет.
3. Разреженные исторические серии — 4 921 пара, 7.50% объёма holdout. На них Bias=101.227735%; у остальных eligible=59.667485%. Нельзя обещать восстановление потерянного спроса по неизвестным остаткам.
4. Проверены 17 кандидатов на пяти 64-дневных окнах: SBA, TSB, ADIDA, исторические средние, global L2/L1/Tweedie и binary×Gamma. Все 85 строк проверены независимо. Публикации обосновывают рассмотрение методов; результаты Nonton получены только локальным выполнением.
5. Binary×Gamma дал небольшой средний выигрыш development minmax: 0.836491→0.834972; средний Bias 83.043672→82.878383%, но Bias ухудшился в трёх окнах из четырёх. Веса почти вдвое больше, inference примерно вдвое дольше. Мы сохранили более простую production модель, а сильного кандидата оставили для дальнейших данных. Значимость выигрыша не установлена.
6. Главный принятый результат — проверяемость поставки: точные веса связаны с каталогом/схемой/кодом/зависимостями и новым обучающим run; cache получает version/model/input identities, безопасно переживает ошибку POST и проверяется настоящими конкурентными запросами.
7. Финальные веса, config и catalogs побитово совпали с исходными; quality delta релиза по всем пяти метрикам равна нулю. Это честное ограничение результата, а не обещание победы или финансовой экономии. Измеренные API/Docker ресурсы и итоговый release gate приведены в `release_verdict.md` и `cache_concurrency_report.md`.

Для слайдов с конкретным before/after используйте `before_after_metrics.csv` (релиз) и `challenger_before_after_metrics.csv` (исследование); не смешивайте эти таблицы. Все источники и reviewer verdict доступны в `evidence_register.csv` и `independent_verification.md`.
''')
    print('Отчёты и evidence register построены из выполненных измерений.')


if __name__=='__main__':
    run()
