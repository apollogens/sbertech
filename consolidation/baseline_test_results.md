# Исходная проверка

До изменения существующего кода запущена точная команда:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest tests reports/qa/check_backend_independent.py integration/test_catalog_policy.py integration/test_ensemble_engine.py -q
```

Результат: **193 passed**, 37.61 с, одно предупреждение Starlette об httpx. Область: 156 основных, 21 отдельный backend regression и 16 integration. Журнал — `baseline_tests.log`. Default pytest discovery и явная команда имеют разные области, поэтому числа без команды не сопоставляются.

Baseline зависимостей:33пакета в старом lock,42установленных distributions в `.venv` (включая pip). Проверка installed metadata и `pip check` отражена в dependency audit. Текущая `.venv` не уничтожается и не очищается на месте.
