# Проверка экспериментального standalone inference

Исполнен `integration/release/experimental180/verify_standalone.py`. Машинный результат: `release/experimental180/verification.json`, status passed. Это проверка экспериментального CLI, не новый HTTP/Docker-релиз.

Вход содержит ровно180дней, 2026-02-02—2026-07-31:448589строк sales и1142816строк очищенного stock. Исходный audit first-observed reader и `lightgbm.train` заменены функциями, немедленно вызывающими исключение; inference успешно выполняется без обращения к ним. Membership каталога строится из переданных sales, runtime не читает исходную обучающую выгрузку.

Для `equal4:P1` и `D:P1` выполнены по два полных вызова, каждый заново загружает три Booster, читает/очищает CSV, формирует features, четыре компонента и key alignment. Каждый CSV имеет562496строк,64дня, полный11×799grid. Повторные DataFrame совпали точно. Сохранённый `equal4_P1.csv` имеет SHA-256 `310d000f954f48e389661954c9a3d2ac38815d603bae7c9cfc40409015fbd164`. Подмена весов в manifest-bound config отвергнута; отдельная проверка подмены TXT описана в `model_tamper.json`.

На одном и том же180дневном входе текущий nonton-v1 выполнил полный read+clean+load+inference за7.650514с. Experimental equal4 —22.112056с, повтор22.713057с, около2.89× медленнее первого incumbent вызова. Это фактически измеренные последовательные прогоны, не статистическая оценка latency и не ускорение. Peak sampled experimental RSS —2239696896байт. Wrapper D:P1 также вычисляет все три Booster: его22.39с не является минимальной ценой отдельного daily компонента.

Три final TXT весят808013424байта, config содержит явные stable category encodings, weights, postprocessing, dependency versions и adapter hash. Большой размер связан с текущей sparse categorical сериализацией; его нельзя приписывать любому ансамблю вообще. Корректная оптимизация компактного model-local encoder могла бы изменить стоимость, но ещё не проверена.

Эта проверка не содержит будущих labels и не доказывает качество на180дневном input. Исторический development использует полную доступную историю; `long_mean` и known-ID evidence могут отличаться. Для переноса quality claims требуется отдельный production-like180-day backtest. Исходные production модели, API и submission в ходе проверки не менялись.
