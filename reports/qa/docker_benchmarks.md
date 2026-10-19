# Docker и ресурсы — фактический аудит

Финальный tag `nonton-qa-audit:verified`, image ID `sha256:393a092aeffb3159d5059aae2026dcc7426eff7321b4b39b88d5a0f0642f71a7`, размер148,784,934bytes (<30GB). Host: Windows10build19045,16logicalCPUs,16,964,587,520bytes RAM; Docker Desktop4.88.0 (237115)/Engine29.7.2; runtime LinuxWSL2 amd64,Python3.12.15 (main, Oct 6 2026, 02:02:22) [GCC 14.2.0]. GPU не использовался. Container: --network none,--memory=6g,--cpus=4; memory plus swap limit12GiB отдельно раскрыт в JSON.

No-cache dependency build до финальных source-исправлений69.366517s; финальный COPY rebuild с cache2.296653s. Это разные измерения, не единая чистая сборка финального дерева. Зависимости устанавливались при build; модель никаких downloads при startup/inference не делает. Train/source CSV не входят в image; после старта inputs временно копировались в/tmp и передавались реальным HTTP loopback внутри network-none.

| Операция | Измерение | Лимит |
|---|---:|---:|
| Full real POST | 33.768355s | 3600s |
| Repeat POST | 32.386739s | 3600s |
| GET full CSV | 0.890852s | 600s |
| GET full JSON | 0.483800s | 600s |
| cgroup memory peak | 3,753,984,000B | 64GB |
| Server sampled peak RSS | 3,223,523,328B | описательная метрика |
| CPU process | 81.12CPU-s | 4CPU assigned |
| Probe total wall | 70.388999s | не равно POST latency |

cgroup включает память probe/сервера/файлового cache; RSS выборочно измерялся каждые0.1s и может пропустить короткий пик. Нет утверждений о другом hardware или RAM на произвольных размерах входа. Вход450MB читается целиком; streaming реализован для выхода. Все лимиты пройдены на фактически проверенном входе.

Exact full Cartesian keys и finite nonnegative quantities проверены. Offline/API maxdiff3.5527136788005009e-15<1e-7; repeated bytes identical. После restart cache409; отсутствующий MODEL_DIR остановил startup exit1 ожидаемо. Контейнер аудитора удалён, финальный image сохранён. Production weights/config/catalog hashes совпали с начальным manifest; runtime source hashes внутри image записаны в docker_benchmark.json и сверены root с рабочим деревом.

LightGBM параметры deterministic=true,force_col_wise=true,seed20261018,num_threads4,version4.7.0 соответствуют [официальной документации](https://lightgbm.readthedocs.io/en/stable/Parameters.html). Она ограничивает гарантию стабильности одинаковыми builds/данными/параметрами; межплатформенная parity здесь отдельно измерена. Системный base tag/apt не pinned by digest, будущая bitwise rebuild не доказана. JSON с точными командами, версиями и измерениями — docker_benchmark.json; протокол — reviewer_backend.md. Signoff:PASS для проверенного окружения.
