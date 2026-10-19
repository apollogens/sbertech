"""Finalize release findings only after executed API/Docker/reviewer evidence."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from src.predict import load_bundle
from src.artifacts import file_hash


def run():
    out=ROOT/'reports/remediation'
    api=json.loads((out/'backend_fullsize/benchmark.json').read_text())
    docker=json.loads((out/'docker_benchmark.json').read_text(encoding='utf-8-sig'))
    command=json.loads((out/'docker_command_status.json').read_text(encoding='utf-8-sig'))
    review=json.loads((out/'review_docker_artifacts.json').read_text())
    challenge=json.loads((out/'review_challenger_verification.json').read_text())
    suite=ET.parse(out/'final_tests.xml').getroot()[0].attrib
    bundle=load_bundle(ROOT/'model')
    assert api['status']==docker['status']==review['status']==challenge['status']=='passed'
    assert command['exit_code']==0
    assert all(int(suite[k])==0 for k in ['errors','failures','skipped'])
    assert 'Окончательная независимая подпись после Docker' in (out/'independent_verification.md').read_text(encoding='utf-8')
    tests=int(suite['tests'])
    record=json.loads((ROOT/'model/training_record.json').read_text(encoding='utf-8'))
    summary=pd.read_csv(out/'candidate_summary.csv').set_index('model')
    difference=pd.read_csv(out/'challenger_before_after_metrics.csv')
    bias=difference[(difference.metric=='bias')&difference.period.str.startswith('Четыре')].iloc[0]
    verdict=f'''# Итог ремедиации Nonton

**PASS в проверенном инженерном объёме.** Выпуск сохраняет прежнее качество прогнозирования и устраняет подтверждённые проблемы целостности артефактов, диагностируемости/изоляции кэша и CLI. Новые методы реально исследованы и испытаны. Небольшой средний development-выигрыш challenger признан; он не вошёл в serving по раскрытому tradeoff. Победа на leaderboard, высокая бизнес-точность и финансовый эффект не заявляются.

Дата завершения проверок: 18.10.2026, Москва. Корневой агент — PRINCIPAL ML REMEDIATION ARCHITECT; independent reviewer E подписал конкретный model/image/source комплект (`independent_verification.md`). Git HEAD отсутствует; контроль revision выполнен immutable snapshot и SHA-256, а не придуманным коммитом.

| Gate | Итог | Исполненные доказательства |
|---|---|---|
| A — baseline | PASS | Исходный snapshot: 119 тестов, 11 групп временного аудита, 31 OOF на трёх origins, исходные sales и официальные функции метрик |
| B — diagnosis | PASS | Диагностика всех серий, частоты, объёма, остатков и сегментов; 5 078 eligible нулевых прогнозов; ablation порога и горизонты |
| C — sources | PASS | Первичные источники и официальные реализации; научные принципы и локальные результаты разделены в evidence_register.csv |
| D — comparison | PASS | 17 кандидатов × 5 реальных 64-дневных окон = 85; независимый пересчёт; четыре development-окна и открытый terminal; явное дополнение L2 |
| E — engineering | PASS | Новый журнал обучения и строгий manifest, отказоустойчивый кэш, реальные CLI; {tests} тестов, без ошибок и пропусков |
| F — end-to-end | PASS | Полный grid 11 × 799 × 64; API/offline/submission parity; настоящий Docker с --network none, 6 GiB и 4 CPU |
| G — independent review | PASS | Reviewer E независимо проверил baseline, 85 прогнозов, файлы модели и image, полноразмерные выходы и финальные тесты |

## Принятый комплект

- Модель: `nonton-v1`, Tweedie 1.3, 220 деревьев, 45 признаков, threshold 0.25.
- Training run: `{record['training_run_id']}`; 1 476 552 строки, cutoff 2026-07-31; обучение заняло {record['fit_seconds']:.6f} с.
- Bundle ID: `{bundle['manifest']['bundle_id']}`.
- Веса SHA-256: `{file_hash(ROOT/'model/lightgbm.txt')}`; новые weights/config/catalog побитово совпали с сохранёнными исходными. Manifest и training record новые и относятся к реально выполненному refit.
- Docker image: `{review['image_id']}`; {docker['image_bytes']} байт. Сборка заняла {docker['build_seconds']:.6f} с и использовала кэш слоёв; это не замер холодной сборки.
- Submission: 562 496 строк, 2026-08-01–2026-10-03, полный grid 11 × 799 × 64; исходный файл сохранён. Локальная поставка: `nonton_solution_remediated_verified.zip`; состав и SHA-256 — `delivery_manifest.json`.

## Числа до и после

На 2026-05-29–2026-07-31 (7 752 eligible Bias-серии) выпущенный refit имеет **те же** SMAPE 158.687161721%, WAPE 80.430065677%, RMSE 0.866284149, Bias 80.565557266%, RMSLE 0.312615322. Разница каждой метрики релиза равна нулю; Bias изменился на 0 п.п. и 0% относительно исходного. Основания: побитово одинаковые weights/config/catalog, неизменённый численный pipeline и независимая end-to-end проверка (`before_after_metrics.csv`).

Исследовательский binary×Gamma с прежним threshold 0.25 улучшил средние всех пяти метрик на четырёх development-окнах. Bias: {bias.before:.9f} → {bias.after:.9f}%, разница {bias.difference:.9f} п.п. ({bias.relative_difference_pct:.6f}% относительно incumbent). Однако Bias хуже в трёх отдельных окнах из четырёх; значимость среднего выигрыша не установлена. Средний inference — {summary.loc['two_part_gamma_z0.25','inference_seconds']:.6f} с против {summary.loc['current_tweedie_z0.25','inference_seconds']:.6f} с; требуются два Booster вместо одного. Полное основание консервативного выбора — `final_model_decision.md`. Открытый terminal не использован как скрытое veto выбора.

## Полноразмерный runtime

| Проверка | Фактический результат |
|---|---:|
| Локальный HTTP POST | {api['post_seconds']:.6f}с |
| Замещающий HTTP POST | {api['replacement_post_seconds']:.6f}с |
| Concurrent POST / invalid upload | 409 / 400 |
| GET во время replacement / failed POST | Старая целая версия / сохранена версия2 |
| API/offline max abs | {api['max_abs_offline_difference']:.12g} |
| Server process-tree peak RSS | {api['peak_server_rss_bytes']}байт |
| Docker HTTP POST | {docker['post_seconds']:.6f}с |
| Docker cgroup memory peak | {docker['cgroup_memory_peak_bytes']}байт |
| Docker/offline max abs | {docker['max_abs_difference']:.12g} |

Windows RSS — сумма процесса запуска и дочерних процессов с опросом каждые 50 мс; общие страницы могут учитываться дважды. Cgroup — другой показатель, включающий память и кэш контейнера. Первая оценка около 4 МБ измеряла только launcher и признана недействительной. Оба JSON сохранены; приняты исправленные результаты. Память каждого fit отдельно не измерялась: в learned experiments сохранён накопительный максимум RSS процесса, который нельзя выдавать за память каждого алгоритма.

Первый внешний запуск PowerShell с перенаправлением `2>&1` получил NativeCommandError на обычном сообщении BuildKit, хотя вложенные build, HTTP и parity завершились успешно. Повтор того же Docker-script с раздельными stdout/stderr завершился с exit code 0 (`docker_command_status.json`). Это ошибка захвата вывода оболочкой; сырой первый лог сохранён. В таблице приведён последний успешный прогон, первый benchmark сохранён отдельно.

## Что остаётся неизвестным или ограниченным

1. Историческая хронология tuning не доказана Git-history; terminal уже открыт. Пять rolling-origin окон не являются пятью независимыми статистическими репликациями, нового untouched test нет.
2. ТЗ и executable SMAPE расходятся на (0,0): 47.089556121% против 158.687161721% на исходном holdout. Исполняемый scorer сохранён; текстовый diagnostic хранится отдельно. Обработка одинаковых рангов и неоднозначность minmax/rank требуют разъяснения организаторов; они не устранены нашим выбором.
3. Высокие WAPE/Bias и ошибка sparse сохраняются. Истинный неограниченный спрос и причинное влияние stockout не восстановлены. Анонимизированной quantity не приписано физическое count-distribution.
4. Поддерживается один процесс/worker и один экземпляр. После restart кэш пуст. Distributed cache, несколько контейнеров и скрытые custom worker launchers не поддерживаются.
5. Проверена точная опубликованная CLI matrix, а не все возможные повреждения любого входа. Неизменённый official scorer сохраняет warnings-only validator и собственное поведение ошибок. Подробности `cli_test_report.md`.
6. Ресурсы измерены на этой машине/запусках. Полная отдельная peak memory каждого fit, холодная сборка, будущие данные, финансовый эффект и место leaderboard не измерены.

Открытых подтверждённых release-blocking P0/P1 в проверенном объёме не найдено. Эти ограничения остаются частью приёмки; PASS инженерной поставке не означает доказанную высокую точность продаж.

## Воспроизведение

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 -m pytest tests reports/qa/check_backend_independent.py -q
.\\.venv\\Scripts\\python.exe -X utf8 scripts/remediation_diagnose.py
.\\.venv\\Scripts\\python.exe -X utf8 scripts/remediation_experiments.py
.\\.venv\\Scripts\\python.exe -X utf8 scripts/remediation_l2.py
.\\.venv_stats\\Scripts\\python.exe -X utf8 scripts/remediation_statistical.py
.\\.venv\\Scripts\\python.exe -X utf8 scripts/remediation_compare.py
.\\.venv\\Scripts\\python.exe -X utf8 scripts/remediation_report.py
.\\.venv\\Scripts\\python.exe -X utf8 scripts/remediation_backend_probe.py --model-dir model
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remediation_docker.ps1
```

Исходные пользовательские CSV нужны локально; в архив поставки они не входят. Production lock — `requirements.lock`; benchmark lock — `reports/remediation/statsforecast_requirements.lock`. Прежние QA-скрипты пишут исторические отчёты: их воспроизводят в snapshot-копии. Новые скрипты не меняют исходные CSV. Утверждения с источниками, числами и проверкой — `evidence_register.csv`; материал презентации — `presentation_evidence_ru.md`.
'''
    (out/'release_verdict.md').write_text(verdict,encoding='utf-8')
    answers=[
        ('Что было неправильно?', 'Не было криптографической связи каталога и весов; наружу выдавался изменяемый объект кэша; не хватало диагностических идентификаторов и CLI-проверок. Порог создавал конфликт метрик, скрытая ошибка масштабирования не подтверждена.'),
        ('Какие проблемы воспроизведены?', '119 исходных тестов, 11 групп временного аудита, все 31 OOF на трёх origins и все пять holdout-метрик. Риск замены каталога и изменяемый кэш воспроизведены отдельно.'),
        ('Почему модель недопрогнозировала?', 'Порог 0.25 удаляет 407 940 положительных дневных оценок и 30 517.941043 единицы объёма. У 5 078 из 7 752 eligible серий весь прогноз равен нулю. Без порога Bias ниже, но SMAPE и WAPE хуже.'),
        ('Какова роль intermittent-серий?', 'Исторически sparse: 4 921 ряд, 3 898 eligible, из них 3 847 с нулевым прогнозом; 7.499219% holdout-объёма. Bias — 101.227735% против 59.667485% у остальных eligible.'),
        ('Какие методы исследованы?', 'SBA, TSB, ADIDA, two-part/hurdle, global forecasting, метрики и временная валидация, LightGBM objectives, контракты артефактов и API. Источники: method_evidence.md.'),
        ('Что реально реализовано?', 'Три официальных StatsForecast-бенчмарка, L1 и binary×positive-only Gamma, оценка пяти origins, SHA-256 manifest и журнал обучения, защитные снимки кэша и CLI-интеграция.'),
        ('Какие научные источники это поддерживают?', 'Первичные DOI и официальные документы перечислены в method_evidence.md и evidence_register.csv. Общая обоснованность метода отделена от локального выигрыша Nonton.'),
        ('Что испытано и отклонено?', 'Новые методы не включены в serving. Небольшой средний выигрыш binary×Gamma признан; кандидат сохранён для дальнейшей проверки. Полное решение: final_model_decision.md.'),
        ('Какие изменения улучшили метрики?', 'У two-part средние всех пяти метрик немного лучше на четырёх development-окнах; SMAPE лучше в каждом из них. Этот выигрыш не приписан выпускной модели: её численный pipeline сохранён.'),
        ('Как изменился Bias в процентах?', f'В релизе: 80.565557266 → 80.565557266%, то есть 0 п.п. и 0% относительно исходного. У challenger на development: {bias.before:.6f} → {bias.after:.6f}%, {bias.difference:.6f} п.п. и {bias.relative_difference_pct:.6f}% относительно incumbent; хуже в трёх отдельных окнах из четырёх.'),
        ('Что произошло с остальными четырьмя метриками?', 'В релизе SMAPE 158.687161721%, WAPE 80.430065677%, RMSE 0.866284149, RMSLE 0.312615322; изменения равны нулю. Ненулевые исследовательские разности — challenger_before_after_metrics.csv.'),
        ('Улучшились ли дни 36–64?', 'В релизе Bias 84.552356% не изменился. У two-part на terminal — 83.768484%, но на development дальний Bias лучше лишь в двух окнах из четырёх; устойчивый выигрыш не установлен.'),
        ('Устойчиво ли улучшение по окнам?', 'Пять реальных 64-дневных окон: четыре development и открытый terminal. У two-part minmax лучше в трёх development-окнах, Bias — в одном. Значимость не установлена; независимость окон не заявляется.'),
        ('Какие инженерные дефекты исправлены?', 'Добавлены строгий контракт файлов и происхождения, защитные committed snapshots, заголовки и diagnostics, запрет обычного многопроцессного запуска, пути и ошибки CLI, проверки реальных entry points. Сохранено уже работавшее исключение конкурентных POST.'),
        ('Связаны ли каталоги с весами?', f'Да, для нового фактического run `{record["training_run_id"]}`; bundle `{bundle["manifest"]["bundle_id"]}`. Старому обучению не приписано фиктивное восстановленное происхождение.'),
        ('Безопасен ли кэш при ошибках и конкуренции?', 'Настоящие полноразмерные POST/GET подтвердили 409 для конкурента, 400 для invalid upload, целую старую версию во время замены и сохранение версии 2 после ошибки. Инъекция ошибки 500 проверена регрессионными тестами.'),
        ('Работают ли CLI?', f'{tests} тестов всего, включая 20 subprocess CLI cases, настоящий изолированный pipeline с двумя итерациями и запуск uvicorn. Точная матрица и границы проверок — cli_test_report.md.'),
        ('Совпадают ли Docker и offline?', f'Да: 562 496 ключей, сеть отключена, max abs {docker["max_abs_difference"]:.12g}. Реальные файлы image, исходников и модели независимо сравнены по SHA-256.'),
        ('Какова вычислительная стоимость?', f'Финальное обучение — {record["fit_seconds"]:.6f} с; HTTP — {api["post_seconds"]:.6f}/{api["replacement_post_seconds"]:.6f} с, RSS дерева процессов — {api["peak_server_rss_bytes"]} байт. Последний Docker POST — {docker["post_seconds"]:.6f} с, cgroup peak — {docker["cgroup_memory_peak_bytes"]} байт. Различия показателей и ограничения замеров раскрыты.'),
        ('Что остаётся непроверенным?', 'Новый untouched test, значимость небольшого выигрыша, причинный stockout и истинный спрос, все сочетания ошибок CLI, память каждого fit, холодная сборка, distributed cache, финансовый эффект и место leaderboard. Противоречия организаторских правил остаются открытыми.')
    ]
    # Readable questions are numbered; detailed numerical tables remain authoritative.
    text='# Ответы на 20 вопросов итогового технического отчёта\n\n'
    text+='Окончательный инженерный вердикт — `release_verdict.md`; первичные измерения и команды воспроизведения приведены там и в специализированных отчётах.\n\n'
    for i,(question,answer) in enumerate(answers,1):
        text+=f'{i}. **{question}** {answer}\n\n'
    (out/'final_technical_report_ru.md').write_text(text,encoding='utf-8')
    # Remove stale role-A/early-run counts in the merged register only.
    register=pd.read_csv(out/'evidence_register.csv').fillna('Не применимо')
    mask=register.claim_id=='ENG-CLI'
    register.loc[mask,'local_numerical_evidence']=f'20 CLI subprocess cases; финальный suite: {tests} passed, 0 failed, 0 skipped'
    register.loc[mask,'reviewer_signoff']='independent_verification.md;final_tests.xml'
    mask=register.claim_id=='ENG-CACHE'
    register.loc[mask,'local_numerical_evidence']=f'562 496 строк; POST {api["post_seconds"]:.6f}/{api["replacement_post_seconds"]:.6f} с; concurrent 409; failed 400; parity 0'
    register.loc[mask,'acceptance_status']='Принято; полноразмерные выходы и фактические файлы Docker независимо проверены'
    register.to_csv(out/'evidence_register.csv',index=False)
    print('Итоговый вердикт сформирован по проверенным evidence.')


if __name__=='__main__':
    run()
