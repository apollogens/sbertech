# Паритет официальных метрик

Источники: оригинальное ТЗ раздел9.2 и неизменённый scripts/official_score.py; normalized SHA256 `a2c9348de0232eeede99948fb6640241de6593cd665d0048145ea4d88272f9cc`. Дословное совпадение и AST подтверждены независимым reviewer. Подробный протокол — reviewer_metrics.md, машинные факты — metrics_independent.json.

SMAPE: внутри ряда среднее только по days с `(abs(actual)+abs(pred))/2 >0`; затем равное среднее по рядам. Полностью zero/zero ряд даёт0. Написанная формула сохраняет zero/zero как0; fixture actual[0,0,0,10],pred[0,0,0,0] даёт written50%, evaluator200%. Оба варианта реализованы и протестированы отдельно.

WAPE:100*sum(abs(error))/sum(abs(actual)); zero denominator→0 по scorer. RMSE:sqrt(mean(error²)) globally. RMSLE:sqrt(mean((log1p(pred)-log1p(actual))²)) globally. Истинные значения должны быть конечными и неотрицательными. Массивная production metric функция намеренно повторяет official NaN prediction→0 и negative prediction→0; бесконечности отклоняются. Output submission/API отдельно отвергает NaN/Inf/negative и не полагается на scorer sanitization.

Bias: отдельно100*abs(sum(pred_s)-sum(actual_s))/abs(sum(actual_s)), затем среднее eligible рядов. Actual total0 исключается; когда все исключены, scorer fallback0 является неинформативным. Epsilon не добавляется. Обязательный fixture A[0,10]→[0,8]:20% и signed−20%; B[2,2]→[4,4]:100% и signed+100%; C[0,0]→[1,1] исключается. Среднее60%, signed mean40%, global signed28.5714286% с учетом прогноза C. Fixtures perfect/over/under/allzero/tiny positive/low-volume over/same totals/different pattern/order/NaN/Inf/missing duplicate keys включены в26 root QA regressions и independent scripts.

Все31 saved OOF пересчитаны независимой реализацией из raw-reconstructed truth. max abs deviation пяти метрик/score5.684341886080802e-14; tolerance1e-10. Supplied keyed scorer дополнительно исполнялся на идентичных синтетических ключах и6 реальных рядах каждого OOF; не утверждается, что медленный scorer31раз запускался на всём grid. Все6 baseline на3fold воспроизведены побитово, OOF alignment подтверждён catalog/даты/реальными prediction paths. Missing/duplicate submission keys отдельно отклоняются stronger submission validator по полному grid.

Minmax:ideal0,baseline1,clip worse→1,zero base:value0→0 иначе1. Metric weights50/20/15/10/5%; weighted score применяется после нормировки. Rank:argsort ranks0..N−1, деление наN−1; singleton0. Равные значения получают разные ranks и зависят от порядка submissions; это унаследованное поведение evaluator, оригинал сохранён.

ТЗ ожидает rank, хотя code/default поддерживает minmax. Текущий frozen selection использует честно обозначенный local minmax: Tweedie z.25 mean .8323826469 против L2 z.25 .8337666652. На тех же12 кандидатах rank чувствительность предпочитает L2 z.25 .20681818 против Tweedie .22727273. Официальный leaderboard неизвестен, его балл не заявляется; повторная оптимизация по открытому holdout не проводилась.

Signoff Agent A:PASS после root validation fixes,13 metric tests прошли повторно, все14 Bias diagnostics×3fold независимо подтверждены. Обнаруженных численных defects метрик нет. Остались upstream SMAPE prose/code и rank ties discrepancies; они не скрыты исправлением scorer.
