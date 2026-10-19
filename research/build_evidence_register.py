"""Normalize verified bibliographies, retaining provenance and claim limits."""
import csv
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research'
fields=['source_id','exact_title','authors_or_maintainers','venue_or_owner','year','doi','primary_url','implementation_url','commit','license_status','evidence_type','verification_status','verified_claims','assumptions_and_nonton_differences','nonton_validation_status','access_date','local_evidence']
rows=[]
with (OUT/'science_sources.csv').open(encoding='utf-8-sig',newline='') as f:
    for original in csv.DictReader(f):
        row={k:original.get(k,'') for k in fields}
        row.update(access_date='2026-10-19',local_evidence='research/source_inspection/manifest.json; research/scientific_architectures.md')
        rows.append(row)
with (OUT/'competition_sources.csv').open(encoding='utf-8-sig',newline='') as f:
    for original in csv.DictReader(f):
        url=original['official_url']
        row={k:original.get(k,'') for k in fields}
        row.update(exact_title=original['title'],primary_url=url,doi=url.split('doi.org/')[-1] if 'doi.org/' in url else '',
                   evidence_type='Публичный конкурсный артефакт' if 'github' in url or 'kaggle' in url else 'Первичный исследовательский источник',
                   verification_status=original['reproduction_status'],
                   assumptions_and_nonton_differences=original['assumptions']+'; '+original['nonton_differences'],
                   nonton_validation_status='Внешний результат не устанавливает улучшение Nonton; исходный код прочитан, не обучался',
                   local_evidence='research/source_snapshot_manifest.json; research/competition_solutions.md')
        rows.append(row)
rows.append(dict(source_id='LGB-API',exact_title='Parameters — LightGBM 4.7.0 documentation',authors_or_maintainers='LightGBM maintainers / Microsoft',venue_or_owner='Microsoft/LightGBM',year='2026 (проверенная версия документации)',primary_url='https://lightgbm.readthedocs.io/en/stable/Parameters.html',implementation_url='https://github.com/microsoft/LightGBM',license_status='MIT для библиотеки; права документации проверять отдельно',evidence_type='Официальная документация реализации',verification_status='Документация 4.7.0 открыта; установленная версия 4.7.0; API исполнен',verified_claims='Tweedie objective, deterministic/seed/num_threads; фактические параметры записаны в metadata',assumptions_and_nonton_differences='API совместимость не является доказательством качества',nonton_validation_status='Использована в десяти локальных fits',access_date='2026-10-19',local_evidence='research/environment_and_inputs.json; research/experiment_results.csv'))
for id,title,artifact,claim in [
    ('NONTON-OLD','Повторная проверка прежних 17 кандидатов на пяти окнах','research/diagnostics/','85/85 массивов и метрик повторно проверены; zero-total 5078 подтверждён'),
    ('NONTON-NEW','Архитектурное сравнение weekly volume и article top-down','research/experiment_results.csv','35 полных прогнозов; 10 fits; ни один из 6 режимов не проходит development gate'),
    ('NONTON-REVIEW','Независимая проверка архитектурных экспериментов','research/diagnostics/independent_architecture_review.json','35 scorer checks, 15 побитовых replay, cutoff invariance; 409 release files совпадают'),
]:
    rows.append(dict(source_id=id,exact_title=title,authors_or_maintainers='Локальная исследовательская команда Nonton',venue_or_owner='D:/SberTech',year='2026',license_status='Код независимо реализован; права на исходные данные не расширяются',evidence_type='Nonton-specific validation' if id!='NONTON-REVIEW' else 'Локально воспроизведённая независимая проверка',verification_status='Исполнено на реальной cached panel',verified_claims=claim,assumptions_and_nonton_differences='Повторно использованные окна; нет untouched test; фиксированный каталог',nonton_validation_status='Измерение на Nonton; превосходство релиза не установлено',access_date='2026-10-19',local_evidence=artifact))
assert len({r['source_id'] for r in rows})==len(rows)
for name in ['source_catalog.csv','evidence_register.csv']:
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
for row in rows:
    assert row['exact_title'] and row['verified_claims'] and row['license_status']
print(f'{len(rows)} verified source/evidence records')
