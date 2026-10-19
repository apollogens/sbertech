"""Build Russian decision documents from measured, full-grid experiments."""
from pathlib import Path
import sys
import json
import hashlib
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data import load_panel

OUT=ROOT/'research'
METRICS=['smape','wape','rmse','bias','rmsle']
def table(frame):
    def fmt(x):
        return f'{x:.6f}' if isinstance(x,(float,np.floating)) else str(x)
    return '\n'.join(['| '+' | '.join(map(str,frame.columns))+' |', '|'+'|'.join(['---']*len(frame.columns))+'|']+
                     ['| '+' | '.join(fmt(x) for x in row)+' |' for row in frame.itertuples(index=False,name=None)])
def write(name, text):
    (OUT/name).write_text(text,encoding='utf-8')

def run():
    x=pd.read_csv(OUT/'experiment_results.csv')
    assert len(x)==35 and not x.duplicated(['model','origin']).any()
    dev=x[x.role=='development']; terminal=x[x.role=='terminal_diagnostic']
    mean=dev.groupby('model')[METRICS].mean()
    base=mean.loc['incumbent']; delta=mean.subtract(base)
    mean.to_csv(OUT/'development_summary.csv')
    delta.to_csv(OUT/'development_deltas.csv')
    td=terminal.set_index('model')[METRICS].subtract(terminal.set_index('model').loc['incumbent',METRICS])
    td.to_csv(OUT/'terminal_deltas.csv')
    gates=[]
    for name in mean.index:
        if name=='incumbent': continue
        paired=dev[dev.model==name].set_index('origin')[METRICS]-dev[dev.model=='incumbent'].set_index('origin')[METRICS]
        gates.append(dict(model=name,smape_better_windows=int((paired.smape<0).sum()),bias_better_windows=int((paired.bias<0).sum()),
                          all_mean_metrics_improve=bool((delta.loc[name]<0).all()),
                          promotion_gate=bool(delta.loc[name,'smape']<0 and delta.loc[name,'bias']<0 and (paired.smape<0).sum()>=3 and (delta.loc[name,['wape','rmse','rmsle']]<=0).all())))
    gates=pd.DataFrame(gates); gates.to_csv(OUT/'promotion_gates.csv',index=False)
    assert not gates.promotion_gate.any(), 'A candidate passed: serving verification and new decision are required'
    h=pd.read_csv(OUT/'horizon_results.csv')
    hd=h[h.origin.isin(dev.origin)].groupby(['model','horizon'])[METRICS].mean()
    hd.to_csv(OUT/'development_horizon_summary.csv')
    hb=hd.loc['incumbent']; diffs=hd.copy()
    for name in mean.index:
        diffs.loc[name]=hd.loc[name].subtract(hb).to_numpy()
    diffs.to_csv(OUT/'development_horizon_deltas.csv')
    panel=load_panel(ROOT/'cache'); correlations=[]
    for date in dev.origin.unique():
        origin=panel.dates.get_loc(date); truth=panel.y[origin+1:origin+65]
        errors=[(np.load(OUT/f'predictions/{name}_{date}.npz')['prediction']-truth).ravel() for name in ['weekly_allocation','article_topdown']]
        correlations.append(dict(origin=date,comparison='weekly_allocation vs article_topdown raw',daily_error_correlation=float(np.corrcoef(errors)[0,1])))
    pd.DataFrame(correlations).to_csv(OUT/'development_error_correlations.csv',index=False)
    resource=x[x.model.isin(['weekly_allocation','article_topdown'])].groupby('model')[['train_seconds','inference_seconds','process_peak_rss_bytes']].agg(['mean','max'])
    resource.to_csv(OUT/'resource_summary.csv')
    write('horizon_analysis.md', '# Качество по горизонту\n\nПять метрик считаются заново внутри каждого блока дней; их нельзя усреднять для получения полной метрики. Средние по четырём development-окнам:\n\n'+table(hd.reset_index())+
          '\n\nИзменения относительно incumbent на днях 36–64 (отрицательное значение лучше):\n\n'+table(diffs.xs('36_64',level='horizon').reset_index())+
          '\n\nВсе окна, включая ранее открытый terminal, сохранены в `horizon_results.csv`. Улучшение отдельного блока или Bias не доказывает улучшения всего 64-дневного прогноза. В выпущенной модели дальние метрики не меняются, поскольку challenger не принят.\n')
    final='''# Решение главного исследовательского архитектора

**Сохранить nonton-v1. Ни один из шести заранее заданных режимов трёх архитектур не прошёл development gate.** Новые методы дают измеримые, но конфликтующие улучшения; общего превосходства и улучшения итоговой поставки не заявляем.

## Что выполнено

Первичные научные источники, официальные конкурсные артефакты и выбранные исходники проверены отдельно от локальных результатов. Реконструированы M5 A1/U1; авторские Favorita и Store Item материалы явно отделены от официально подтверждённых мест. Источники, commits, лицензии и ограничения находятся в `competition_solutions.md`, `architecture_reconstruction.md`, `scientific_architectures.md`, `source_licenses.md`, `evidence_register.csv`. Публичность репозитория не даёт права копировать код без лицензии; PoC независимо написаны в `scripts/architecture_experiments.py`.

Реально исполнены десять обучений: пять weekly-volume и пять article-total. Три механизма × два фиксированных режима постобработки × пять окон = 30 прогнозов кандидатов; ещё пять сохранённых прогнозов incumbent пересчитаны тем же evaluator. Итого 35 полных массивов 64×8789; 19 687 360 прогнозных значений. Сохранены TXT-модели, NPZ, training origins/features/config, SHA-256 прогнозов, время и RSS. Непороговая недельная когерентность и article coherence проверены отдельно. После .25 когерентность не заявляется.

## Development: абсолютные значения и изменения

SMAPE/WAPE/Bias указаны в процентах; их разницы — процентные пункты. RMSE/RMSLE — исходные единицы метрики. Это невзвешенное среднее четырёх временных окон, не официальный leaderboard.

'''+table(mean.reset_index())+'\n\nИзменения относительно incumbent:\n\n'+table(delta.reset_index())+'\n\nПроверка заранее записанного критерия:\n\n'+table(gates)+'''

Weekly allocation с порогом улучшает средние SMAPE и Bias, но ухудшает WAPE, RMSE и RMSLE. Сохранение дневной формы уменьшает часть ухудшения, но не устраняет компромисс. Article top-down с порогом улучшает средние WAPE, RMSE и RMSLE, однако ухудшает SMAPE; Bias меняется слабо. Raw методы убирают нулевые суммы, но создают много положительных малых прогнозов на нулевых днях, что ухудшает executable SMAPE. Уменьшение числа нулей само по себе не является успехом.

Недельная цель усредняет редкие дневные события; pooling по артикулу ослабляет разреженность между складами. Это объяснение механизма, а не доказательство причинного эффекта: PoC также меняют число обучающих строк и структуру признаков агрегированной панели. Неудача этих спецификаций не опровергает весь класс temporal/hierarchical моделей.

## Ранее открытый terminal: только диагностика

'''+table(terminal[['model']+METRICS+['zero_total_eligible']])+'\n\nИзменения всех пяти метрик:\n\n'+table(td.reset_index())+'''

В terminal weekly allocation .25 уменьшает eligible zero-total с 5078 до 4011. Raw модели дают 0 таких рядов, но существенно хуже SMAPE/WAPE. Article top-down .25 увеличивает это число до 5154. Terminal не использован для решения о promotion; он уже многократно открыт и не служит независимым подтверждением. Исходный релиз сохраняет 5078 и прежние метрики.

## Почему остановлено расширение

Отдельные улучшения разными механизмами есть, но ошибка raw weekly/article сильно коррелирована: '''+f'{min(r["daily_error_correlation"] for r in correlations):.4f}–{max(r["daily_error_correlation"] for r in correlations):.4f}'+'''. Это не доказывает бесполезность ансамбля, однако не даёт убедительного сигнала для нового подбора весов на многократно использованном development. Новый representation-aware ансамбль в этом цикле не запускался. Полная MinTrace, stockout recovery и NHITS/TiDE не обучались: их статус — отложенные гипотезы, не проигравшие измеренные кандидаты. Stock данные не поддерживают механическую реконструкцию latent demand; будущие stock и actual shares не использованы.

## Стоимость и инженерные ограничения

'''+table(x[x.model.isin(['weekly_allocation','article_topdown'])][['model','origin','train_seconds','inference_seconds','process_peak_rss_bytes']])+'''

RSS мониторится каждые 50 мс и относится к процессу внутри origin, а не к изолированной модели. Измерения ниже 10 GB и 20 минут на fit. У direct-shape дополнительно нужен прежний daily inference; его стоимость не включена в записанный timing. Incumbent timings=0 означают reuse, не новый benchmark. Сетевые ресурсы использовались только для исследования публичных источников; локальные данные внешним сервисам не передавались.

Ни один challenger не встроен в API/Docker, новый финальный submission не формировался. Исследовательские NPZ подтверждают форму полного grid, но не являются сертифицированным API-релизом challenger. Для текущего сохранённого релиза заново выполнены 177 тестов; повторная Docker-сборка в этом исследовании не выполнялась. Прежние Docker/API parity доказательства остаются историческими. Неизменность serving-файлов проверяется SHA-256 в `release_preservation_check.json` и независимом аудите.

## Ограничения доказательств

Все пять окон использовались прежде, независимого untouched test нет. Git до работы не содержал commits; старые ZIP сохранены и production-файлы не изменялись. Каталог фиксирован как в прежних опытах; история появления всех ID на ранних origins отдельно не установлена. Objective Tweedie не совпадает со сложной многокритериальной функцией конкурса. Scorer исключает (0,0) из дневного SMAPE внутри ряда, письменная формула оставляет их нулевыми слагаемыми; обе версии сохранены, конфликт не разрешён молча. Ни внешний paper, ни локальный fixed-candidate rank не дают обещания конкурсного места.

Дальнейшая работа оправдана после появления нового временного периода или новых достоверных сведений о доступности товара. Для текущих данных рационально сохранить простой воспроизводимый релиз и показать судьям конкретные компромиссы, а не объявлять любую более сложную модель улучшением.

Воспроизведение: `.venv/Scripts/python.exe -X utf8 scripts/architecture_experiments.py`, затем `research/summarize_architectures.py` и независимый `research/independent_architecture_review.py`. Обучение читает только cached panel, сохраняет всё в research; production model не затрагивается.
'''
    write('final_architecture_decision.md',final)
    write('presentation_evidence_ru.md','''# Материал для защиты

Мы проверили, меняется ли прогноз, если сначала оценивать объём недели или суммарные продажи артикула, затем распределять их по дням и складам. Это проверка представления задачи, а не новый подбор гиперпараметров.

Исследованы M5, временные и перекрёстные иерархии, ADIDA, stockout-aware demand, NHITS и TiDE. На Nonton реально обучены два типа моделей, обеспечившие три механизма прогноза. Выполнены 30 сравнений кандидатов с пятью прогнозами incumbent на одинаковых временных окнах.

Изменения средних development-метрик:

'''+table(delta.reset_index())+'''

Главный результат: улучшения объёма и SMAPE конфликтуют с WAPE/RMSE/RMSLE. Например, weekly allocation с прежним порогом уменьшает terminal нулевые eligible прогнозы 5078→4011 и Bias, однако ухудшает другие метрики. Поэтому исходная модель сохранена. Изменение всех пяти метрик поставленной модели равно нулю.

Можно утверждать: методы реализованы, исполнены на реальных данных, прогнозы и результаты воспроизводимы, лицензии проверялись, результат отрицательный по заранее заданному критерию promotion. Нельзя утверждать: «мы выиграли leaderboard», «доказали статистическое превосходство», «восстановили истинный спрос», «нейросеть проиграла», «новый challenger прошёл Docker/API». Независимого нового test нет. Слайды должны ясно разделять опубликованные внешние методы, собственные измерения и оставшиеся гипотезы.
''')

if __name__=='__main__':
    run()
