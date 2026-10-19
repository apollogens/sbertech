"""Build Russian release reports and a manifest from completed execution evidence."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "consolidation"
sys.path.insert(0, str(ROOT))
from src.artifacts import file_hash
from src.runtime import verify_runtime_bundle


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def write(name, text):
    (OUT / name).write_text(text, encoding="utf-8")


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
                      + ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def run():
    baseline = read("pre_merge_manifest.json")
    cleanup = read("cleanup_result.json")
    rollback = read("rollback_verification.json")
    regression = read("regression/result.json")
    assert regression["status"] == rollback["status"] == "passed"
    config, candidate_manifest = verify_runtime_bundle(ROOT / "bundles/equal4-rc1")
    test_bytes = (OUT / "final_tests.log").read_bytes()
    final_tests = test_bytes.decode("utf-16" if test_bytes.startswith(b"\xff\xfe") else "utf-8-sig")
    assert "238 passed" in final_tests and "failed" not in final_tests
    docker_rows = []
    docker_data = {}
    for strategy, tag in (("nonton-v1", "nonton:consolidated-v1"), ("equal4", "nonton:consolidated-equal4")):
        evidence = read(f"docker_{strategy}/verification.json")
        restart = read(f"docker_{strategy}/restart.json")
        images = read(f"docker_{strategy}/image.json")
        actual_image = json.loads(subprocess.check_output(["docker", "image", "inspect", tag], text=True))[0]
        display_size = subprocess.check_output(["docker", "image", "ls", tag, "--format", "{{.Size}}"], text=True).strip()
        assert images[0]["Id"] == actual_image["Id"], "HTTP evidence belongs to a superseded image"
        assert evidence["status"] == restart["status"] == "passed"
        container = read(f"docker_{strategy}/container_inspect.json")[0]
        assert container["HostConfig"]["NetworkMode"] == "none"
        assert container["Image"] == actual_image["Id"]
        docker_data[strategy] = dict(image=tag, image_id=actual_image["Id"],
                                     inspect_size_bytes=actual_image["Size"], image_ls_size=display_size, **evidence)
        docker_rows.append([strategy, display_size, actual_image["Size"], f'{evidence["post_seconds"]:.3f}',
                            f'{evidence["repeat_post_seconds"]:.3f}', evidence["cgroup_peak_rss_bytes"],
                            f'{evidence["offline_api_max_abs_difference"]:.3g}'])
    write("docker_summary.json", json.dumps(docker_data, ensure_ascii=False, indent=2))
    build = read("docker_build_v1.json")
    write("docker_benchmarks.md", "# Проверка финальных контейнеров\n\n"
          "Оба образа исполнены без сети, с 4 CPU и лимитом 6 GiB. В таблице полная HTTP-операция: "
          "валидация CSV, загрузка истории, построение признаков, все необходимые Booster, alignment и сериализация. "
          "GET/JSON, повторный POST, сохранение кэша после ошибочного POST и пустой кэш после restart проверены.\n\n"
          + table(["Стратегия", "image ls", "inspect.Size, байт", "POST, с", "Повтор POST, с", "cgroup memory.peak, байт", "max |offline−API|"], docker_rows)
          + f"\n\nПервичная сборка incumbent с `--no-cache`: {build['seconds']:.3f} с. "
          "Это пересборка без reuse инструкционных слоёв, не измерение полностью холодного Docker daemon/диска/registry. "
          "Финальные сборки после peer review использовали cache; их отдельные timings — `docker_build_*_final.json`. "
          "Первоначальная сборка candidate до исправления config не выдаётся за проверенный финальный образ. "
          "Базовый Python закреплён digest, runtime packages — точными версиями.\n\n"
          "`inspect.Size` и `docker image ls` в данном Docker Desktop используют различный учёт хранения; "
          "их нельзя смешивать для утверждения экономии. Ни одна из величин не приближается к лимиту 30 GB. "
          "cgroup peak включает процессы probe/CSV comparison, файловый cache и повторные запросы, а не только модель. "
          "Оба измерения укладываются в 64 GB RAM и лимиты POST 60 минут/GET 10 минут. "
          "Это последовательные acceptance measurements, не статистический latency benchmark. "
          "Исходные CSV поданы после старта; в образах их нет. Runtime images не содержат OOF/NPZ, тестовых библиотек и чужих checkout.\n")
    write("test_results.md", "# Исполненные проверки\n\n"
          "Baseline до изменений: 193 passed, 37.61 с. После нового runtime: 219 passed, 37.05 с. "
          "После Gate 8 в чистой среде: 237 passed, 48.57 с. Финальная общая команда: **238 passed**, 61.56 с; "
          "включает 193 прежних проверки и 45 добавленных. Один Starlette warning о будущем httpx не подавлялся; "
          "обновление библиотек не входило в cleanup. Числа разных прогонов не суммируются.\n\n"
          "```powershell\n.venv_consolidated/Scripts/python.exe -X utf8 -m src.cli test -- tests reports/qa/check_backend_independent.py integration/test_catalog_policy.py integration/test_ensemble_engine.py -q\n```\n\n"
          "Ruff E9/F и deptry по каноническим src/app: 0 замечаний. Обе новые среды проходят pip check. "
          "Чистый runtime содержит 23 пакета Windows без pip, 22 Linux; pytest/httpx/psutil не требуются для serving.\n\n"
          "Реальные сохранённые модели дали полный grid 562496 строк. Runtime facade и прежние Windows reference CSV "
          "совпали побайтово; отдельное воспроизведение четырёх raw components и пяти P1 стратегий дало maxdiff=0.0. "
          "CLI намеренно пишет LF: количества и порядок ключей сохранены, текстовый hash отличается от CRLF reference. "
          "Host real CLI и оба настоящих Docker HTTP outputs проверены отдельно от synthetic unit tests.\n\n"
          "180-day backtest: 25 новых прогнозов D/W/S/A/equal4, пять historical origins, official primitives, sparse/horizon diagnostics. "
          "25 прежних reference NPZ и official metrics сверены отдельно. Reviewer независимо пересчитал все 25 новых NPZ. "
          "Не выполнен квадратичный full official merge на всех панелях; проверены исходные функции метрик и ранее сохранённый merge fixture.\n\n"
          "Rollback: 1003 извлечённых файла сверены по SHA-256; старая модель на 562496 строках maxdiff=3.55e−15. "
          "Peer QA повторил hashes всего ZIP и всех извлечённых файлов. Доказательства — JSON/логи рядом; "
          "Docker measurements — `docker_benchmarks.md`.\n")
    write("migration_log.md", "# Выполненная миграция\n\n"
          "1. Созданы immutable snapshot и inventory до изменений; Git HEAD отсутствует, фиктивного commit нет.\n"
          "2. Три первоначальных read-only аудита завершены до распределения реализации.\n"
          "3. Выделены src.catalog/temporal/ensemble/components; добавлены runtime dispatcher и один CLI. "
          "Шесть hash-bound incumbent модулей сохранены точно.\n"
          "4. Новый runtime-v2 bundle сохраняет исходные три TXT побайтово; manifest содержит parent hashes, catalogs, encoder, features, dependencies и runtime sources. "
          "Последующая source-only reseal сохраняет старый manifest в runtime_manifest_history и отвергает изменение весов.\n"
          "5. До удаления чего-либо доказана реальная численная регрессия; затем отдельно пересобраны locks и новые среды.\n"
          "6. Четыре исторических файла делегируют общие расчёты каноническим модулям; шесть дублирующих инструментов архивированы и удалены из активного дерева. "
          "Ledger — deleted_files_and_reasons.csv, архив проверен до unlink. scripts/predict.py сохранён как тонкий адаптер публичных legacy flags.\n"
          "7. Старые source-bound manifests/ZIP/models не переписаны. Их исторические команды исполняются после восстановления frozen source из pre_merge_snapshot.zip. "
          "Для текущих predict/package/API/Docker используется новый CLI. Общие исследования, evidence, scorer и исходные данные сохранены.\n"
          "8. Проверены 180-day inputs, clean tests, оба Docker images, restart и rollback. Peer review выявил и исправил выбор strategy в Docker CLI и config кандидата.\n\n"
          "Внешний код не копировался. Подтверждён только filipp880/forecast-64-v1; второй пользовательский проект не найден. "
          "Из-за отсутствия лицензии перенесена самостоятельно реализованная идея смеси/postprocessing.\n")
    # A measured history-policy comparison, explicitly distinct from refactoring parity.
    write("before_after_metrics.csv", (OUT / "backtest_180/before_after_metrics.csv").read_text(encoding="utf-8"))
    software = [
        ["runtime_packages_windows_excluding_pip", 33, 23, "resolved mixed old lock versus runtime-only new lock"],
        ["explicit_regression_cases", 193, 238, "same 193 old cases plus45 new"],
        ["separate_component_boosters", 3, 3, "unchanged model architecture; S shares D/W"],
        ["duplicate_release_adapters_active", 6, 0, "six ledger entries archived; historical originals preserved"],
        ["shared_legacy_helper_file_lines", 0, 0, "computed below"],
    ]
    merged = ["integration/catalog_policy.py", "integration/ensemble_engine.py", "integration/corrected_models.py", "scripts/architecture_experiments.py"]
    with zipfile.ZipFile(OUT / "pre_merge_snapshot.zip") as archive:
        old_lines = sum(len(archive.read(name).splitlines()) for name in merged)
    new_lines = sum(len((ROOT / name).read_bytes().splitlines()) for name in merged)
    software[-1] = ["legacy_helper_file_lines", old_lines, new_lines,
                    "four rewritten historical files only; excludes new runtime and validation code"]
    with (OUT / "before_after_software_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["measure", "before", "after", "scope"])
        writer.writerows(software)
    quality_rows = [["Corrected D:P1", "165.307454", "85.931055", "0.775274", "82.795357", "0.307112"],
                    ["equal4:P1", "165.027991", "85.723702", "0.771062", "81.284307", "0.305680"]]
    write("final_release_report_ru.md", "# Финальная консолидация Nonton\n\n"
          "**Один проект и один runtime поставлены; активным остаётся nonton-v1. equal4:P1 — технически проверенный selectable release candidate.** "
          "Веб-API, CLI и Docker используют общий inference; четыре corrected представления доступны через отдельный versioned bundle. "
          "Консолидация не переобучала модели и не изменяла их численные прогнозы.\n\n"
          "Объединены собственные production и integration реализации Nonton. Подтверждён один внешний GitHub-проект "
          "filipp880/forecast-64-v1, commit f8a8c6e60edaf12af2fd351e290c35e6875afea0; его tracked tree не содержит лицензии. "
          "Чужой код не перенесён. Самостоятельно реализованы общая выпуклая смесь и half-even исследовательский postprocessing. "
          "Второй пользовательский репозиторий не установлен; интеграция двух внешних проектов не заявляется.\n\n"
          "Общие catalog, temporal allocation, component inference и ensemble вынесены в src. Исторические paths стали тонкими adapters; "
          f"{cleanup['archived_removed']} заменённых release-инструментов архивированы. Данные, официальный scorer, все прежние модели/NPZ/ZIP сохранены. "
          "Подробный ledger и migration_log описывают каждый путь. Legacy scripts/predict.py также делегирует единому CLI.\n\n"
          + table(["Инженерный показатель", "До", "После"], [[row[0], row[1], row[2]] for row in software])
          + "\n\nЧисло строк относится только к четырём старым helper-файлам; общий объём проекта вырос из-за новых стратегий, проверок и отчётов. "
          "Сокращение dependencies означает выделение runtime, а не удаление возможностей обучения/тестирования. "
          "Из runtime убраны certifi, colorama, httpcore, httpx, iniconfig, packaging, pluggy, psutil, Pygments, pytest; "
          "они остаются в соответствующих dev/training группах. Runtime сохраняет numpy/pandas/lightgbm, FastAPI/Starlette/Uvicorn, multipart "
          "и разрешённые transitive dependencies. Версии прежних библиотек не обновлялись.\n\n"
          "Чистые runtime и dev установки проходят pip check. **238 тестов прошли**, включая все 193 прежних. "
          "Ruff/deptry: 0 замечаний. Реальные четыре raw компонента и все пять P1 стратегий совпали с frozen реализацией точно (maxdiff=0). "
          "Host CLI совпадает численно; новый serializer явно использует LF вместо прежнего CRLF. "
          "Оригинальный submission.csv не заменён; новый `consolidation/submission.csv` валиден: 562496 строк, 64 дня 2026-08-01—2026-10-03, "
          "11 складов, 799 товаров, полное покрытие без duplicate/NaN/Inf/negative.\n\n"
          "Production-like backtest завершён на пяти origins с ровно 180 днями входных sales/stock. "
          "Средние по четырём development origins, меньше лучше:\n\n"
          + table(["Кандидат", "SMAPE", "WAPE", "RMSE", "Bias", "RMSLE"], quality_rows)
          + "\n\nВыигрыш equal4 против corrected D небольшой, но присутствует во всех пяти средних. "
          "Это прежние повторно используемые окна. Incumbent historical TXT однозначно сохранились лишь для двух origins, "
          "поэтому полного четырёхоконного сравнения incumbent/equal4 при одинаковом 180-day input нет. "
          "Terminal diagnostic не участвует в выборе. Политика serving — вся переданная история, минимум 180 дней; "
          "сокращение входной истории в backtest не выдаётся за эффект cleanup.\n\n"
          + table(["Docker", "image ls", "inspect.Size, байт", "POST, с", "Повтор, с", "cgroup peak, байт", "max |offline−API|"], docker_rows)
          + "\n\nОба финальных образа проверены без сети, 4 CPU/6 GiB: cache/filter/JSON/repeat/error/restart пройдены. "
          "Лимиты конкурса соблюдены. POST включает валидацию CSV, признаки, prediction, alignment и сериализацию; "
          "загрузка весов происходит при startup и в POST не включена. Startup отдельно не измерен. Candidate заметно тяжелее. "
          "Сравнения скорости с прежними измерениями не являются статистическим benchmark. "
          "Новый ensemble теперь проверен через общий API и Docker; это техническая готовность кандидата, не доказанная победа по качеству.\n\n"
          "Манифесты связывают preprocessing, encoder, признаки, численные зависимости и веса. Повреждённые artifacts/config отвергаются. "
          "Старые manifests сохранены; новый runtime contract имеет отдельную identity. External preregistration и новое untouched test не заявляются. "
          "Executable/written SMAPE и rank/minmax uncertainty остаются раскрыты. Survivorship output catalog и неизвестный организаторский catalog "
          "полностью историческим replay не устраняются. Авторы runtime/CLI участвовали в peer review с раскрытием ролей; "
          "это отдельные агентские проверки, не внешняя сертификация.\n\n"
          "Артефакты: `consolidation/nonton_consolidated_verified.zip`, `release_manifest.json`, `release_package.json`, "
          "`submission.csv`; candidate weights — `bundles/equal4-rc1`; runtime selection — `config/runtime.json`. "
          "Rollback отдельно: `pre_merge_snapshot.zip` и `pre_merge_manifest.json`, проверены 1003 извлечённых файла и старый полноразмерный inference. "
          "Точные инструкции — rollback_plan.md; архив извлекается в новую пустую папку. Для переключения только модели достаточно "
          "nonton-v1 config и перезапуска API без переобучения.\n\n"
          "```powershell\n.venv_consolidated/Scripts/python.exe -m src.cli test\n"
          ".venv_consolidated/Scripts/python.exe -m src.cli predict --sales sales.csv --stock stock.csv --output forecast.csv\n"
          ".venv_consolidated/Scripts/python.exe -m src.cli serve --model-dir bundles/equal4-rc1 --strategy equal4:P1\n"
          ".venv_consolidated/Scripts/python.exe -m src.cli docker test --image nonton:consolidated-v1 --strategy nonton-v1\n"
          ".venv_consolidated/Scripts/python.exe -m src.cli docker test --image nonton:consolidated-equal4 --strategy equal4\n```\n")
    return candidate_manifest


if __name__ == "__main__":
    run()
