"""Restore UTF-8 Russian fields after Windows stdin transcoding; no network/training."""
import csv
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'science_sources.csv'
with path.open(encoding='utf-8-sig', newline='') as stream:
    rows = list(csv.DictReader(stream))
fields = list(rows[0])
updates = {
    'SCI-TEMP': ('рецензируемая методология', 'Библиография проверена; авторский PDF открыт и теория прочитана выборочно; воспроизведения нет', 'Непересекающиеся суммы и согласование между частотами', 'Теряются дневная форма и число наблюдений; остаток h64 требует собственной адаптации'),
    'SCI-ADIDA': ('рецензируемая методология', 'Metadata подтверждены; полный текст не прочитан; прочитан прежний локальный отчёт', 'Агрегация и дезагрегация intermittent demand', 'Уже испытан по remediation; обучаемая недельная сумма — отдельная адаптация'),
    'SCI-MINT': ('рецензируемая методология', 'Подтверждены авторские metadata и abstract; код прочитан выборочно', 'Минимизация coherent MSE при несмещённых базовых прогнозах через covariance ошибок', 'Не оптимизирует официальный SMAPE/Bias; плотная covariance требует памяти и длинной истории'),
    'SCI-HF': ('официальная реализация', 'Выборочно прочитаны methods.py и pyproject; установки и запуска нет', 'BottomUp; TopDown требует дерева; MinTrace использует residuals; есть nonnegative flag и ERM', 'Пересечение warehouse/article не дерево; важен порядок строк и столбцов S'),
    'SCI-MERS': ('рецензируемая методология', 'DOI корректен; проверены publisher metadata и abstract; полный алгоритм не изучен', 'Неопределённость inventory может создавать отрицательное смещение оценки скрытого спроса', 'Target Nonton — observed sales; latent demand и future availability не идентифицированы'),
    'SCI-FRN': ('препринт и официальная реализация', 'Проверены metadata и abstract; выборочно прочитан SSA/recovery; воспроизведения нет', 'SSA:90+7 дней; discount и precipitation; evaluation фильтрует stock_hour6_22_cnt==0; recovery почасовой', 'Аналогичная разметка Nonton не установлена; доступность будущих covariates требует проверки; target отличается'),
    'SCI-NHITS': ('рецензируемая методология и официальная реализация', 'Проверены publisher metadata; прочитан NHITS source, выборочно BaseModel; запуска нет', 'Pooling, residual MLP, interpolation; в просмотренной версии default MAE', 'Иерархия NHITS — временная декомпозиция, не cross-sectional coherence; MAE может давать нули'),
    'SCI-TIDE': ('исследовательская статья и оригинальный код', 'Список авторов подтверждён arXiv/README; Google пропускает Shaan Mathur; код прочитан выборочно; воспроизведения нет', 'Residual MLP encoder-decoder; linear skip; MSE; scaler только по train range', 'TF2.10.1 и старые numpy/pandas конфликтуют с production; предполагаются известные будущие global covariates'),
    'SCI-TIDE-NF': ('официальная поддерживаемая библиотечная реализация', 'Прочитаны model source и pyproject; install/import не проверены', 'PyTorch residual MLP; historic/future/static covariates; default MAE', 'Runtime и objective отличаются от оригинального TF; эквивалентность не заявлена'),
}
for row in rows:
    if row['source_id'] in updates:
        for key, value in zip(['evidence_type', 'verification_status', 'verified_claims', 'assumptions_and_nonton_differences'], updates[row['source_id']]):
            row[key] = value
        row['nonton_validation_status'] = 'Не испытано этой ролью; прежние локальные результаты отделены от новой проверки'
if not any(row['source_id'] == 'SCI-MAFILDES' for row in rows):
    rows.append(dict(zip(fields, [
        'SCI-MAFILDES',
        'The performance of the global bottom-up approach in the M5 accuracy competition: A robustness check',
        'Shaohui Ma; Robert Fildes',
        'International Journal of Forecasting 38(4):1492-1499',
        '2022',
        '10.1016/j.ijforecast.2021.09.002',
        'https://doi.org/10.1016/j.ijforecast.2021.09.002',
        'https://eprints.lancs.ac.uk/id/eprint/159736/',
        '',
        'Accepted manuscript: CC BY-NC-ND по Lancaster; code license не установлена',
        'рецензируемая методология',
        'Metadata, DOI, abstract и статус accepted manuscript подтверждены Lancaster; DOI endpoint недоступен web-tool; полный алгоритм не воспроизведён',
        'Авторы проверяют устойчивость global bottom-up по разным временным периодам и рекомендуют rolling test sets',
        'Устойчивость внешнего M5 не устанавливает качество Nonton; повторное использование окон не создаёт untouched test',
        'Не испытано; источник обосновывает осторожную интерпретацию повторно используемых окон',
    ])))
with path.open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
assert not any('???' in value or '\ufffd' in value for row in rows for value in row.values())
print(f'{len(rows)} records; UTF-8 fields restored and checked')
