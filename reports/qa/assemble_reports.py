"""Assemble Russian QA reports strictly from executed evidence."""
import ast
import csv
import difflib
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/qa'


def read(name):return json.loads((OUT/name).read_text(encoding='utf8'))
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(name,content):(OUT/name).write_text(content.strip()+'\n',encoding='utf8')
def table(rows,columns):
    return '\n'.join(['| '+' | '.join(columns)+' |','|'+'|'.join(['---']*len(columns))+'|']+['| '+' | '.join(str(row.get(col,'')) for col in columns)+' |' for row in rows])


def final_report(revision,tree_hash,docker,retraining,corecovered,corelines,corebranchcovered,corebranches):
    return fr'''# Итоговый независимый QA-вердикт: CONDITIONAL PASS

Проверка выполнена 18 октября 2026 года в `D:\SberTech`. Principal QA Architect — root. Реально участвовали три нативных независимых ревьюера: `metrics_audit`, `leakage_audit`, `backend_audit`. Production-исправления интегрировал только root.

## Ревизия и решение

В Git ещё нет коммитов: HEAD отсутствует, исходные файлы неотслеживаемые. Исходная ревизия сохранена в `initial_manifest.json` с SHA256 `{revision['initial_manifest_sha256']}` и восстановимом `pre_audit_snapshot.zip`. Финальное дерево исходников имеет SHA256 `{tree_hash}`; точный состав указан в `revision.json`.

Проверены `src`, `app`, `scripts`, `tests`, Docker и зависимости, оригинальный scorer, реальные CSV продаж и остатков, конфигурация и веса модели, 31 OOF-прогноз. Карта зависимостей и точные границы проверки находятся в `code_audit.md` и `dependency_map.json`. Заявления о ручном чтении каждой строки нет.

Подтверждённых P0 не выявлено. Исправлен P1: неизвестный тип bundle проходил загрузку и мог объявляться готовой моделью. Исправлены пять групп P2: повреждённые записи CSV, переполнение числового диапазона, нестрогие offline-даты и пустые ID, неверная форма прогноза, переставленный каталог. Механизмы, воспроизведения и статусы всех находок — в `defects.csv`.

Открытых P1 нет. Метрики и backend получили независимый PASS; ML/temporal — CONDITIONAL PASS из-за оставшихся ограничений артефактов. **Общий CONDITIONAL PASS относится к фиксированному конкурсному каталогу и проверенному окружению.** Полный PASS удерживают перечисленные ниже ограничения доказательств, воспроизводимости и покрытия. Пригодность для автоматических закупок не заявляется.

## Исполненные проверки

До изменений основной набор дал **68 passed**. После добавления регрессий — **98 passed, 0 failed, 0 skipped**. Отдельный независимый backend-набор дал **21 passed, 0 failed, 0 skipped**. Временной аудит выполнил 11 успешных групп проверок. Независимо пересчитаны все 31 OOF; 18 baseline-прогнозов и три выбранных LightGBM OOF воспроизведены точно. Повторные 13 metric-тестов входят в основной набор и не считаются дополнительными уникальными тестами.

Все Python-команды запускались через `.venv/Scripts/python.exe -X utf8`. Основные исполненные команды:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_qa_regressions.py -q
.\.venv\Scripts\python.exe -X utf8 -m pytest reports/qa/check_backend_independent.py -q
.\.venv\Scripts\python.exe -X utf8 reports/qa/check_metrics_independent.py
.\.venv\Scripts\python.exe -X utf8 reports/qa/check_temporal_independent.py
.\.venv\Scripts\python.exe -X utf8 scripts/qa_analysis.py
.\.venv\Scripts\python.exe -X utf8 scripts/qa_stock_integrity.py
.\.venv\Scripts\python.exe -X utf8 scripts/qa_verify_submission.py
.\.venv\Scripts\python.exe -X utf8 scripts/qa_retrain.py
```

Команды coverage и результаты — `test_runs.json`, `coverage_summary.txt`, `final_pytest.txt`; Docker-команды — `reviewer_backend.md`. Основной набор сочетает синтетические данные, mocks и маленькие обученные модели. Отдельные проверки используют настоящие сохранённые веса и полный реальный вход через HTTP. Ошибки первоначальных воспроизводителей и неверная предпосылка ревьюера о числе наблюдавшихся ID раскрыты в отчётах, успешными тестами они не объявлены.

В `src`/`app` покрыто {corecovered}/{corelines} строк ({100*corecovered/corelines:.2f}%) и {corebranchcovered}/{corebranches} ветвей ({100*corebranchcovered/corebranches:.2f}%). Общее покрытие с CLI ниже; его нельзя подменять процентом основного кода. Полный orchestration-скрипт не запускался с перезаписью рабочих артефактов.

Вместо этого изолированно повторены **все шесть полных обучений**: L2 и Tweedie на первых двух folds, выбранная holdout-модель и финальная модель, по 220 деревьев. Все файлы весов побитово совпали с исходными; финальная конфигурация также совпала. Обучение и проверки заняли {retraining['seconds']:.3f} с, измеренный пик RSS — {retraining['peak_process_rss_bytes']:,} байт. Независимый ревьюер дополнительно проверил реальные файлы и hashes. Результат — `retraining_reproduction.json`, копии весов — `retrained/`. Рабочие веса не заменялись.

## Измеренное качество

Единственный holdout: origin **2026-05-28**, факты **2026-05-29–2026-07-31**, 64 дня, 8 789 рядов. Два предыдущих окна использовались для выбора модели: 2026-01-21–2026-03-25 и 2026-03-26–2026-05-28.

| Метрика | Holdout |
|---|---:|
| Официальный SMAPE | 158.687162% |
| Глобальный WAPE | 80.430066% |
| Глобальный RMSE | 0.866284 |
| Официальный абсолютный Bias по рядам | 80.565557% |
| Глобальный RMSLE | 0.312615 |

Официальный Bias равен среднему `100 * abs(sum(pred_s) - sum(actual_s)) / abs(sum(actual_s))` по рядам с ненулевым фактом. Участвуют **7 752** ряда, исключены **1 037**. Средний signed Bias по рядам — **−62.834934%**; глобальный signed Bias по объёму — **−19.105414%**. Это отдельные диагностические величины. Медиана и 75/90/95-й процентили абсолютного Bias равны 100%; завышение наблюдается у 16.17647% eligible-рядов, занижение — у 83.82353%.

Разрезы складов, категорий, регулярности, исторического объёма и stockout приведены в `bias_analysis.md` и `bias_segments.csv`. Крайние ряды обозначены только хешированными ID. Из-за анонимизации и преобразований эти проценты нельзя считать денежным или физическим отклонением запасов компании.

**Изменения QA не изменили ни одну из пяти метрик: Δ = 0.** TSB на том же holdout имеет SMAPE 178.51910%, WAPE 88.28437%, RMSE 0.872480, Bias 66.14748%, RMSLE 0.305562. Tweedie лучше по первым трём метрикам и хуже по Bias/RMSLE. Порог 0.25 также ухудшает Bias относительно исходного Tweedie-кандидата на selection. Эти компромиссы сохранены, улучшение точности не заявляется.

Локальный minmax-score 0.838184 не является баллом будущего рангового leaderboard. При замене minmax на rank на тех же кандидатах первых двух folds меняется победитель. Это раскрыто в `metrics_parity.md`; повторный выбор по открытому holdout не проводился.

Для дней 1–14 holdout получены RMSE 0.816197 и Bias 78.92695%; для дней 36–64 — RMSE 0.892771 и Bias 84.55236%; для дней 57–64 — RMSE 0.900818 и Bias 85.45525%. Все формулы и eligible-ряды пересчитаны отдельно на каждом диапазоне. Отсутствие рекурсивной подачи прогнозов не гарантирует точность дальнего горизонта. Все пять диапазонов и три folds представлены в `horizon_analysis.md`; графики построены из вычисленных данных.

Для intermittent-рядов с исторической частотой продаж <0.1: WAPE **102.97758%**, абсолютный Bias **101.22774%**, средний signed Bias **−97.18667%**. Для регулярных рядов Bias 59.66749%, для верхних 10% по историческому объёму — 24.32111%. Сильное занижение редкого спроса остаётся измеренным риском качества. Устойчивое преимущество на множестве независимых holdout не доказано.

## API, Docker и submission

Финальный Docker image: `{docker['image_id']}`, размер **{docker['image_bytes']:,} байт**. На полном очищенном реальном входе с `--network none`, 6 GiB и четырьмя CPU: POST **{docker['post_seconds']:.3f} с**, повтор **{docker['repeat_post_seconds']:.3f} с**, GET CSV **{docker['get_csv_seconds']:.3f} с**, GET JSON **{docker['get_json_seconds']:.3f} с**. Пик cgroup — **{docker['memory_peak_bytes']:,} байт**, RSS сервера — {docker['server_peak_rss_bytes']:,} байт. Все фактически проверенные ресурсные лимиты соблюдены. Время первоначальной no-cache сборки и финальной сборки с cache раскрыто раздельно.

Все ключи и quantities JSON/CSV проверены. Максимальное расхождение offline/API — **{docker['max_abs_difference']:.3g}**, допуск `atol=1e-7`, `rtol=0`. Повторный POST и GET CSV байтово идентичны. Проверены ошибки, конкурентные запросы, сохранение cache после отказа, restart и отказ старта без модели. Контейнер аудитора удалён, image сохранён.

Submission содержит **562 496 строк**, 64 даты **2026-08-01–2026-10-03**, ровно четыре требуемые колонки и полный grid 11 × 799. Пропусков ключей, лишних ключей, дублей, NaN, infinity и отрицательных quantities нет. Проверены порядок, повторное чтение CSV с диска и полное равенство множества ключей.

В истории наблюдались 8 777 из 8 789 пар. Оставшиеся 12 получили по 64 явных прогноза модели; после порога они нулевые. Пропущенные output keys не заполнялись молча. Свежий `reports/qa/submission_verified.csv` точно совпал с исходным `submission.csv` после одинаковой сериализации. Исходные веса, конфигурация, каталог и submission сохранили hashes. Фактическая отправка организаторам и публикация не выполнялись.

## Оставшиеся ограничения

- **P2:** отсортированное содержимое каталога не связано fingerprint с весами. Текущий bundle согласован; ошибочная ручная подмена другим отсортированным ID пока не выявляется loader.
- **P2:** при смене исходных файлов cache требует документированный `--refresh`. NPZ OOF не содержат самодостаточных ключей/provenance. Текущие cache и OOF независимо сверены с raw-данными.
- **P2:** часть CLI-ветвей и полный orchestration `run_pipeline.py` после fixes не исполнены целиком; все его реальные обучения и основные пути данных/инференса повторены отдельно.
- ТЗ и scorer расходятся на zero/zero SMAPE: обязательный fixture даёт 50% по написанной формуле и 200% по scorer. Равные rank-метрики зависят от порядка участников. Полный grid и 180 дней включительно остаются явно описанными интерпретациями.
- Есть один holdout; каталог первого fold содержит шесть ID, появившихся позже. Будущие quantities/stock не используются. Допущения об очистке stock и нулевых пропусках sales не подтверждены владельцем. Равенство полной и 180-дневной истории не универсально.
- **P3:** системные бинарники/base image не закреплены digest; побитовая пересборка в другой день не доказана. Структурированное логирование неполное. Проверенная архитектура использует один worker.

Будущие Bias и все пять метрик для submission: **NOT MEASURABLE** — факты после 2026-07-31 отсутствуют. Конкурсный ранг и бизнес-эффект неизвестны. Корректностные исправления приняты; новый поиск моделей без нового протокола проверки не проводился.

## Файлы результата

Все десять обязательных отчётов находятся в `reports/qa`: `code_audit.md`, `defects.csv`, `metrics_parity.md`, `bias_analysis.md`, `leakage_audit.md`, `horizon_analysis.md`, `api_test_results.md`, `docker_benchmarks.md`, `before_after_comparison.md`, `final_qa_verdict.md`.

Там же находятся независимые `reviewer_*.md`, JSON измерений, coverage, diff и manifests. Проверенный прогноз — `reports/qa/submission_verified.csv`; рабочая модель — `model/lightgbm.txt`; воспроизведённые веса — `reports/qa/retrained/`. Актуальный архив — `nonton_solution_qa_verified.zip`. Первоначальный `nonton_solution.zip` сохранён.
'''


def main():
    docker=read('docker_benchmark.json');retraining=read('retraining_reproduction.json')
    analysis=read('analysis_summary.json');stock=read('stock_integrity.json');fresh=read('fresh_inference.json')
    metrics=read('metrics_independent.json');coverage=read('coverage.json');catalog=read('catalog_grid_audit.json')
    assert docker['status']=='passed' and retraining['passed']==6
    assert all(row['model_bytes_identical'] for row in retraining['fits'])
    assert fresh['original_submission_max_abs_difference']==0
    assert '98 passed' in (OUT/'final_pytest.txt').read_text(encoding='utf-16')
    # PowerShell's redirection produces UTF-16 logs; reports and code use UTF-8.
    manifest={key.replace('\\','/'):v for key,v in read('initial_manifest.json').items()}
    source_paths=sorted([p for folder in ['app','src','scripts','tests','model'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[ROOT/name for name in ['README.md','Dockerfile','.dockerignore','requirements.txt','requirements-dev.txt','requirements.lock']])
    source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in source_paths}
    tree_hash=hashlib.sha256(''.join(f'{key}\t{value}\n' for key,value in sorted(source_hashes.items())).encode()).hexdigest()
    revision={'git_head':None,'git_state':'unborn HEAD; no commits, original files untracked',
              'initial_manifest_sha256':sha(OUT/'initial_manifest.json'),
              'pre_audit_snapshot_sha256':sha(OUT/'pre_audit_snapshot.zip'),
              'final_source_tree_sha256':tree_hash,'source_hashes':source_hashes}
    write('revision.json',json.dumps(revision,ensure_ascii=False,indent=2))
    changes=[]
    with zipfile.ZipFile(OUT/'pre_audit_snapshot.zip') as archive:
        for path in source_paths:
            name=path.relative_to(ROOT).as_posix()
            old=manifest.get(name,{}).get('sha256')
            if old!=source_hashes[name]:
                changes.append({'path':name,'status':'added' if old is None else 'modified','before_sha256':old,'after_sha256':source_hashes[name]})
        diff=[]
        for row in changes:
            name=row['path']
            before=archive.read(name).decode('utf8').splitlines(True) if name in archive.namelist() else []
            after=(ROOT/name).read_text(encoding='utf8').splitlines(True)
            diff.extend(difflib.unified_diff(before,after,fromfile='before/'+name,tofile='after/'+name))
    write('changes.diff',''.join(diff))
    write('changed_files.json',json.dumps(changes,indent=2))
    defects=[
        dict(id='QA-001',severity='P2',path='app/validators.py; src/data.py',function='validate_history; build_panel',mechanism='finite float64 превращается в inf при float32 cast либо после sales aggregation',reproduction='pytest tests/test_qa_regressions.py::test_panel_rejects_float32_overflow; ::test_panel_rejects_aggregation_overflow',expected='422 для API либо ValueError offline до model inference',observed_before='1e40 sales/stock и две записи 2e38 дают inf panel; отказ отсутствует',fix='Проверка конечного диапазона до cast и после суммы; API 422 до инференса',status='FIXED; main regression + независимый backend + real Docker'),
        dict(id='QA-002',severity='P2',path='app/validators.py',function='read_csv',mechanism='strict csv.reader проверял лишь header; pandas дополнял недостающие поля и принимал часть сломанных кавычек',reproduction='pytest reports/qa/check_backend_independent.py -q; tests/test_qa_regressions.py::test_csv_body_structure_is_strict',expected='400 VALIDATION_ERROR для структурно сломанного CSV',observed_before='HTTP200 на усечённом metadata-поле; independent16pass4fail',fix='strict csv.reader всего тела, одинаковая ширина записей; legal quoted newline/explicit empty cells разрешены',status='FIXED; independent21pass и malformed real Docker400'),
        dict(id='QA-003',severity='P2',path='src/data.py',function='build_panel',mechanism='pandas format допускает 2025-1-1; пустые/пробельные keys проходили offline',reproduction='pytest tests/test_qa_regressions.py::test_offline_requires_strict_date_format; ::test_offline_rejects_empty_identifier',expected='Строгие YYYY-MM-DD и непустые ID',observed_before='Нестрогая дата и пустые ключи приняты',fix='Regex для строк, midnight для datetime, проверка empty IDs',status='FIXED; root и independent temporal checks'),
        dict(id='QA-004',severity='P1',path='src/predict.py',function='load_bundle',mechanism='unknown kind проходил загрузку без реальной модели, readiness мог объявляться раньше неизбежного inference failure',reproduction='pytest tests/test_qa_regressions.py::test_unknown_model_kind_fails_at_load',expected='Неподдерживаемый bundle отклоняется при загрузке',observed_before='kind=typo возвращал bundle без model',fix='Whitelist kind/baseline, finite nonnegative threshold, структура каталога',status='FIXED; root + independent temporal; valid real artifact/Docker startup verified'),
        dict(id='QA-005',severity='P2',path='src/submission.py',function='forecast_frame',mechanism='flatten принимал неверные оси при совпадающем числе элементов, переставляя quantities по ключам',reproduction='pytest tests/test_qa_regressions.py::test_forecast_rejects_wrong_axes_with_correct_element_count',expected='Только shape (64, warehouse_count * article_count)',observed_before='(2,64) принят вместо (64,2)',fix='Явный shape guard до построения grid',status='FIXED; root+independent temporal; actual production grid correct before/after'),
        dict(id='QA-006',severity='P2',path='src/predict.py',function='load_bundle',mechanism='Перестановка ID каталога меняла categorical mapping без ошибки feature schema',reproduction='pytest tests/test_qa_regressions.py::test_bundle_rejects_reordered_categorical_mapping; temporal checker',expected='Порядок training encoder должен сохраняться',observed_before='Подменённый переставленный каталог принят',fix='Sorted order проверяется согласно catalog_from_sales',status='FIXED permutation case; residual fingerprint QA-007'),
        dict(id='QA-007',severity='P2',path='src/predict.py; model/catalogs.json',function='load_bundle',mechanism='Отсортированный чужой каталог не связан fingerprint с весами',reproduction='reports/qa/check_temporal_independent.py::artifact_catalog_remap_reproduction',expected='При export сохраняется ordered catalog hash; loader сверяет его',observed_before='Изменённый sorted ID принят; текущие реальные catalogs проверены и согласованы',fix='Будущее версионированное добавление catalog/model hash в export без переобучения деревьев',status='OPEN limitation; текущий bundle verified; не подтверждённая порча текущих прогнозов'),
        dict(id='QA-008',severity='P2',path='scripts/run_pipeline.py; src/data.py',function='run; load_panel',mechanism='Существующий cache используется без fingerprint сравнения с --data-dir',reproduction='run_pipeline.py выбор prepare_cache только при --refresh или отсутствии cache/panel.npz; README явно требует --refresh',expected='При замене исходных файлов cache обновлён либо provenance проверена',observed_before='Новый data-dir игнорируется при existing cache без --refresh',fix='Использовать документированный --refresh; последующее manifest-based cache invalidation',status='OPEN documented operational limitation; cache текущего набора независимо восстановлен и verified'),
        dict(id='QA-009',severity='P2',path='scripts/run_pipeline.py; reports/oof',function='record',mechanism='NPZ содержит prediction/origin без явных ключей и hash catalog/truth/model',reproduction='check_metrics_independent.py инспекция всех31 NPZ; фактические ключи восстановлены по verified catalogs и baseline reproduction',expected='Самодостаточный provenance manifest OOF',observed_before='Самостоятельно перенесённый NPZ не доказывает alignment',fix='Добавлять keyed/hashes manifest в следующем export',status='OPEN portability limitation; current31 OOF independently aligned and verified'),
        dict(id='QA-010',severity='P2',path='scripts/run_pipeline.py; reports/selection_frozen.json',function='ranking',mechanism='Выбор по local minmax чувствителен к ожидаемому rank evaluator',reproduction='check_metrics_independent.py rank sensitivity на тех же12 кандидатах folds1/2',expected='Критерий и влияние нормализации явно раскрыты; новый выбор требует нового protocol',observed_before='minmax winner Tweedie z0.25; rank winner L2 z0.25',fix='Раскрыто в metrics_parity и final verdict; frozen choice сохранён; holdout не переоткрывается для оптимизации',status='DOCUMENTED methodological limitation; official code supports both modes'),
        dict(id='QA-011',severity='P3',path='scripts/official_score.py',function='normalize_rank',mechanism='argsort даёт разные ранги равным значениям, зависит от порядка участников',reproduction='pytest tests/test_qa_regressions.py::test_rank_ties_reproduce_original_evaluator_order_dependence',expected='Точно воспроизвести supplied evaluator и раскрыть странность',observed_before='Два одинаковых участника получают0 и1',fix='Оригинальный scorer сохранён; поведение документировано и regression-tested',status='DOCUMENTED upstream evaluator behavior'),
        dict(id='QA-012',severity='P3',path='app/main.py; Dockerfile',function='observability; build',mechanism='Нет специальных request/coverage structured logs; базовый image tag/apt меняются со временем',reproduction='code review и image inspection reviewer_backend.md',expected='Не обещать byte-identical rebuild на других датах/бинарниках',observed_before='Поведение текущей среды воспроизведено; будущие системные builds не фиксированы',fix='Рассмотреть base digest/system pinning и structured observability отдельно',status='OPEN noncritical operational limitation'),
    ]
    with (OUT/'defects.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(defects[0]));writer.writeheader();writer.writerows(defects)

    modules=[]
    for folder in ['src','app','scripts','tests']:
        for path in sorted((ROOT/folder).glob('*.py')):
            tree=ast.parse(path.read_text(encoding='utf8'))
            imports=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):imports.append('.'*node.level+(node.module or ''))
                elif isinstance(node,ast.Import):imports.extend(n.name for n in node.names)
            functions=[node.name for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
            modules.append({'path':path.relative_to(ROOT).as_posix(),'lines':len(path.read_text(encoding='utf8').splitlines()),'imports':', '.join(sorted(set(imports))),'entry_functions':', '.join(functions)})
    write('dependency_map.json',json.dumps(modules,ensure_ascii=False,indent=2))
    corefiles=[v for key,v in coverage['files'].items() if key.replace('\\','/').startswith(('app/','src/'))]
    corelines=sum(v['summary']['num_statements'] for v in corefiles); corecovered=sum(v['summary']['covered_lines'] for v in corefiles)
    corebranches=sum(v['summary']['num_branches'] for v in corefiles);corebranchcovered=sum(v['summary']['covered_branches'] for v in corefiles)
    write('test_runs.json',json.dumps({'environment':{'python':platform.python_version(),'platform':platform.platform()},
        'baseline':{'command':'.venv/Scripts/python.exe -X utf8 -m pytest -q','passed':68,'failed':0,'skipped':0},
        'final':{'command':'.venv/Scripts/python.exe -X utf8 -m coverage run --append --branch --source=src,app,scripts --data-file=reports/qa/.coverage -m pytest -q','passed':98,'failed':0,'skipped':0},
        'independent_backend':{'command':'.venv/Scripts/python.exe -X utf8 -m pytest reports/qa/check_backend_independent.py -q','passed':21,'failed':0,'skipped':0},
        'independent_temporal':{'command':'.venv/Scripts/python.exe -X utf8 reports/qa/check_temporal_independent.py','passed_assertion_groups':11,'failed':0,'skipped':0},
        'independent_metrics':{'command':'.venv/Scripts/python.exe -X utf8 reports/qa/check_metrics_independent.py','verified_oof_files':31,'failed':0},
        'isolated_fits':{'command':'.venv/Scripts/python.exe -X utf8 scripts/qa_retrain.py','passed':6,'failed':0,'skipped':0},
        'coverage_core':{'covered_lines':corecovered,'lines':corelines,'covered_branches':corebranchcovered,'branches':corebranches},
        'coverage_all_instrumented':coverage['totals']},ensure_ascii=False,indent=2))

    write('code_audit.md',f'''# Аудит кода и карта исполнения

Дата 18.10.2026; Principal QA Architect — root, единственный интегратор production-исправлений. Реально работали независимые Agent A metrics_audit, Agent B leakage_audit, Agent C backend_audit. Использованы нативные subagents; дополнительный AI-model override не задавался и наличие иных моделей не заявляется.

Git HEAD отсутствует: репозиторий без коммитов, все исходные файлы untracked. Исходная ревизия — initial_manifest.json, SHA256 `{revision['initial_manifest_sha256']}`; восстановимый код/модели — pre_audit_snapshot.zip. Все старые OOF, CSV, результаты и исходные данные сохранены; список SHA до изменений включает99 файлов. Аудированное финальное дерево: `{tree_hash}`; состав — revision.json. SHA рабочих весов, конфигурации, каталога и исходного submission не изменены.

## Источники и исполнение

Сначала прочитано оригинальное markdown ТЗ; встроенный scorer извлечён и дословно/AST совпал с scripts/official_score.py. Реальные CSV прочитаны и независимо реконструированы; backend DOCX разобран zip/XML. Затем проверены код/config/артефакты/старые отчёты. Противоречия SMAPE, full grid против observed pairs, отсутствующие cost_price/volume_weight и inclusive180 описаны явно. DOCX не подменяет организаторское ТЗ. Данные не отправлялись внешним AI; сеть использовалась для официальной документации и установки QA-зависимостей.

Тренировка: run_pipeline → prepare_cache/load_panel → read_inputs → clean_stock → build_panel → training_data → snapshot/horizon_features → train_model → lgb.Dataset/train → save_model/config/catalog. Кандидаты L2/Tweedie с220trees и thresholds0/.25/.5 сравниваются на одинаковых folds1/2; frozen JSON записывается до holdout; final refit использует всю допустимую историю.

Инференс: scripts/predict.py либо HTTP POST → общий predict_64 → build_panel фиксированного каталога → predict_panel → snapshot только до origin → horizon_features известных будущих дат →8 batch по8 горизонтов → LightGBM → finite/nonnegative/threshold → forecast_frame → validate_submission. Ни один forecast не подаётся обратно в lag.

HTTP путь: UploadFile → strict CSV → validate_history → post_lock → Predictor.predict → проверка full grid → атомарная публикация cache → StreamingResponse. GET удерживает завершённый snapshot. Cache живёт в RAM одного worker и пропадает после restart. Docker копирует только runtime source/model/lock, train не требуется.

Модель зависит от ordered feature list, ordered catalogs, horizon64, schema1 и текстовых весов. Loader проверяет schema/kind/threshold/order/uniqueness/features. Отсортированная замена содержимого каталога пока не привязана fingerprint к весам; это residual P2, не текущая порча bundle.

## Независимая проверка данных

Sales1,492,370 строк →970,677 aggregated keys, панель943×8789 точно совпала с raw; quantity total1,826,791. Департаменты суммируются, join со stock не используется для умножения строк. Все943 sales даты есть в источнике. Из всех8789 required pairs наблюдались8777, остальные12 отдельно проверены: каждый имеет64 прогнозов, все0 после фактического inference/threshold, а не заполнения отсутствующих output keys. Полный grid chosen по фиксированному числу562496; неоднозначность прозы ТЗ раскрыта.

Stock{stock['raw_rows']:,} строк, negative{stock['negative_rows']}, conflicting keys{stock['raw_conflicting_keys']:,}; после удаления negatives конфликтных ключей{stock['conflicts_after_negative_removal']:,}, clean unique keys{stock['clean_unique_keys']:,}. Независимые min/max по ключам воспроизвели clean policy и cache stock побитово. Missing stock=NaN отличается от0. Это допущение очистки неоднозначных данных, не восстановленная истинная величина запасов.

Категории по реальному train: конфликтующих article на каждом из levels1/2/3 —0; отсутствующие категории допустимы. Для segmented diagnostics категории определялись только по истории fold. Missing sales=0 — явно принятое event-export допущение; истинный скрытый спрос не измерен.

## Полнота обхода и coverage

Статическая карта imports/entrypoints всех first-party .py: dependency_map.json. Команда inventory: `rg --files` с исключением venv/cache/binaries; источники читались с Get-Content UTF8 и Python AST. Root и reviewers трассировали data→training/inference→API и вспомогательные CLI. Не заявляется ручная проверка каждой строки новых и старых скриптов. Third-party/venv и бинарные NPZ вручную построчно не читались; NPZ проверены программно. CI-конфигурация в дереве не обнаружена.

Покрытие core src/app: statements{corecovered}/{corelines} ({corecovered/corelines*100:.2f}%), branches{corebranchcovered}/{corebranches} ({corebranchcovered/corebranches*100:.2f}%). Полный инструментированный набор src/app/scripts имеет отдельное coverage.json и coverage_summary.txt: CLI-обёртки сильно снижают общий процент. Coverage записывалась для main tests, real OOF/temporal/backend, свежего инференса и шести full fits; часть QA/CLI запусков сделана до включения scripts в coverage и не должна трактоваться как неисполненная только по0%.

Риск непокрытых ветвей: HIGH — run_pipeline orchestration/cache refresh целиком не запускалась, чтобы не перезаписывать лучшие результаты; вместо этого отдельно повторены все6 реальных fits и pipeline transformations. MEDIUM — prepare_cache при смене источника, исходные audit/packaging wrappers, baseline-only bundle route, некоторые invalid schema branches. LOW — empty streaming frame и malformed internal alias branches. Dead-code выводы не делались: baseline/train/finalize CLI используются README, хотя не являются runtime API.

## Инвентарь модулей

{table(modules,['path','lines','entry_functions','imports'])}

Реестр всех находок с механизмом, воспроизведением, severity, ожидаемым/наблюдавшимся поведением и статусом: defects.csv. Полные независимые выводы: reviewer_metrics.md, reviewer_leakage.md, reviewer_backend.md.
''')

    write('metrics_parity.md',f'''# Паритет официальных метрик

Источники: оригинальное ТЗ раздел9.2 и неизменённый scripts/official_score.py; normalized SHA256 `{metrics['scorer_sha256_normalized']}`. Дословное совпадение и AST подтверждены независимым reviewer. Подробный протокол — reviewer_metrics.md, машинные факты — metrics_independent.json.

SMAPE: внутри ряда среднее только по days с `(abs(actual)+abs(pred))/2 >0`; затем равное среднее по рядам. Полностью zero/zero ряд даёт0. Написанная формула сохраняет zero/zero как0; fixture actual[0,0,0,10],pred[0,0,0,0] даёт written50%, evaluator200%. Оба варианта реализованы и протестированы отдельно.

WAPE:100*sum(abs(error))/sum(abs(actual)); zero denominator→0 по scorer. RMSE:sqrt(mean(error²)) globally. RMSLE:sqrt(mean((log1p(pred)-log1p(actual))²)) globally. Истинные значения должны быть конечными и неотрицательными. Массивная production metric функция намеренно повторяет official NaN prediction→0 и negative prediction→0; бесконечности отклоняются. Output submission/API отдельно отвергает NaN/Inf/negative и не полагается на scorer sanitization.

Bias: отдельно100*abs(sum(pred_s)-sum(actual_s))/abs(sum(actual_s)), затем среднее eligible рядов. Actual total0 исключается; когда все исключены, scorer fallback0 является неинформативным. Epsilon не добавляется. Обязательный fixture A[0,10]→[0,8]:20% и signed−20%; B[2,2]→[4,4]:100% и signed+100%; C[0,0]→[1,1] исключается. Среднее60%, signed mean40%, global signed28.5714286% с учетом прогноза C. Fixtures perfect/over/under/allzero/tiny positive/low-volume over/same totals/different pattern/order/NaN/Inf/missing duplicate keys включены в26 root QA regressions и independent scripts.

Все31 saved OOF пересчитаны независимой реализацией из raw-reconstructed truth. max abs deviation пяти метрик/score5.684341886080802e-14; tolerance1e-10. Supplied keyed scorer дополнительно исполнялся на идентичных синтетических ключах и6 реальных рядах каждого OOF; не утверждается, что медленный scorer31раз запускался на всём grid. Все6 baseline на3fold воспроизведены побитово, OOF alignment подтверждён catalog/даты/реальными prediction paths. Missing/duplicate submission keys отдельно отклоняются stronger submission validator по полному grid.

Minmax:ideal0,baseline1,clip worse→1,zero base:value0→0 иначе1. Metric weights50/20/15/10/5%; weighted score применяется после нормировки. Rank:argsort ranks0..N−1, деление наN−1; singleton0. Равные значения получают разные ranks и зависят от порядка submissions; это унаследованное поведение evaluator, оригинал сохранён.

ТЗ ожидает rank, хотя code/default поддерживает minmax. Текущий frozen selection использует честно обозначенный local minmax: Tweedie z.25 mean .8323826469 против L2 z.25 .8337666652. На тех же12 кандидатах rank чувствительность предпочитает L2 z.25 .20681818 против Tweedie .22727273. Официальный leaderboard неизвестен, его балл не заявляется; повторная оптимизация по открытому holdout не проводилась.

Signoff Agent A:PASS после root validation fixes,13 metric tests прошли повторно, все14 Bias diagnostics×3fold независимо подтверждены. Обнаруженных численных defects метрик нет. Остались upstream SMAPE prose/code и rank ties discrepancies; они не скрыты исправлением scorer.
''')

    write('leakage_audit.md',f'''# Временная корректность и воспроизводимость обучения

Независимый reviewer B:11 PASS/0FAIL/0SKIP. Команда: `.venv/Scripts/python.exe -X utf8 reports/qa/check_temporal_independent.py`; протокол reviewer_leakage.md. Проверены actual execution: append future sales/stock при фиксированном cutoff, изменение future labels/stock, shuffle, origin+h boundaries, train/inference feature parity, известный будущий календарь и leap-year, равные сериализованные tiny parameters после future perturbation, реальные fixed-origin predictions.

snapshot сначала срезает y/stock до origin. Все training origins<=cutoff−64; horizons[1,7,14,21,28,42,56,64], label=origin+h<=cutoff. Direct forecast использует history<=origin и известный календарь, не future realized stock/sales и не предыдущие predictions. Stock conflicts решаются внутри дневного ключа, future append не меняет past aggregate. Current fixed catalogs предоставляются явно. Обнаруженной target leakage нет в проверенном объёме.

Выбор модели:fold1 origin2026-01-20,fold2 2026-03-25,holdout origin2026-05-28. Frozen objective/threshold/220trees выбраны на первых двух окнах; holdout2026-05-29–2026-07-31 не использован в коде для выбора. Независимого журнала прежних ручных действий нет; воспроизводимое сохранённое решение подтверждено повтором, невозможные исторические гарантии не заявляются.

Реальные18 baseline OOF и3 выбранные Tweedie OOF воспроизведены точно. Дополнительно root `scripts/qa_retrain.py` заново обучил6 frozen configurations: все model txt SHA256 совпали побитово с original artifacts;6pass0fail0skip. Время{retraining['seconds']:.3f}s, peak sampled process RSS{retraining['peak_process_rss_bytes']:,}bytes,4threads. L2/Tweedie selection fits,holdout и final включены; все220trees. Final config совпал полностью. Финальный raw prediction против CSV%.10g maxdiff4.9918806865889565e-09<1e-7, OOF differences0. Рабочие model/config/catalog/submission не перезаписывались. Нового поиска параметров и изменения решений не было. Records: retraining_reproduction.json; веса-копии: retrained/.

Ограничение ID catalog: в первом fold наблюдались793 из799 article, в последующих799; warehouses11 везде. Fixed catalog передаёт пространство6future-only ID на fold1, что является transductive catalog knowledge, а не будущими quantities. Полный каталог обусловлен fixed-grid competition; open-catalog production этим backtest не проверен. Глобально неизвестные ID отклоняются API.

Длина входа: long_mean зависит от всей истории; остальные demand/stock признаки ограничены180 днями. Full против180days: fold1 отличается1408/562496 predictions,maxdiff0.2565485553;fold2 2855,maxdiff0.2546888064;fold3 exact equal. Поэтому нельзя обобщать совпадение holdout на все входы. Exact offline/API parity проверяется при одинаковой истории.

Остались P2 provenance ограничения: sorted foreign catalog ID не привязан hash к model; NPZ без полных ключей/hash; cache требует --refresh при замене исходников. Текущие mappings/cache/OOF независимо согласованы. Финальный temporal signoff — CONDITIONAL PASS; все root fixes приняты reviewer. Первоначальная ложная предпосылка reviewer о799 observed на первом fold дала9pass1fail и честно исправлена измерением793/799/799, не подгонкой production.
''')

    write('api_test_results.md',f'''# Проверка API и надёжности

Оригинальные68 tests PASS; финальные main tests98PASS/0FAIL/0SKIP (`final_pytest.txt`). Отдельный independent pytest backend21PASS/0FAIL/0SKIP (`independent_backend_run.txt`), не складывается с повторными13metric tests как с новыми уникальными тестами. Independent concurrent tests используют реальный параллельный HTTP с Event-barrier, а не только ручную блокировку. Полные случаи/команды/среда — reviewer_backend.md.

Проверены POST multipart both files, missing file422, empty/invalid CSV400, missing columns422, strict/bad dates422, minimum180 inclusive days и длинная история, negative/NaN/Inf/non-numeric/unknown ID/stock conflict422, numeric/aggregation overflow422, stock alias, departments aggregation. API errors содержат строковый detail и code; status400/422→VALIDATION_ERROR,404/409/500→REQUEST_ERROR. Поломанное тело CSV до fix давало200, после400. Явно пустая ячейка и quoted newline остаются допустимыми. Before16pass4fail independent→after21pass.

GET /predict article-only/warehouse-only/both дают704/51136/64 строк на официальном catalog; neither400,unknown404, beforePOST409. GET /predict/all CSV и JSON проверены на562496 rows, content types, exact keys и quantities. Invalid format400. /health при реальной загрузке statusok/model_loadedtrue. Недоступная модель вызывает fail startup; отдельный negative Docker test exit1 ожидаем.

Cache/concurrency: identical request deterministic; concurrent identical/different POST→409 при занятом post_lock; GET старого полного snapshot во время compute, атомарная смена после успеха; failed validation/inference/output validation не заменяют cache. Restart real Docker→409. Поддержан1worker; shared multiprocess cache не реализован и не заявляется.

Два уровня данных: unit/concurrency tests используют synthetic model stub, small training tests реальные tiny models; отдельный `check_backend_independent.py --real` загружает genuine LightGBM на контролируемых180days и выдаёт весь grid. Последняя проверка Docker использует полные реальные очищенные CSV и настоящие веса, не mocks: POST{docker['post_seconds']:.6f}s,repeat{docker['repeat_post_seconds']:.6f}s,GETCSV{docker['get_csv_seconds']:.6f}s,GETJSON{docker['get_json_seconds']:.6f}s. Все562496 keys validated; offline maxdiff{docker['max_abs_difference']:.17g},atol1e-7/rtol0,JSON также проверен полностью. Repeat/get CSV bytes identical. Повреждённый CSV через реальный HTTP400,cache сохранён.

Ошибка первого QA Docker probe была в sys.path самого harness, исправлена и прогон повторён; это не production failure и не засчитанный PASS. DeprecationWarning Starlette/httpx остаётся неблокирующим. Signoff Agent C:PASS. Числа и image identification — docker_benchmark.json.
''')

    write('docker_benchmarks.md',f'''# Docker и ресурсы — фактический аудит

Финальный tag `{docker['image_tag']}`, image ID `{docker['image_id']}`, размер{docker['image_bytes']:,}bytes (<30GB). Host: Windows10build19045,16logicalCPUs,{docker['host']['physical_ram_bytes']:,}bytes RAM; Docker Desktop{docker['host']['docker_desktop']}/Engine{docker['host']['docker_engine']}; runtime LinuxWSL2 amd64,Python{docker['python']}. GPU не использовался. Container: --network none,--memory=6g,--cpus=4; memory plus swap limit12GiB отдельно раскрыт в JSON.

No-cache dependency build до финальных source-исправлений{docker['build_seconds_initial_no_cache_before_final_source_repairs']:.6f}s; финальный COPY rebuild с cache{docker['build_seconds_final_cached']:.6f}s. Это разные измерения, не единая чистая сборка финального дерева. Зависимости устанавливались при build; модель никаких downloads при startup/inference не делает. Train/source CSV не входят в image; после старта inputs временно копировались в/tmp и передавались реальным HTTP loopback внутри network-none.

| Операция | Измерение | Лимит |
|---|---:|---:|
| Full real POST | {docker['post_seconds']:.6f}s | 3600s |
| Repeat POST | {docker['repeat_post_seconds']:.6f}s | 3600s |
| GET full CSV | {docker['get_csv_seconds']:.6f}s | 600s |
| GET full JSON | {docker['get_json_seconds']:.6f}s | 600s |
| cgroup memory peak | {docker['memory_peak_bytes']:,}B | 64GB |
| Server sampled peak RSS | {docker['server_peak_rss_bytes']:,}B | описательная метрика |
| CPU process | {docker['server_cpu_seconds']:.2f}CPU-s | 4CPU assigned |
| Probe total wall | {docker['total_probe_wall_seconds']:.6f}s | не равно POST latency |

cgroup включает память probe/сервера/файлового cache; RSS выборочно измерялся каждые0.1s и может пропустить короткий пик. Нет утверждений о другом hardware или RAM на произвольных размерах входа. Вход450MB читается целиком; streaming реализован для выхода. Все лимиты пройдены на фактически проверенном входе.

Exact full Cartesian keys и finite nonnegative quantities проверены. Offline/API maxdiff{docker['max_abs_difference']:.17g}<1e-7; repeated bytes identical. После restart cache409; отсутствующий MODEL_DIR остановил startup exit1 ожидаемо. Контейнер аудитора удалён, финальный image сохранён. Production weights/config/catalog hashes совпали с начальным manifest; runtime source hashes внутри image записаны в docker_benchmark.json и сверены root с рабочим деревом.

LightGBM параметры deterministic=true,force_col_wise=true,seed20261018,num_threads4,version4.7.0 соответствуют [официальной документации](https://lightgbm.readthedocs.io/en/stable/Parameters.html). Она ограничивает гарантию стабильности одинаковыми builds/данными/параметрами; межплатформенная parity здесь отдельно измерена. Системный base tag/apt не pinned by digest, будущая bitwise rebuild не доказана. JSON с точными командами, версиями и измерениями — docker_benchmark.json; протокол — reviewer_backend.md. Signoff:PASS для проверенного окружения.
''')

    write('before_after_comparison.md',f'''# Проверка до и после исправлений

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
''')

    summary_csv=list(csv.DictReader((OUT/'bias_summary.csv').open(encoding='utf8')))
    holdout=summary_csv[-1]
    # Keep generated Russian prose readable even around dynamic values.
    write('final_qa_verdict.md',final_report(revision,tree_hash,docker,retraining,corecovered,corelines,corebranchcovered,corebranches))
    for relative,digest in docker['production_sha256'].items():assert sha(ROOT/relative)==digest,relative
    subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-m','pip','freeze'],stdout=(OUT/'environment_final.txt').open('w',encoding='utf8'),check=True)
    print(json.dumps({'verdict':'CONDITIONAL PASS','source_tree_sha256':tree_hash,'changes':len(changes),'reports':'reports/qa','core_branches':f'{corebranchcovered}/{corebranches}'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
