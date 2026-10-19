# Лицензии и границы повторного использования

Проверка 19.10.2026: выбранные файлы скачаны как текст для чтения; чужие setup/train не выполнялись. [Manifest](source_inspection/manifest.json) содержит точные raw URL, commit и SHA-256. Загруженные исходники сохраняют upstream headers. Новые research-отчёты пересказывают механизмы самостоятельно; production-код из этих проектов не скопирован.

| Источник | Проверенный снимок и LICENSE | Разрешённый путь |
|---|---|---|
| Nixtla/hierarchicalforecast | `56cc4fac0c5c7b4ff33884d4a8a929f3cd8f03ec`, [Apache-2.0](https://github.com/Nixtla/hierarchicalforecast/blob/56cc4fac0c5c7b4ff33884d4a8a929f3cd8f03ec/LICENSE) | Библиотечное использование или адаптация с соблюдением LICENSE/NOTICE и attribution |
| Nixtla/neuralforecast | `6c11accfbcfdd62a40ef69a7c81e3d9c7f272682`, [Apache-2.0](https://github.com/Nixtla/neuralforecast/blob/6c11accfbcfdd62a40ef69a7c81e3d9c7f272682/LICENSE) | Аналогично; зависимости и pretrained weights проверять отдельно |
| Dingdong-Inc/frn-50k-baseline | `8af694a09a5a427d1d50648d348c022565a781f2`, [Apache-2.0](https://github.com/Dingdong-Inc/frn-50k-baseline/blob/8af694a09a5a427d1d50648d348c022565a781f2/LICENSE) | Root license подтверждена; repository содержит заимствования PyPOTS и других проектов — перед reuse конкретного файла нужны его headers и dependency licenses |
| google-research/google-research, tide | `3ef52111c1fabc301880818f5a547570e926a76b`, [Apache-2.0](https://github.com/google-research/google-research/blob/3ef52111c1fabc301880818f5a547570e926a76b/LICENSE) | Root LICENSE и headers выбранных Python файлов проверены; самостоятельная реализация идеи тоже допустима |
| Статьи Temporal Hierarchies / ADIDA / MinT / Mersereau | DOI и авторство подтверждены; blanket license на копирование текста не установлена | Ссылки и самостоятельное изложение метода. Публичный PDF не приравнивается к open-source code |
| FreshRetailNet статья/датасет | Статья arXiv и ссылка на data проверены; license самого dataset в этой роли не проверялась | Dataset не загружался и не использован в Nonton. Apache кода не распространяется автоматически на данные |
| NHITS / TiDE статьи | Проверены publisher/arXiv metadata; права статьи и кода различаются | Для алгоритма — собственное изложение; для кода — Apache конкретного repository snapshot |

Лицензии подтверждают возможность определённых форм reuse, но не соответствие правилам соревнования и не качество на Nonton. Нет предположения, что любые чужие данные разрешены. Это техническая инвентаризация, не юридическое заключение и не полный transitive dependency audit. `thief` и оригинальный ADIDA code не скачивались; разрешение на их копирование здесь не установлено. Существующий локальный StatsForecast benchmark описан в предыдущих отчётах; его лицензия заново не проверялась этой ролью.

Дополнительно проверен [Ma, Fildes — Lancaster accepted manuscript](https://eprints.lancs.ac.uk/id/eprint/159736/): Creative Commons Attribution-NonCommercial-NoDerivs (CC BY-NC-ND). Использованы библиографическая ссылка и самостоятельное краткое изложение вывода об устойчивости; текст manuscript не переносился в код или production. Оригинальная implementation license не установлена.
