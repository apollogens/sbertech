# Выполненная миграция

1. Созданы immutable snapshot и inventory до изменений; Git HEAD отсутствует, фиктивного commit нет.
2. Три первоначальных read-only аудита завершены до распределения реализации.
3. Выделены src.catalog/temporal/ensemble/components; добавлены runtime dispatcher и один CLI. Шесть hash-bound incumbent модулей сохранены точно.
4. Новый runtime-v2 bundle сохраняет исходные три TXT побайтово; manifest содержит parent hashes, catalogs, encoder, features, dependencies и runtime sources. Последующая source-only reseal сохраняет старый manifest в runtime_manifest_history и отвергает изменение весов.
5. До удаления чего-либо доказана реальная численная регрессия; затем отдельно пересобраны locks и новые среды.
6. Четыре исторических файла делегируют общие расчёты каноническим модулям; шесть дублирующих инструментов архивированы и удалены из активного дерева. Ledger — deleted_files_and_reasons.csv, архив проверен до unlink. scripts/predict.py сохранён как тонкий адаптер публичных legacy flags.
7. Старые source-bound manifests/ZIP/models не переписаны. Их исторические команды исполняются после восстановления frozen source из pre_merge_snapshot.zip. Для текущих predict/package/API/Docker используется новый CLI. Общие исследования, evidence, scorer и исходные данные сохранены.
8. Проверены 180-day inputs, clean tests, оба Docker images, restart и rollback. Peer review выявил и исправил выбор strategy в Docker CLI и config кандидата.

Внешний код не копировался. Подтверждён только filipp880/forecast-64-v1; второй пользовательский проект не найден. Из-за отсутствия лицензии перенесена самостоятельно реализованная идея смеси/postprocessing.
