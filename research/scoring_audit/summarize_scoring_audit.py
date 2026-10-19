"""Derived audit tables, independently cross-checked against reviewers."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
from src.data import load_panel
KEYS=['smape','wape','rmse','bias','rmsle']
FOCUS=['incumbent','weekly_allocation_z0.25','weekly_direct_shape_z0.25','article_topdown_z0.25']
def table(frame):
    def fmt(x):return f'{x:.6f}' if isinstance(x,(float,np.floating)) else str(x)
    return '\n'.join(['| '+' | '.join(map(str,frame.columns))+' |','|'+'|'.join(['---']*len(frame.columns))+'|']+['| '+' | '.join(fmt(x) for x in r)+' |' for r in frame.itertuples(index=False,name=None)])
def write(name,text):(OUT/name).write_text(text,encoding='utf-8')
def run():
    x=pd.read_csv(OUT/'per_fold_candidate_metrics.csv');dev=x[x.role=='development'];pair=pd.read_csv(OUT/'paired_incumbent_differences.csv')
    rank=pd.read_csv(OUT/'weighted_rank_sensitivity.csv');norm=pd.read_csv(OUT/'minmax_sensitivity.csv')
    # Independent scalar evaluator crosscheck, joined by exact artifact path.
    independent=pd.read_csv(OUT/'reviewer_c_metrics.csv')
    x['join_path']=x.prediction_path.str.replace('\\','/',regex=False)
    independent['join_path']=independent.path.str.replace('\\','/',regex=False)
    cross=x.merge(independent,on='join_path',suffixes=('','_ind'),validate='one_to_one')
    errors={k:float(np.max(np.abs(cross[k]-cross[k+'_ind']))) for k in KEYS}
    errors['smape_written']=float(np.max(np.abs(cross.smape_written-cross.smape_text)))
    assert len(cross)==119 and max(errors.values())<1e-10
    (OUT/'root_reviewer_c_crosscheck.json').write_text(json.dumps(dict(compared=119,max_errors=errors),indent=2),encoding='utf-8')
    rs=rank[rank.role=='development'].groupby(['pool','order','smape_definition','tie_policy','model']).agg(score=('score','mean'),delta_vs_incumbent=('delta_vs_incumbent','mean'),wins=('delta_vs_incumbent',lambda z:int((z < -1e-12).sum())),folds=('origin','nunique')).reset_index()
    rs.to_csv(OUT/'development_rank_summary.csv',index=False)
    ns=norm[norm.role=='development'].groupby(['smape_definition','baseline','model']).agg(score=('score','mean'),delta_vs_incumbent=('delta_vs_incumbent','mean'),wins=('delta_vs_incumbent',lambda z:int((z < -1e-12).sum())),folds=('origin','nunique')).reset_index()
    ns.to_csv(OUT/'development_minmax_summary.csv',index=False)
    # All sensitivity settings are scenarios, never statistical replicates.
    focus_rs=rs[rs.model.isin(FOCUS)&rs.pool.isin(['legacy17','architecture7','focus4','union23','learned_only','all_available'])]
    focus_rs.to_csv(OUT/'focus_rank_scenarios.csv',index=False)
    complete=rs[rs.folds==4]
    winners=complete.loc[complete.groupby(['pool','order','smape_definition','tie_policy']).score.idxmin()].copy()
    winners.to_csv(OUT/'development_rank_scenario_winners.csv',index=False)
    mean=dev.groupby('model')[KEYS].mean()
    mean['available_origins']=dev.groupby('model').origin.nunique()
    mean.to_csv(OUT/'development_mean_metrics.csv')
    incomplete=dev.groupby('model').origin.nunique();assert incomplete['lgb_l2_z0.5']==2
    # Per-series contribution decomposition (additive SMAPE/Bias/WAPE, MSE/MSLE).
    panel=load_panel(ROOT/'cache');s=pd.read_csv(OUT/'focus_series_differences.csv.gz');groups=[]
    for (date,name),g in s.groupby(['origin','model']):
        origin=panel.dates.get_loc(date);truth=panel.y[origin+1:origin+65];eligible=int((truth.sum(axis=0)>0).sum())
        masks={'all':np.ones(len(g),bool),'sparse':g['sparse'].to_numpy(),'regular':~g['sparse'].to_numpy(),
               'incumbent_zero_recovered':(g.incumbent_zero&~g.candidate_zero).to_numpy(),
               'incumbent_zero_still_zero':(g.incumbent_zero&g.candidate_zero).to_numpy(),
               'incumbent_nonzero':(~g.incumbent_zero).to_numpy(),'future_zero':(g.actual_total==0).to_numpy()}
        for label,mask in masks.items():
            z=g[mask]
            groups.append(dict(origin=date,model=name,segment=label,series=len(z),actual_total=float(z.actual_total.sum()),
                               smape_contribution_pp=float(z.delta_smape.sum()/8789),bias_contribution_pp=float(z.delta_bias.sum()/eligible),
                               wape_contribution_pp=float(z.delta_absolute_error.sum()/truth.sum(dtype=float)*100),
                               mse_contribution=float(z.delta_squared_error.sum()/truth.size),msle_contribution=float(z.delta_squared_log_error.sum()/truth.size)))
    g=pd.DataFrame(groups);g.to_csv(OUT/'focus_group_contributions.csv',index=False)
    # Equal-window averages of contributions retain the per-origin denominators.
    gd=g[g.origin!='2026-05-28'].groupby(['model','segment'])[['smape_contribution_pp','bias_contribution_pp','wape_contribution_pp','mse_contribution','msle_contribution']].mean().reset_index()
    gd.to_csv(OUT/'development_group_contributions.csv',index=False)
    focus_pair=pair[(pair.role=='development')&pair.model.isin(FOCUS)][['origin','model']+['delta_'+k for k in KEYS]]
    focus_pair.to_csv(OUT/'focus_per_fold_deltas.csv',index=False)
    canonical=rs[(rs.pool=='union23')&(rs.order=='forward')&(rs.smape_definition=='executable')&(rs.tie_policy=='official_argsort')].sort_values('score')
    focus_scenarios=focus_rs[(focus_rs.order=='forward')&(focus_rs.tie_policy=='official_argsort')]
    pernorm=norm[(norm.role=='development')&(norm.baseline=='last')&(norm.smape_definition=='executable')&norm.model.isin(FOCUS)][['origin','model','score','delta_vs_incumbent','clipped_metrics']]
    print('UNION23 EXECUTABLE ORDINAL\n'+canonical.to_string(index=False))
    print('FOCUS SCENARIOS\n'+focus_scenarios.to_string(index=False))
    print('MINMAX LAST\n'+pernorm.to_string(index=False))
    write('normalization_sensitivity.md','''# Чувствительность к нормализации

Все оценки ниже — локальные диагностические значения на сохранённых прогнозах, не балл реального leaderboard. Средние считаются после нормализации отдельно на каждом из четырёх development origins. Нормализация средних сырых метрик дала бы другую задачу. Terminal исключён из сводок, но его строки доступны в исходных таблицах.

Основной объединённый набор: 17 прежних методов и 6 новых режимов, incumbent учитывается один раз. Всего 23 метода с полными пятью окнами. Ещё два старых режима z0.5 есть только на двух development origins; они включены в all_available и исходные таблицы, но не конкурируют по среднему двух окон с методами на четырёх. Результаты all_available на каждом origin отражают фактически разный pool. Точный порядок имён сохранён в `candidate_pools.json`.

## Rank на union23: executable SMAPE, прямой порядок, исходный argsort

'''+table(canonical[['model','score','delta_vs_incumbent','wins','folds']])+'''

## Состав пула и определение SMAPE

'''+table(focus_scenarios[['pool','smape_definition','model','score','delta_vs_incumbent','wins','folds']])+'''

В `weighted_rank_sensitivity.csv` сохранены все 86 352 строки: 5 origins, разные пулы, оба порядка, обе версии SMAPE и семь правил ties. Варианты ties: точный исходный `np.argsort`, стабильный ordinal, average/min/max/dense и average после округления метрики до 6 знаков. Последние шесть — диагностические альтернативы, не подтверждённые настройки организатора. Dense также делится на n−1 для изоляции эффекта присвоения рангов; это не отдельный официальный алгоритм. Для точного исходного варианта NumPy версия фиксирована; равные значения не получают автоматически общий ранг. Перестановка списка может менять результат; без стабильной сортировки это не обязательно простое правило «первый выигрывает» для любого размера.

Пулы: legacy17, architecture7, focus4, union23, learned_only, все leave-one-out варианты union23 (incumbent всегда сохранён), каждая пара incumbent–candidate и all_available. Это анализ чувствительности к выбранному окружению, не голосование сценариев и не независимые репликации. Дубликаты массивов удалены из основных сравнений; считать их отдельными участниками было бы искусственным изменением ранга.

## Minmax относительно last-value baseline

'''+table(pernorm)+'''

Пять метрик делятся на метрики сохранённого last-прогноза того же origin, значения выше 1 обрезаются. Это **не** масштабирование по минимуму/максимуму текущего пула. Поэтому удаление кандидата не меняет minmax других методов при неизменном baseline; в отличие от rank, добавление слабого метода не меняет их значения. Если baseline-метрика равна нулю, нулевой model error даёт 0, любой ненулевой — 1. Дополнительно рассчитан mean28 как альтернативный диагностический reference, а не признанный официальный baseline.

`minmax_sensitivity.csv` содержит вклад изменения каждой метрики в delta суммарной оценки; `clipped_metrics` показывает, где clipping скрывает величину ухудшения. Например, улучшение метрики, уже обрезанной до 1 и остающейся выше baseline, не изменит score. Нельзя интерпретировать неизменный score как отсутствие изменения качества.

## Что означает Парето

`pareto_frontier.csv` показывает доминирование на каждом origin для обеих версий SMAPE; дополнительно дана устойчивость к допуску 1e−10, чтобы не называть различие порядка roundoff содержательным преимуществом. `pareto_dominance_pairs.csv` перечисляет все пары доминирования. При положительных весах улучшение всех компонент монотонной нормализации — достаточное условие не ухудшить scalar score, но не необходимое. Строгое улучшение raw metric может быть скрыто clipping.

Если `S(c)=Σ w_j N_j(m_j(c))`, достаточно `Σ w_j [N_j(m_j(c))−N_j(m_j(i))]<0`. Отдельные слагаемые могут быть положительными. Поэтому `all_mean_metrics_improve` отсеивает и модели с лучшим weighted objective. Оно сохраняется как диагностика, а не заменяет конкурсную цель. Точный численный counterexample проверен Reviewer A в `reviewer_a_scoring.json`.
''')
    write('tradeoff_diagnostics.md','''# Что меняется по периодам и рядам

Пять сырых метрик пересчитаны исходными функциями evaluator. Ни одно новое обучение не выполнялось. Разницы кандидатов с incumbent на каждом development origin (минус лучше):

'''+table(focus_pair)+'''

Вклад разреженных/регулярных рядов и восстановления нулевых прогнозов в средние development-разницы:

'''+table(gd[gd.segment.isin(['sparse','regular','incumbent_zero_recovered','incumbent_nonzero'])])+'''

SMAPE и Bias аддитивно разложены по рядам с исходным полным знаменателем (8789 и число eligible на каждом окне). WAPE — изменение суммы абсолютных ошибок, делённое на общую фактическую сумму окна. Для RMSE/RMSLE показаны вклады MSE/MSLE до квадратного корня; их нельзя называть аддитивными изменениями RMSE/RMSLE. Группы sparse/regular образуют разбиение, а группы восстановления нулей и sparse могут пересекаться — их нельзя складывать между собой.

Полные 131 835 сравнений рядов сохранены в `focus_series_differences.csv.gz`, сводки числа улучшенных/ухудшенных рядов и наиболее сильных вкладов — `metric_drivers.csv`. Все 11 складов и сегменты sparse/regular, historical-zero и future-zero пересчитаны в `segment_candidate_metrics.csv`; future-based сегменты — только диагностика, не доступный модели признак. Группы фиксируются по cutoff-history, sparse означает частоту положительных продаж за 180 дней <0.1.

Все методы и горизонты 1–14, 15–35, 36–64, 57–64 доступны в `horizon_candidate_metrics.csv`. Пересчитанные блоковые метрики не складываются в полную SMAPE/Bias: у блока свои denominator и eligible set. Готовые таблицы средних не заменяют строки отдельных окон.
''')

if __name__=='__main__':run()
