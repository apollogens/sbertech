"""Produce final evidence from actual artifacts and executable acceptance checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.predict import load_bundle
from src.submission import validate_submission

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        while block:=stream.read(1024*1024):h.update(block)
    return h.hexdigest()


def table(frame, columns, digits=5):
    lines=["| "+" | ".join(columns)+" |","|"+"|".join(["---"]*len(columns))+"|"]
    for _,row in frame.iterrows():
        vals=[f"{row[c]:.{digits}f}" if isinstance(row[c],(float,np.floating)) else str(row[c]) for c in columns]
        lines.append("| "+" | ".join(vals)+" |")
    return "\n".join(lines)


def run():
    bundle=load_bundle()
    frame=pd.read_csv("submission.csv",dtype={"date":str,"warehouse_name":str,"article":str})
    submission=validate_submission(frame,"2026-07-31",bundle["catalogs"])
    offline=pd.read_csv("data/parity/offline.csv",dtype={"date":str,"warehouse_name":str,"article":str})
    assert frame.iloc[:,:3].equals(offline.iloc[:,:3])
    csv_difference=float(np.max(np.abs(frame.quantity-offline.quantity)))
    assert csv_difference<1e-7
    test=subprocess.run([sys.executable,"-m","pytest","-q"],text=True,capture_output=True)
    Path("reports/test_results.txt").write_text(test.stdout+test.stderr,encoding="utf-8")
    assert test.returncode==0,test.stdout+test.stderr
    training=json.loads(Path("reports/training_benchmarks.json").read_text())
    parity=json.loads(Path("reports/parity_benchmarks.json").read_text())
    docker=json.loads(Path("reports/container_benchmark.json").read_text(encoding="utf-8-sig"))
    assert parity["status"]==docker["status"]=="passed"
    assert docker["network_mode"]=="none" and docker["rows"]==562496
    assert docker["build_seconds"]<=3600 and docker["post_seconds"]<=3600
    assert docker["image_bytes"]<30e9 and docker["cgroup_memory_peak_bytes"]<64e9
    assert parity["get_csv_seconds"]<600 and parity["get_json_seconds"]<600
    source_paths=[Path(r"C:\Users\apollo\Desktop\выборка")/name for name in [
        "markdown hakaton.md","sales_dataset_hakaton_train.csv","stock_dataset_hakaton_train.csv"]]
    source_paths += [Path(r"C:\Users\apollo\Downloads\Nonton_Backend_TZ_Forecasting_API.docx"),
        Path(r"C:\Users\apollo\.codex\attachments\7f55313f-e003-4c04-b2fc-618a2fbd039c\Pasted text.txt")]
    manifest={str(path):{"bytes":path.stat().st_size,"sha256":digest(path)} for path in source_paths}
    Path("reports/input_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    importance=pd.DataFrame({"feature":bundle["model"].feature_name(),
                            "gain":bundle["model"].feature_importance(importance_type="gain"),
                            "split":bundle["model"].feature_importance(importance_type="split")}).sort_values("gain",ascending=False)
    importance.to_csv("reports/feature_importance.csv",index=False)
    verification={"date":"2026-10-18","submission":submission,"submission_sha256":digest(Path("submission.csv")),
        "submission_vs_offline_max_abs_difference":csv_difference,"model_sha256":digest(Path("model/lightgbm.txt")),
        "tests_returncode":test.returncode,"tests_summary":test.stdout.strip().splitlines()[-1],
        "offline_api_parity":parity["status"],"docker_parity":docker["status"],"network_none":True}
    Path("reports/final_verification.json").write_text(json.dumps(verification,indent=2),encoding="utf-8")
    resources=f"""# Измеренные вычислительные затраты

Проверка выполнена 18 октября 2026 года на AMD Ryzen 7 5700, 16 логических CPU, 16 964 587 520 байт физической RAM. Обучение и прогноз LightGBM используют четыре потока. Docker Desktop Linux имеет около 8,22 GB RAM; проверяемому контейнеру заданы лимиты 6 GiB и четыре CPU. GPU не использовался.

| Операция | Измерение |
|---|---:|
| Полный pipeline с подготовкой и всеми экспериментами | {training['pipeline_seconds']:.2f} с |
| Peak RSS процесса pipeline, опрос каждые 0,1 с | {training['peak_process_rss_bytes']/1e9:.3f} GB |
| Финальное обучение | {training['final_fit_seconds']:.2f} с |
| Прогноз готовой панели | {training['final_inference_seconds']:.2f} с |
| Текстовые веса модели | {training['final_model_bytes']:,} байт |
| Offline с подготовкой полного очищенного входа | {parity['offline_seconds']:.2f} с |
| Локальный POST TestClient с сериализацией CSV | {parity['post_seconds']:.2f} с |
| Повторный POST | {parity['repeated_post_seconds']:.2f} с |
| GET полный CSV / JSON, TestClient | {parity['get_csv_seconds']:.2f} / {parity['get_json_seconds']:.2f} с |
| Peak RSS полного локального parity-процесса | {parity['peak_process_rss_bytes']/1e9:.3f} GB |
| Docker build --no-cache | {docker['build_seconds']:.2f} с |
| Размер образа по docker image inspect .Size | {docker['image_bytes']:,} байт |
| HTTP POST внутри контейнера без сети | {docker['post_seconds']:.2f} с |
| Пик memory.peak cgroup контейнера | {docker['cgroup_memory_peak_bytes']/1e9:.3f} GB |

Зависимости загружались при сборке. Базовый образ уже был локально доступен; время не включает холодную установку Docker и загрузку базового образа. memory.peak включает файловый кэш контейнера; это не та же величина, что RSS Python. RSS с дискретным опросом может пропустить очень короткий пик. Сравнение latency между платформами не является контролируемым аппаратным экспериментом.

Полный Docker POST выполнен с --network none; файлы запроса временно переданы в /tmp, оригинальная train-выгрузка не встроена в образ. CSV считывались через HTTP loopback, а результат сравнен с offline на всех 562 496 строках. Контейнер удалён после теста. Стоимость облачной инфраструктуры и денежная экономия не измерялись.

Машиночитаемые источники: training_benchmarks.json, parity_benchmarks.json, container_benchmark.json. Вычислительные затраты обучения отдельных кандидатов:

{table(pd.DataFrame(training['fits']),['model','fold','train_rows','train_seconds','inference_seconds'])}
"""
    Path("reports/resource_benchmarks.md").write_text(resources,encoding="utf-8")
    final=f"""# Итоговая проверка решения

Проверено 18 октября 2026 года в D:\\SberTech. Реализованы обученная модель, воспроизводимый backtest, итоговый прогноз, FastAPI и автономный Docker. Исходные пользовательские документы и датасеты сохранены без изменений. Источники и SHA-256 находятся в input_manifest.json.

| Проверка | Результат | Свидетельство |
|---|---|---|
| Полная история прочитана и проверена | выполнено | input_audit.json, detailed_audit.json |
| Суммирование продаж департаментов | выполнено | src/data.py, tests/test_pipeline.py |
| Разрешение неоднозначных остатков | явное консервативное допущение | docs/decision_log.md, scripts/prepare_api_inputs.py |
| Метрики эквивалентны встроенному scorer | выполнено | 13 metric-тестов, scripts/official_score.py |
| Два selection-среза и независимый 64-дневный holdout | выполнено | experiment_results.csv, selection_frozen.json, oof/ |
| Утечка будущих наблюдений в признаки | тесты не выявили | tests/test_pipeline.py, independent_review.md |
| Финальная сериализованная модель | выполнено | model/lightgbm.txt, config.json, catalogs.json |
| Итоговый CSV прочитан повторно и проверен | {submission['rows']} строк, 64 даты | submission.csv, final_verification.json |
| Четыре endpoint API и ошибки | выполнено | tests/test_api.py |
| Полный offline/API parity | max diff {parity['max_abs_difference']:.3g}, все ключи совпали | parity_benchmarks.json |
| Повторный POST | байты CSV идентичны | parity_benchmarks.json |
| Полный Docker parity без сети | max diff {docker['max_abs_difference']:.3g}, все ключи совпали | container_benchmark.json |
| Лимиты RAM, времени и размера Docker | выполнено на измеренном входе | resource_benchmarks.md |
| Все автоматические тесты | {verification['tests_summary']} | test_results.txt |

Финальный прогноз покрывает 2026-08-01–2026-10-03, содержит ровно date, warehouse_name, article, quantity, все 11 × 799 пары, без дублей, NaN, infinity и отрицательных значений. Проверка требует детерминированного порядка ключей. Максимальная погрешность записи submission относительно offline составляет {csv_difference:.3g}, ниже допуска 1e-7.

Выбран LightGBM Tweedie, 220 деревьев, восемь опорных обучающих горизонтов и порог 0,25. Полные результаты по моделям и периодам приведены в model_selection.md. Holdout: SMAPE 158,687%, WAPE 80,430%, RMSE 0,866284, Bias 80,566%, RMSLE 0,312615. Преимущество по диагностическому совокупному score не означает улучшения каждой метрики: TSB лучше по Bias и RMSLE. Разница Tweedie и L2 на selection мала и не доказывает статистической значимости.

Последние 180 дней проверены отдельно на holdout-модели, не обученной на holdout labels. Пять метрик совпали с полным историческим входом на этом одном origin. Другие периоды или другие файлы могут давать иные признаки и прогнозы. Тест точного offline/API совпадения всегда использует одинаковую историю.

Остаются содержательные ограничения: пропуски продаж интерпретированы как нули, смысл конфликтов остатков не подтверждён владельцем, расхождение текстового SMAPE со scorer не разъяснено организаторами, полный каталог выбран по числу обязательных строк. На sparse-рядах WAPE около 103%; решение не заявлено достаточным для автоматических закупок. Конкурсный ранг и бизнес-эффект неизвестны. Публичная публикация, облачное развёртывание и фактическая отправка submission организаторам не выполнялись.

Воспроизведение описано в README.md; материал для защиты — docs/presentation_pitch_ru.md. Первоначальные статусы «требуется проверка» в аудите спецификации являются исторической записью; актуальный результат находится в этой таблице.
"""
    Path("reports/final_verification.md").write_text(final,encoding="utf-8")
    # Compact delivery excludes private source data, environments and heavy caches.
    include=[]
    for folder in ["src","app","tests","scripts","docs","model"]:
        include.extend(p for p in Path(folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    include.extend(p for p in Path("reports").iterdir() if p.is_file() and p.name!="container_forecast.csv")
    include.append(Path("reports/oof/selected_holdout.txt"))
    for name in ["README.md","Dockerfile",".dockerignore",".gitignore","requirements.txt","requirements-dev.txt","requirements.lock","submission.csv","submission_baseline.csv"]:
        include.append(Path(name))
    with zipfile.ZipFile("nonton_solution.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(set(include)):
            if path.exists():archive.write(path,path.as_posix())
    print(json.dumps(verification,indent=2))
    print("Archive bytes",Path("nonton_solution.zip").stat().st_size)


if __name__=="__main__":
    run()
