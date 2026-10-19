# Независимый ML/temporal audit — Agent B

Исполнен 18 октября 2026 года в D:\SberTech. Это независимый запуск текущего кода и реальных сохранённых моделей. Reviewer не перезапускал полное обучение; отдельное воспроизведение root проверено ниже по сохранённым весам.

Команда: `.venv\Scripts\python.exe reports/qa/check_temporal_independent.py`. Результат: **11 PASS, 0 FAIL, 0 SKIP**.

Среда: Python 3.12.10, NumPy 2.5.4, pandas 3.0.6, LightGBM 4.7.0; Windows-10-10.0.19045-SP0.

## Область и зависимости

`src/data.py` → Panel; `src/features.py` → snapshot/horizon_features/training_data; `src/train.py` → train_model; `src/baselines.py` и `src/predict.py` → inference. Просмотрены scripts/run_pipeline.py, train_final.py, backtest_baselines.py, prepare_api_inputs.py, predict.py, verify_parity.py, audit_inputs.py, tests/test_pipeline.py, model/config.json, selection_frozen.json, training_benchmarks.json, detailed_audit.json, model_selection.md, independent_review.md и оригинальное ТЗ markdown hakaton.md.

## Выводы и ограничения

- Подтверждённой temporal target leakage в выполненных ветках не обнаружено. Каждый synthetic training label выровнен с origin+h; последняя label не позднее cutoff. Изменение будущего не меняет features, labels и строки сериализованной tiny-модели.
- Все baseline OOF на трёх окнах и выбранные LightGBM OOF воспроизведены текущим кодом и реальными артефактами с точной численной идентичностью. Root повторил все 6 полных fits; reviewer независимо сверил файлы весов, hashes, встроенные параметры и metadata. Все 6 побитово совпадают с исходниками и initial_manifest; ограничение невоспроизведённого полного обучения снято.
- `scripts/run_pipeline.py` использует одинаковые окна/ключи для кандидатов, выбирает objective и threshold по fold 1/2 и записывает выбор до fold 3. Факт исторического порядка действий подтверждён кодом и сохранёнными файлами, а не независимым журналом из прошлого. Разница top-2 мала; устойчивое превосходство не доказано.
- `src/features.py:21` long_mean зависит от всей предоставленной истории. Другие признаки ограничены максимум 180 днями. Результаты full/180 приведены по фактическому инференсу ниже; равенство здесь не является математической гарантией для других входов.
- `src/data.py:37` clean_stock удаляет сначала negative, затем неоднозначные оставшиеся daily keys. Это консервативная политика, а не восстановленный истинный остаток. При [-1,3] сохраняется 3; при [2,9] удаляются обе строки. Строгий builder/API отвергает конфликтный сырой файл; предусмотрена явная подготовка через prepare_api_inputs.py.
- `prepare_cache` формирует каталог из всей истории. Добавление future-only ID при глобальном расширении каталога способно менять past warehouse_mean и integer categorical mapping; это ограничение при переносе на открытый каталог. В официальной задаче каталог фиксирован 11×799. На первом validation origin реально наблюдались 793 article, на двух следующих — 799; во всех трёх окнах 11 warehouse. Следовательно, fold1 использует 6 future-only article IDs в фиксированном каталоге. Это transductive knowledge пространства ID; реальные будущие quantity/stock не используются. Оценку open-catalog deployment этот протокол не доказывает.
- Исправление root независимо подтверждено: `load_bundle` теперь отвергает перестановку categorical ID по проверке sorted order, которая соответствует фактическому training encoder catalog_from_sales. Текущие bundle/catalog/cache согласованы; реальные OOF по-прежнему воспроизводятся точно.
- Residual limitation P2: sorted order не заменяет fingerprint каталога. Валидный отсортированный каталог с другим ID по-прежнему принимается; это отдельно воспроизведено через mock чтения JSON без изменения файлов. Риск относится к неверной ручной комплектации чужими artifacts, не к обнаруженной порче текущего bundle. Минимальное дальнейшее усиление: persist canonical catalog fingerprint/model checksum и сверять при загрузке.
- Отдельно независимо исполнены root guards: нестрогая дата, float32 overflow sales/stock и после aggregation, неизвестный kind, отрицательный/NaN threshold, неверные оси forecast shape — всё отвергается.
- Уточнение воспроизводимости аудита: первоначальный запуск дал 9 PASS/1 FAIL на неверном предположении ревьюера, что каждый ID уже наблюдался на каждом fold. Этот результат сохранён в evidence initial_run; тест заменён измерением actual catalog counts в соответствии с официальным fixed-catalog scope. Это исправление тестовой предпосылки, не исправление production-кода.
- Reviewer лично не выполнял container benchmark и HTTP API. Full training reproduction выполнено root; сохранённые веса и metadata независимо проверены reviewer без повторного fit. Синтетические tiny fit имеют 2 дерева и проверяют только temporal invariance, не качество.

## Исправленный P2 и оставшееся ограничение артефактов

Файл: `src/predict.py`, функция `load_bundle`, чтение `catalogs.json` и проверка feature schema. Repro: тест `root_guards_and_catalog_remap_rejection` подменяет только read_text каталога на JSON с двумя переставленными article IDs; настоящие config и LightGBM model читаются с диска. Ожидание усиленного integrity-контракта: несогласованный mapping отвергается. До root fix load_bundle принимал перестановку; после fix отвергает её. Исправление принято reviewer независимо. Дополнительный negative probe заменяет первый ID на другой с сохранением sorted order: load_bundle принимает такой каталог. Это оставшееся ограничение fingerprint P2: текущие артефакты согласованы, риск возникает при неверной ручной сборке bundle. Предложение: хранить canonical catalog fingerprint при training/export и проверять при загрузке; применение такого изменения требует повторной artifact parity, но не меняет признаки и не требует переобучения деревьев. Статус: root permutation guard проверен; fingerprint limitation раскрыт. Этим read-only reviewer production artifacts не изменялись.

## Результаты тестов

```json
[
  {
    "test": "future_append_new_id_fixed_cutoff_row_order_sales_aggregation",
    "status": "PASS",
    "seconds": 0.125
  },
  {
    "test": "stock_duplicate_negative_and_shuffle_policy",
    "status": "PASS",
    "seconds": 0.021
  },
  {
    "test": "training_boundary_label_alignment_feature_parity",
    "status": "PASS",
    "seconds": 0.438
  },
  {
    "test": "tiny_saved_model_future_parameter_invariance",
    "status": "PASS",
    "seconds": 0.329
  },
  {
    "test": "calendar_leap_year_and_year_boundaries",
    "status": "PASS",
    "seconds": 0.036
  },
  {
    "test": "real_artifact_schema_catalog_and_training_origins",
    "status": "PASS",
    "seconds": 0.027
  },
  {
    "test": "root_guards_and_catalog_remap_rejection",
    "status": "PASS",
    "seconds": 0.046
  },
  {
    "test": "real_model_future_perturbation_invariance",
    "status": "PASS",
    "seconds": 5.169
  },
  {
    "test": "real_all_18_baseline_oof_reproduction",
    "status": "PASS",
    "seconds": 0.281
  },
  {
    "test": "real_ml_3fold_oof_reproduction_and_full_vs_180",
    "status": "PASS",
    "seconds": 17.907
  },
  {
    "test": "future_catalog_expansion_and_actual_fold_catalogs",
    "status": "PASS",
    "seconds": 7.374
  }
]
```

## Измеренные доказательства

```json
{
  "stock_policy": "Negative rows removed first; remaining contradictory nonnegative daily keys entirely removed; identical duplicates collapsed. Strict builder rejects contradictory keys.",
  "synthetic_training": {
    "origins": [
      179,
      214,
      249,
      281
    ],
    "rows": 128,
    "last_label_index": 345,
    "cutoff": 345
  },
  "synthetic_tiny_fit": {
    "rounds": 2,
    "identical_serialized_model_strings": true
  },
  "real_artifact": {
    "shape": [
      943,
      8789
    ],
    "dates": [
      "2024-01-01",
      "2026-07-31"
    ],
    "features": 45,
    "trees": 220,
    "training_rows": 1476552
  },
  "root_guards_independent_revalidation": [
    "strict date 2025-1-1",
    "strict date 2025-01-01 00:00:00",
    "float32 sales",
    "float32 stock",
    "float32 aggregation",
    "config kind invalid",
    "config zero_threshold -1.0",
    "config zero_threshold nan",
    "forecast shape axes"
  ],
  "catalog_artifact_integrity_gap": {
    "before_fix_swapped_mapping_accepted": true,
    "after_fix_swapped_mapping_rejected": true,
    "sorted_foreign_id_still_accepted": true,
    "production_artifacts_modified": false,
    "mechanism": "Mock substitutes only the catalog JSON read; genuine config and genuine LightGBM file are loaded."
  },
  "real_future_perturbation": {
    "origin": "2026-01-20",
    "max_abs_prediction_difference": 0.0
  },
  "baseline_oof_reproduction": [
    {
      "fold": 1,
      "baseline": "zero",
      "max_abs_difference": 0.0
    },
    {
      "fold": 1,
      "baseline": "last",
      "max_abs_difference": 0.0
    },
    {
      "fold": 1,
      "baseline": "mean28",
      "max_abs_difference": 0.0
    },
    {
      "fold": 1,
      "baseline": "mean90",
      "max_abs_difference": 0.0
    },
    {
      "fold": 1,
      "baseline": "seasonal56",
      "max_abs_difference": 0.0
    },
    {
      "fold": 1,
      "baseline": "tsb",
      "max_abs_difference": 0.0
    },
    {
      "fold": 2,
      "baseline": "zero",
      "max_abs_difference": 0.0
    },
    {
      "fold": 2,
      "baseline": "last",
      "max_abs_difference": 0.0
    },
    {
      "fold": 2,
      "baseline": "mean28",
      "max_abs_difference": 0.0
    },
    {
      "fold": 2,
      "baseline": "mean90",
      "max_abs_difference": 0.0
    },
    {
      "fold": 2,
      "baseline": "seasonal56",
      "max_abs_difference": 0.0
    },
    {
      "fold": 2,
      "baseline": "tsb",
      "max_abs_difference": 0.0
    },
    {
      "fold": 3,
      "baseline": "zero",
      "max_abs_difference": 0.0
    },
    {
      "fold": 3,
      "baseline": "last",
      "max_abs_difference": 0.0
    },
    {
      "fold": 3,
      "baseline": "mean28",
      "max_abs_difference": 0.0
    },
    {
      "fold": 3,
      "baseline": "mean90",
      "max_abs_difference": 0.0
    },
    {
      "fold": 3,
      "baseline": "seasonal56",
      "max_abs_difference": 0.0
    },
    {
      "fold": 3,
      "baseline": "tsb",
      "max_abs_difference": 0.0
    }
  ],
  "full_vs_180_and_ml_oof_reproduction": [
    {
      "fold": 1,
      "origin": "2026-01-20",
      "full_days": 751,
      "full_oof_max_abs_difference": 0.0,
      "short_full_max_abs_difference": 0.25654855528807696,
      "short_full_changed_predictions": 1408,
      "changed_features": [
        "long_mean"
      ],
      "full_metrics": {
        "smape": 166.15730535073962,
        "wape": 86.36603801986789,
        "rmse": 0.7170157110592179,
        "bias": 82.65221765561317,
        "rmsle": 0.30279180783983334,
        "mean_signed_series_bias": -65.76697866917922,
        "global_signed_volume_bias": -16.26712059891621
      },
      "short_metrics": {
        "smape": 166.15758390526506,
        "wape": 86.36562265715806,
        "rmse": 0.7170219399334996,
        "bias": 82.65399594464088,
        "rmsle": 0.3027941389626715,
        "mean_signed_series_bias": -65.76939054006013,
        "global_signed_volume_bias": -16.26685931900686
      }
    },
    {
      "fold": 2,
      "origin": "2026-03-25",
      "full_days": 815,
      "full_oof_max_abs_difference": 0.0,
      "short_full_max_abs_difference": 0.2546888063787308,
      "short_full_changed_predictions": 2855,
      "changed_features": [
        "long_mean"
      ],
      "full_metrics": {
        "smape": 162.00784460572268,
        "wape": 85.98702985641725,
        "rmse": 0.7646519376766182,
        "bias": 81.96409910972304,
        "rmsle": 0.30788379540892646,
        "mean_signed_series_bias": -64.715698800999,
        "global_signed_volume_bias": -18.151312685276558
      },
      "short_metrics": {
        "smape": 162.009279073772,
        "wape": 85.98177333915717,
        "rmse": 0.7646496932729916,
        "bias": 81.95542161044823,
        "rmsle": 0.3078784968310483,
        "mean_signed_series_bias": -64.73997585792887,
        "global_signed_volume_bias": -18.159801923022943
      }
    },
    {
      "fold": 3,
      "origin": "2026-05-28",
      "full_days": 879,
      "full_oof_max_abs_difference": 0.0,
      "short_full_max_abs_difference": 0.0,
      "short_full_changed_predictions": 0,
      "changed_features": [
        "long_mean"
      ],
      "full_metrics": {
        "smape": 158.6871617213434,
        "wape": 80.43006567684449,
        "rmse": 0.8662841487164723,
        "bias": 80.5655572662628,
        "rmsle": 0.3126153218811934,
        "mean_signed_series_bias": -62.834934485864856,
        "global_signed_volume_bias": -19.105414359749908
      },
      "short_metrics": {
        "smape": 158.6871617213434,
        "wape": 80.43006567684449,
        "rmse": 0.8662841487164723,
        "bias": 80.5655572662628,
        "rmsle": 0.3126153218811934,
        "mean_signed_series_bias": -62.834934485864856,
        "global_signed_volume_bias": -19.105414359749908
      }
    }
  ],
  "long_mean_tree_thresholds": [
    {
      "fold": 1,
      "long_mean_splits": 15,
      "minimum_threshold": 1.0000000180025095e-35,
      "maximum_threshold": 0.6621358394622804
    },
    {
      "fold": 2,
      "long_mean_splits": 21,
      "minimum_threshold": 1.0000000180025095e-35,
      "maximum_threshold": 0.14602261781692508
    },
    {
      "fold": 3,
      "long_mean_splits": 12,
      "minimum_threshold": 1.0000000180025095e-35,
      "maximum_threshold": 0.14325282722711566
    }
  ],
  "catalog": {
    "expansion_can_change_past_warehouse_means": true,
    "actual_fold_counts": [
      {
        "origin": "2026-01-20",
        "articles": 793,
        "warehouses": 11,
        "observed_pairs": 8664,
        "future_only_articles": 6
      },
      {
        "origin": "2026-03-25",
        "articles": 799,
        "warehouses": 11,
        "observed_pairs": 8751,
        "future_only_articles": 0
      },
      {
        "origin": "2026-05-28",
        "articles": 799,
        "warehouses": 11,
        "observed_pairs": 8774,
        "future_only_articles": 0
      }
    ],
    "fixed_official_grid": 8789
  },
  "initial_run": {
    "passed": 9,
    "failed": 1,
    "failure": "Reviewer assumption that all 799 articles were observed by each fold was false: first fold has 793. The official catalog is fixed, so this assertion was replaced with a measured count rather than called a production target-leakage defect."
  }
}
```

## Независимый verdict

CONDITIONAL PASS для temporal/features/inference paths: подтверждённых P0/P1 здесь не найдено. Итоговый release verdict требует отдельной проверки scoring/API/Docker/submission главным QA.

## Независимая проверка полного переобучения

Команда: `.venv\Scripts\python.exe reports/qa/check_temporal_independent.py --verify-retraining-only`. Независимо подтверждены **6/6** файлов моделей: SHA256 новых весов = SHA256 исходников = initial_manifest, 220 деревьев, objective, seed, threads, deterministic flags, training rows и cutoff. Финальный config независимо восстановлен из текущего feature schema, origins и frozen parameters без fit и точно совпал. Сами 6 fits исполнил root, reviewer их повторно не запускал. Одинаковые веса вместе с прежде независимо воспроизведённым inference подтверждают сохранение прогнозов; новые quality improvements не заявляются. Проверка остаётся ограничена текущими installed builds. Residual catalog fingerprint limitation P2 остаётся раскрытым.

```json
{
  "fits_verified_from_real_files": [
    {
      "name": "lgb_l2_fold1",
      "sha256": "aed4037d530f0e211d2c79bc8bc5b4043ebde0f142bd64ead78b98efba2507f4",
      "matches_original_and_initial_manifest": true,
      "trees": 220,
      "objective": "regression",
      "training_rows": 1124992
    },
    {
      "name": "lgb_l2_fold2",
      "sha256": "bfd0193db73f92e07221195a2c90a8ce80100c2cae105d842c135a6254efe52a",
      "matches_original_and_initial_manifest": true,
      "trees": 220,
      "objective": "regression",
      "training_rows": 1265616
    },
    {
      "name": "lgb_tweedie_fold1",
      "sha256": "83302aea9d8f928dfc321b3473c08a4cbc6a93a7d53b6ff52d9f618c996906de",
      "matches_original_and_initial_manifest": true,
      "trees": 220,
      "objective": "tweedie",
      "training_rows": 1124992
    },
    {
      "name": "lgb_tweedie_fold2",
      "sha256": "5aef199f1fa62e14bcb3747c5edf857084ea25a855e187d38027d82eb4e38a26",
      "matches_original_and_initial_manifest": true,
      "trees": 220,
      "objective": "tweedie",
      "training_rows": 1265616
    },
    {
      "name": "lgb_tweedie_z0.25_fold3",
      "sha256": "1ea7bea0035b14d3fa5eac726cff1201f08f243cc38ba311685a7b07d632d64a",
      "matches_original_and_initial_manifest": true,
      "trees": 220,
      "objective": "tweedie",
      "training_rows": 1406240
    },
    {
      "name": "final",
      "sha256": "ebc9bafee00b294793f0ef2b01e9b8d1b42825bc461dc7fa4cdb603496fb3b52",
      "matches_original_and_initial_manifest": true,
      "trees": 220,
      "objective": "tweedie",
      "training_rows": 1476552
    }
  ],
  "final_config_independently_reconstructed_equal": true,
  "new_fits_by_reviewer": 0,
  "scope": "The root reran full fits; independent reviewer checked actual weight bytes, hashes, embedded parameters and metadata. Same environment, not a cross-build reproducibility guarantee."
}
```
