# Публикация проекта на GitHub

Репозиторий: https://github.com/apollogens/sbertech, основная ветка `main`.

В Git опубликованы исходники, конфигурация, тесты, Docker, определения зависимостей и исследовательские отчёты. Крупные веса, научные NPZ, архивы выпусков/отката и большие forecast CSV хранятся через Git LFS. Сторонние исследовательские клоны, локальные окружения, входные sales/stock CSV, кэш и дубли распакованных выпусков исключены; они не удаляются с рабочей машины.

```powershell
git lfs install
git clone https://github.com/apollogens/sbertech.git
cd sbertech
git lfs pull
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
.venv/Scripts/python.exe -m src.cli test
```

Git LFS нужен также для прежнего ZIP fixture, используемого regression tests. При обычном клонировании с установленным Git LFS объекты скачиваются автоматически. Для загрузки только необходимых serving-файлов используйте selective LFS pull; полный pull включает исторические веса и rollback.

Переводы строк не нормализуются Git: `.gitattributes` сохраняет исходные байты, поскольку manifests связывают некоторые Python-файлы и модели по SHA-256. Прогнозная логика и веса при публикации не менялись. Файлы самого Git-оформления добавлены после frozen release; существующий проверенный ZIP и его manifest не переписываются задним числом.

Активная стратегия — `nonton-v1`, кандидат — `bundles/equal4-rc1` / `equal4:P1`. Команды запуска приведены в корневом README. Итоговый архив — `consolidation/nonton_consolidated_verified.zip`; его исходный SHA-256: `d2306a62b61e7817ccaaa7c2036e4d6019995df72e7a737dc16b73f3a7466803`.
