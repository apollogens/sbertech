"""Produce a factual release verdict and bind experimental/release artifacts."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from integration.analyze_results import table
OUT=ROOT/'integration';KEYS=['smape','wape','rmse','bias','rmsle']
def sha(p):
    digest=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):digest.update(b)
    return digest.hexdigest()
def write(name,text):(OUT/name).write_text(text,encoding='utf-8')
def run():
    x=pd.read_csv(OUT/'per_origin_metrics.csv');assert len(x)==215
    dev=x[x.role=='development'];means=dev.groupby('candidate')[KEYS].mean()
    scores=pd.read_csv(OUT/'development_scores.csv').set_index('candidate')
    gates=pd.read_csv(OUT/'quality_gates.csv');learned=json.loads((OUT/'learned_weight_evaluation.json').read_text())
    mechanisms=['D','W','S','A','equal4','DA75','DA50','DA25','DS50','source_DA70']
    names=[n+':P1' for n in mechanisms];comparison=means.loc[names].join(scores)
    delta=means.subtract(means.loc['D:P1'])
    selected=learned['selected'];later=dev[(dev.candidate==selected)&dev.origin.isin(['2026-01-20','2026-03-25'])]
    r=pd.read_csv(OUT/'rank_sensitivity.csv');mm=pd.read_csv(OUT/'minmax_sensitivity.csv')
    rounding=dev[dev.mechanism=='D'].groupby('candidate')[KEYS+['zero_total_eligible','positive_changed_to_zero','signed_series_bias','total_volume','volume_change']].mean()
    passed=gates[gates.quality_screen]
    model_bytes={p.parent.name:sum(q.stat().st_size for q in p.parent.glob('*.txt')) for p in (OUT/'models').glob('*/config.json')}
    timings=x.groupby('origin')[['train_seconds','component_inference_seconds','key_alignment_seconds','process_peak_rss_bytes']].first()
    parity=json.loads((OUT/'release/parity.json').read_text(encoding='utf-8'))
    container=json.loads((OUT/'release/container_benchmark.json').read_text(encoding='utf-8-sig'))
    write('model_selection.md','''# Решение о кандидатах

Основная модель сравнения — corrected D:P1, не прежний incumbent с иным historical catalog/encoding. Матрица43вариантов, веса и алгоритмы были заданы до первых успешных fits. Изменение диапазона categorical hashes после технического bad allocation до любых прогнозов описано отдельно; неудача не скрывается. Успешных исторических обучений15, плюс3 финальных экспериментальных Booster; одна ранняя попытка завершилась исключением.

Средние четырёх development origins, raw metrics и local scores:

'''+table(comparison.reset_index())+'''

Разницы пяти метрик относительно corrected D:P1:

'''+table(delta.loc[names].reset_index())+'''

Проверка заранее заданного двухобъективного quality screen:

'''+table(gates)+'''

Quality screen не требует Pareto-доминирования. Он учитывает early/later средние и число per-origin wins по rank/minmax. Его прохождение является основанием рассмотреть кандидат, но не разрешением выпуска. Ранги локальны, реальная нормализация не подтверждена, поздние окна ранее открывались. Все ухудшения пяти метрик опубликованы; terminal не выбирает веса.

**Предпочтительный исследовательский кандидат — equal4:P1.** Он действительно улучшает все пять средних development-метрик относительно corrected D:P1 и выигрывает оба локальных score в4/4окон. Отрицать этот результат на основании старого all-five-gate неправильно. Выигрыш minmax составляет около0.34% относительно corrected D, а текущая реализация требует порядка800MBтекстовых весов вместо одного Booster порядка1.3MB. Это измеренный tradeoff конкретной sparse categorical реализации, не фундаментальная стоимость ансамблей. Решение оставить её experimental — инженерное суждение о достаточности небольшого ретроспективного выигрыша при неопределённости, а не статистическое доказательство, что incumbent лучше.

Выбранный из ограниченной сетки по первым двум origins вес: '''+selected+'''. Его последующие два origins:

'''+table(later[['origin','candidate']+KEYS+['minmax_last']])+'''

**Production сохранён как nonton-v1.** Доказательств будущего выигрыша недостаточно: reused development, отсутствие нового untouched периода, неоднозначность rank/minmax и SMAPE; стоимость экспериментальных сериализованных моделей велика. Это не утверждение оптимальности incumbent. Новые методы оставлены воспроизводимыми экспериментальными компонентами, а не молча включены в POST. Нет необходимости ухудшения одной метрики как автоматического veto.

Число прошедших предварительный quality screen: '''+str(len(passed))+'''. Полный serving verification относится к incumbent. Экспериментальная standalone-проверка на180дневном входе подтверждает работу и воспроизводимость, но не качество на новом test и не parity challenger с HTTP/Docker.
''')
    write('final_decision_ru.md','''# Финальное решение по ансамблю и поставке Nonton

**Выпущенная архитектура остаётся nonton-v1.** Реализованы и исполнены ансамбли, округление и catalog-corrected модели; они поставляются как проверенный экспериментальный код и изолированный bundle. Production `src/`, `app/`, `model/`, исходные submission и прежние ZIP не заменялись. Гарантированное превосходство или конкурсное место не заявляется.

## Внешние источники и перенос

Однозначно найден один пользовательский внешний GitHub-проект: [filipp880/forecast-64-v1](https://github.com/filipp880/forecast-64-v1), commit `f8a8c6e60edaf12af2fd351e290c35e6875afea0`, локально `C:/Users/apollo/AppData/Local/Temp/forecast-comparison-7371efa0b4b14184a05e39ed9dc127b8`. Пользователь подтвердил этот URL и приблизительный Temp-путь в ходе работы. Второй источник из первоначального задания по целевому поиску не установлен и в уточнении не назван. **Интеграция двух проектов не заявляется.** M5/Favorita — дополнительные исследовательские клоны, не подстановка второй пользовательской загрузки.

Реальный source pipeline смешивает .3 hurdle+.7 LightGBM после обратного преобразования цели, затем clip/threshold/np.rint; hurdle использует жёсткий gate p>=.5, вопреки комментарию о произведении p×magnitude. В Git tracked tree нет лицензии. Защищённый код не копировался: независимо реализованы общая выпуклая смесь и half-even postprocessing. `source_DA70` — только адаптация fixed-mixture формы к Nonton daily/article, не воспроизведение чужой hurdle модели. Входы уже в шкале observed quantity, повторный expm1 не применяется.

Source AST fixtures и собственный engine реально исполнены; четыре политики совпали на10010конечных неотрицательных значениях. Дополнительные M5 key-merge/mean и Favorita CSV-format/clipping fixtures проверены, но чужой clip1000 и формат .4f автоматически не переносились. Полные paths/лицензии/обязательства: `source_inventory.md`, `source_analysis.md`, `source_license_audit.md`, `ensemble_reconstruction.md`, `source_audit/transfer_review.md`.

Общая научная основа forecast combination проверена по Wang, Hyndman, Li, Kang, [Forecast combinations: an over 50-year review](https://doi.org/10.1016/j.ijforecast.2022.11.005). Она не доказывает полезность нашей смеси. Ни published результат, ни внешний репозиторий не заменяют Nonton validation.

## Исправление исторического каталога

Output catalog и feature catalog разделены. На каждом **INNER** origin берутся лишь ID, уже встреченные в sales к этой дате, включая строки quantity=0. История обрезается до origin до snapshot/агрегации; future ID не добавляет нулевых колонок в warehouse averages. Идентичность категорий — независимые от будущего bounded SHA256 codes int32 с проверкой коллизий. Unknown output IDs получают deterministic0; финальный grid11×799×64 сохраняется. Категории товаров не используются, future popularity/realized quantity не инициализируют cold start.

Raw first-seen повторно проверен; stock-onlyIDs на ранних внутренних origins существуют и сознательно не включены в консервативную sales-only политику. Это потеря доступной информации, не future leak. Никакого ранее официально датированного fixed ID catalog не найдено. Ключи исторического evaluation сохраняются прежними, а будущие ID используются только для проекции output и оценки, не predictive features. Оговорка о реально неизвестном организаторском forecast catalog остаётся.

Исправленные D/W/S/A обучены заново на одинаковой новой политике. Старые NPZ не перезаписаны. Разницу correctedD и прежнего incumbent нельзя выдавать за чистое качество архитектуры: меняются catalogue handling и categorical encoding. Воспроизводимый отчёт и before/after coverage — `catalog_leakage_resolution.md`, `catalog_audit/` и `review/legacy_comparison.csv`.

## Архитектура и веса

Три обучаемых Booster дают четыре представления: D — daily direct; W — weekly totals+историческая weekday allocation; S — те же weekly totals+форма D; A — article totals+исторические warehouse shares. S переиспользует D и W без повторного inference. Цель observed sales, future stock и future allocation shares не используются. Weekly horizon64=9×7+1. Все прогнозы выравниваются по date/warehouse/article, полный ключевой hash хранится с NPZ.

Смесь yhat=Σw_k×yhat_k, w>=0, Σw=1. Фиксированные варианты — equal4, D/A75:25,50:50,25:75, D/S50:50 и source-derived D/A70:30. Constrained learned-weight challenger выбирает лишь один из трёх D/A весов по первым двум origins; зафиксирован '''+selected+'''. Высокоразмерного stacking и подбора индивидуальных параметров товаров нет. Изменение состава компонентов/порогов после результатов не выполнялось.

Выполнены15исторических fits,215явных candidate×origin прогнозов и20raw component прогнозов. Дополнительные3Booster образуют финальный экспериментальный standalone bundle. Одна первоначальная failedattempt до любых метрик сохранена как `experiments_failed_encoding.txt`; runtime correction ограничила диапазон кодов. Новых untouched labels не появилось.

## Что показали качество и округление

Средние development показатели и локальные scores десяти P1 механизмов:

'''+table(comparison.reset_index())+'''

Изменения всех пяти метрик относительно corrected D:P1:

'''+table(delta.loc[names].reset_index())+'''

Округление D, отдельно от эффекта ансамбля (средние четырёх origins):

'''+table(rounding.reset_index())+'''

P0 — continuous; P1 — значения<.25 в0; P2 — np.rint, половины к чётному; P3 — P1 затем P2. P2=P3 при конечных nonnegative inputs, поэтому это aliases, не два успеха. CSV precision отдельно от integer rounding. В исходном output contract нет обязательного целочисленного прогноза: scorer приводит значения к float и проверяет отсутствие NaN/negative. Integer исторические labels сами по себе не оптимизируют смешанную loss. Fixture с дробной целью показывает, что округление может ухудшать точный прогноз.

Изменённые положительные значения, zero-total eligible, signed Bias, общая сумма, дневное/серийное искажение и overhead записаны для каждой стратегии. P4 сравнивает postprocess-before/after averaging; это различные операции. Threshold и rounding в общем случае разрушают weekly/article coherence; rawW/rawS сохраняют свои bucket totals, rawA — article totals. P6 aggregate-preserving integer allocation не вводился: integer output не требуется и его полезность не установлена.

Основной rank universe18зафиксирован до расчётов; точные aliases удаляются один раз по четырём development arrays, не меняя pool по отдельным origins. Evaluator weights50/20/15/10/5, executable/written SMAPE, minmax(last), exact/average ties, direct/reverse ordering, expanded/base/leave-one-out pools раскрыты в `scoring_sensitivity.md` и CSV. Это не точный leaderboard. Четыре development windows использовались неоднократно, последний terminal только diagnostic. Статистическая значимость и будущее превосходство не установлены.

Предварительный quality screen прошли '''+str(len(passed))+''' вариантов. Лучший исследовательский вариант — **equal4:P1**: все пять средних development-метрик лучше corrected D:P1, а rank и minmax лучше на4/4origins. Это реальный положительный результат, не объявленный неудачей. Средний minmax улучшается примерно на0.34% относительно corrected D. Его будущая устойчивость не установлена, а стоимость конкретной сериализации и inference заметно выше. Поэтому он сохранён как experimental candidate; решение оставить production — открытое инженерное суждение, не вывод об отсутствии улучшений.

Подробный выбор и every-origin losses — `model_selection.md`, `quality_gates.csv`, `paired_corrected_reference.csv`, `sparse_metrics.csv`, `horizon_metrics.csv`. Одна ухудшившаяся метрика сама по себе не является причиной отказа. Итог определяется неопределённостью переноса, реальной стоимостью и готовностью выпуска, а не требованием Pareto-доминирования.

## Стоимость и границы интеграции

Полный shared-component inference включает все3Booster, allocation и создание keyed frames; key alignment измерен отдельно. Записанные train_seconds повторены в строках вариантов, их нельзя суммировать215раз. Общий sampled RSS относится ко всему процессу origin, а не изолированному модели. Размеры сохранённых текстовых весов по пакетам:

'''+table(pd.DataFrame([dict(bundle=n,txt_bytes=b) for n,b in model_bytes.items()]))+'''

Времена исторических прогонов:

'''+table(timings.reset_index())+'''

Большой размер TXT связан с реализацией categorical bitsets при разреженных bounded кодах; это наблюдаемая инженерная стоимость текущей реализации, не теоретическое свойство ансамблей. Оптимизация плотного model-local category mapping возможна отдельно, но в этом цикле ещё один подбор/retrain не выполнялся. Полный experimental180 CSV inference проверяется отдельно, включая model load, все3Boosters и alignment; wrapper не оптимизирован под subset components, поэтому latencyD тоже включает лишние модели. Cached OOF timings не выдаются за serving latency.

Экспериментальный manifest связывает модели, feature schemas, каталоги, runtime sources, dependency versions, weights, postprocessing, источник алгоритмической идеи и hashes. На180дневном входе membership строится только по предоставленным sales CSV; audit/raw train CSV на inference не читаются. Загрузка нового input без обучения проверена, tampered config и TXT отвергаются. Полный equal4 inference на том же180дневном входе занял22.112с против7.651с incumbent, около2.89× медленнее; повтор22.713с, sampledRSS2.240GB. Это отдельные последовательные измерения, не статистический latencybenchmark. Два полных повторных прогноза совпали точно. Подробности и hashes — `experimental_standalone_verification.md` и `release/experimental180/verification.json`. Это isolated standalone candidate, **не новый API/Docker release**.

## Проверенный финальный выпуск

Официальным остаётся исходный `submission.csv` и архив `nonton_solution_remediated_verified.zip`. Новый независимо записанный verification CSV: `integration/release/submission.csv`, SHA-256 `'''+parity['submission_sha256']+'''`. Отличие от исходного≤4.992e−9 из-за float formatting; исходный CSV не заменён. Оба покрывают562496строк,64дня2026-08-01—2026-10-03,11складов799товаров, без NaN/Inf/negative/duplicate/missing keys, deterministic ordering.

Заново прошли177прежних pytest-проверок и16новых. Host offline/API difference0.0; repeated POST byte-identical, filteredGET/CSV/JSON и error/cache contracts проверены. Docker без сети4CPU/6GiB: POST34.376с, cgrouppeak3810914304байт, offline/container difference≤3.56e−15; restart200health/cache409. CPU, image identity/size и cached build limits документированы в `release_tests.md`, raw benchmarks в `release/`. Cold build не измерялся; speedup не заявляется.

Все409файлов прежнего выпуска,151старый forecast NPZ и cache/panel сохранены; rollback snapshot создан до изменений. Независимый reviewer перепроверяет official metrics и replay экспериментальных весов, source fixtures и temporalcatalog. Его заключение — `independent_verification.md`; финальные hashes и разделение production/experimental — `release_manifest.json`.

## Воспроизведение и защита

Команды из D:/SberTech, последовательно:

```powershell
.venv/Scripts/python.exe -X utf8 integration/source_audit/verify_source_fixtures.py
.venv/Scripts/python.exe -X utf8 -m pytest integration/test_catalog_policy.py integration/test_ensemble_engine.py -q
.venv/Scripts/python.exe -X utf8 integration/run_experiments.py
.venv/Scripts/python.exe -X utf8 integration/analyze_results.py
.venv/Scripts/python.exe -X utf8 integration/independent_verify.py
.venv/Scripts/python.exe -X utf8 integration/train_experimental_final.py
.venv/Scripts/python.exe -X utf8 integration/package_experimental.py
.venv/Scripts/python.exe -X utf8 integration/release/experimental180/verify_standalone.py
.venv/Scripts/python.exe -X utf8 integration/release_probe.py
powershell -NoProfile -ExecutionPolicy Bypass -File integration/docker_verify.ps1
.venv/Scripts/python.exe -X utf8 integration/finalize_reports.py
```

Повторное обучение перезаписывает толькоintegrationмодели/результаты; production не затрагивается. Source fixture требует указанного локального source checkout. Полноценный отрыв от этой машины проверен для productionконтейнера; experimental bundle для inference использует только собственные файлы и входныеCSV, source checkout ему не нужен.

Судьям следует представить работающий проверенный релиз, доказанное исправление temporal feature catalog в экспериментах, честные per-origin tradeoffs и реальный источник postprocessing. Нельзя утверждать «интегрировали два GitHubрешения», «доказали superiority на новомtest», «rounding обязателен», «новый ensemble прошёл API/Docker» или «гарантировали первое место». Техническая воспроизводимость эксперимента и будущая прогнозная точность — разные утверждения.
''')
    write('presentation_pitch_ru.md','''# Материал для защиты

Мы проверили три обучаемые модели и четыре представления прогноза, отделив эффект ансамбля от порога и integer rounding. Исправили future-ID leakage на каждом внутреннем срезе обучения и сохранили полный выходной grid. Реализовали key-based alignment и constrained mixtures, а не произвольный большой ансамбль.

Проверен один внешний Nonton-проект forecast-64-v1; второй не найден. Перенесены независимо реализованные общие fixed-blend и half-even механизмы; исходный защищённый код без лицензии не копировался. Реальная hurdle gate отличается от комментария source, что отдельно раскрыто.

Финальный релиз сохранён как nonton-v1. Экспериментальные результаты и ухудшения доступны по каждому origin; локальные scores не являются обещанием leaderboard. Прежние окна повторно использованы, новогоtest нет. Продемонстрировать следует reproducible experiments и working API/Docker, а не гарантированную будущую точность.

'''+table(comparison.reset_index())+'\n')
    # Package the research implementation and final experimental models, excluding raw data/OOF.
    archive=OUT/'nonton_experimental_verified.zip'
    files=[*sorted((ROOT/'src').glob('*.py')),*sorted((OUT).glob('*.py')),
           ROOT/'scripts/architecture_experiments.py',ROOT/'scripts/qa_analysis.py',
           ROOT/'requirements.lock',ROOT/'requirements-dev.txt',
           *sorted((OUT/'models/final_experimental').glob('*')),
           *sorted((OUT/'source_audit').glob('*.md')),*sorted((OUT/'source_audit').glob('*.py')),*sorted((OUT/'source_audit').glob('*.json')),
           *sorted(OUT.glob('*.md'))]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            if p.is_file():z.write(p,str(p.relative_to(ROOT)))
    release=json.loads((ROOT/'model/manifest.json').read_text(encoding='utf-8'))
    important=[ROOT/'submission.csv',ROOT/'nonton_solution_remediated_verified.zip',ROOT/'model/manifest.json',
               OUT/'release/submission.csv',OUT/'release/pre_integration_snapshot.zip',archive,
               OUT/'models/final_experimental/manifest.json',OUT/'models/final_experimental/config.json',OUT/'executed_protocol.json',OUT/'learned_weights.json']
    manifest=dict(released_model='nonton-v1',production_changed=False,production_bundle_id=release['bundle_id'],
                  experimental_model='nonton-integration-experimental-v1',experimental_promoted=False,
                  successful_historical_fits=15,successful_final_experimental_fits=3,failed_attempts_before_metrics=1,
                  candidate_origin_predictions=215,source_identification=dict(required=2,verified_user_repositories=1,missing_second=True),
                  unresolved=['leaderboard normalization/ties/SMAPE ambiguity','no untouched final test','large experimental categorical bitset artifacts'],
                  files={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in important},
                  release_test_evidence='integration/release_tests.md',independent_evidence='integration/independent_verification.md')
    (OUT/'release_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(quality_screen_passed=len(passed),production='nonton-v1',archive_bytes=archive.stat().st_size),ensure_ascii=False))
if __name__=='__main__':run()
