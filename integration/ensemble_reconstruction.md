# Реконструкция ансамбля и округления

19 октября 2026. Исполнено `.venv/Scripts/python.exe -X utf8 integration/source_audit/verify_source_fixtures.py`; все assertions прошли. NumPy **2.5.4**. Машинный отчёт: `source_audit/source_fixture_results.json`. Это проверка выбранных функций реального исходника с synthetic boosters, а не обучение чужой модели или тест качества на Nonton.

## Проверенные формулы

Внешний Nonton `filipp880/forecast-64-v1@f8a8c6e60edaf12af2fd351e290c35e6875afea0`: `F=.3*I(p>=.5)*m+.7*expm1(l)`. Переменные — hurdle probability, положительная magnitude и log1p-прогноз LightGBM. Все величины сначала возвращаются в исходную шкалу. Финальный postprocessing: `x=max(F,0)`, при `t>0` значения `x<t` обнуляются, при round_int — `rint(x)`. В config `t=0`, round_int=true. Fixtures подтвердили [.7,2.7,4.7] для H=[0,2,4], L-original=[1,3,5], и equality gate .5 включается.

Общая адаптация Nonton: `F_k=sum_j(w_j*f_j(k))`, `w_j>=0`, `sum w=1`, ключ `k=(date,warehouse_name,article)`. Equal mean — `w_j=1/J`. Никакого восстановления source hurdle из нашей weekly модели эта формула не делает. Источники конкретных forecasting arrays и веса должны быть в manifest каждого опыта; weights .3/.7 не становятся learned weights. Нужна отдельная проверка полноты ключей, origin, horizon и hashes каждого компонента.

M5 A1 в исследовательском clone подтверждает alignment по ID и равное среднее 6 forecasts; это другая ветвь источников. Favorita README заявляет seed-усреднение и weighted family average, но исполняемый final combiner/weights не обнаружен. Его точный ансамбль воспроизводить или приписывать Nonton нельзя.

Supplemental AST fixtures также исполнены: шесть M5 CSV-таблиц с обратным порядком `b,a` выровнены по `a,b` и дали F1=[3.5,7.0]; реальный Favorita `make_submission` получил synthetic test table без чтения внешних данных и записал `.123456→0.1235`, `1200→1000.0000` в `StringIO`. Исходные функции/assignment nodes исполняются только в памяти, результаты и file hashes сохранены. Это проверяет конкретные операции, не полноту missing ensemble Favorita и не принадлежность к пользовательской паре.

## Семантика округления

[Документация NumPy 2.5](https://numpy.org/doc/2.5/reference/generated/numpy.rint.html), проверена 19.10.2026: `rint` округляет точную половину к ближайшему чётному целому. Исполнены `0.5→0`, `1.5→2`, `2.5→2`, `3.5→4`, zero, small positives, крупное 1e12, а также `nextafter` ниже/выше .25 и .5. При threshold=.25 само .25 сохраняется до округления; strict `<` не равно `<=`. Повторный вызов дал тот же результат. Возвращаемый dtype source float64; целочисленное значение не требует integer CSV type.

При P1 threshold=.25 и P3 threshold=.25→integer rounding для любых неотрицательных конечных x P3 совпадает с P2 rounding: все x<.25 и так округляются в zero. Это предсказуемая эквивалентность, а не два независимых источника улучшения.

Порядок нелинеен: mean(.4,.8)=.6, round(mean)=1; mean(round(.4),round(.8))=.5. Source rounding идёт после blend. Для threshold тоже требуется отдельный order ablation. Ни threshold, ни integer rounding не сохраняют sums по warehouse, article или 7-day buckets. Coherent raw прогноз может перестать быть coherent. Volume-preserving allocation не обнаружен и source не приписывается.

На nonfinite source postprocessor возвращает NaN/+Inf и обнуляет -Inf после clip. Это наблюдение fixture, не допустимый контракт Nonton: собственный engine должен отклонять nonfinite до комбинации и postprocessing. Подмена этих значений нулями замаскирует неисправный компонент.

Favorita `Utils.make_submission`: `expm1→clip[0,1000]→CSV %.4f`; четыре знака CSV отличаются от integer rounding и не обеспечивают сохранения суммы. Clip=1000 зависит от чужой задачи и не переносится. В Nonton quantity допускает непрерывные анонимизированные значения; конкретный judge contract следует подтверждать по локальному ТЗ, а не по наличию round_int во внешнем проекте.

## Научные источники и ограничения

[Wang, Hyndman, Li, Kang (2023)](https://robjhyndman.com/publications/combinations/), *Forecast combinations: an over 50-year review*, IJF 39(4), 1518–1547, DOI [10.1016/j.ijforecast.2022.11.005](https://doi.org/10.1016/j.ijforecast.2022.11.005): авторская страница подтверждает metadata, диапазон от простых фиксированных комбинаций до обучаемых. Это обоснование изучать комбинации, а не свидетельство улучшения Nonton. Проверена авторская metadata/аннотация; полный обзор не выдаётся за прочитанный.

[Официальный пример stacking scikit-learn](https://scikit-learn.org/stable/auto_examples/ensemble/plot_stack_predictors.html) проверен как первичная документация о meta-model. Хронологические OOF и отдельная оценка обязательны для нашей постановки; обычное CV примера не переносится автоматически. Несколько многократно изученных origins не поддерживают множество свободных weights по SKU/horizon.

M5 Results DOI [10.1016/j.ijforecast.2021.11.013](https://doi.org/10.1016/j.ijforecast.2021.11.013) при новом открытии вернул 403. Его полный текст в этой работе не прочитан; прежняя библиография в `research/competition_solutions.md` и исходный M5 combiner отделены от нового подтверждения. Никакие внешние конкурсные места не используются как доказательство качества Nonton.

Принцип переноса: independently coded arithmetic mean/convex blend + exact NumPy rounding, явный source gap и license limits. Утверждение «два пользовательских GitHub решения успешно интегрированы» имеющимися доказательствами не поддерживается.
