"""Fetch public hourly aggregates and atomically publish a seven-day Prophet forecast."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCE = 'https://data.sf.gov/resource/nuek-vuh3.json'
SF = ZoneInfo('America/Los_Angeles')


def fetch(params):
    request = Request(SOURCE + '?' + urlencode(params), headers={'User-Agent': 'EMSForecast/1.0', 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=90) as response:
                result = json.load(response)
            if not isinstance(result, list):
                raise ValueError('Unexpected DataSF response')
            return result
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def normalize(rows, start, end):
    """Absent hours in a successfully fetched complete day have zero dispatches."""
    values = {}
    for row in rows:
        stamp = datetime.fromisoformat(row['day']).replace(hour=int(row['hour']))
        count = float(row['dispatch_count'])
        if not start <= stamp < end or stamp in values or not math.isfinite(count) or count < 0 or count != int(count):
            raise ValueError('Invalid or duplicate hourly aggregate')
        values[stamp] = int(count)
    result = []
    current = start
    while current < end:
        result.append({'time': current.isoformat(), 'dispatches': values.get(current, 0)})
        current += timedelta(hours=1)
    for i in range(0, len(result), 24):
        if sum(r['dispatches'] for r in result[i:i+24]) == 0:
            raise ValueError('Entire day missing from source; refusing to fill it with zeros')
    return result


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def forecast(history, start):
    # Fixed seasonal model: no future lag regressors and no tuning on test data.
    import pandas as pd
    from prophet import Prophet
    frame = pd.DataFrame({'ds': [r['time'] for r in history], 'y': [r['dispatches'] for r in history]})
    frame['ds'] = pd.to_datetime(frame.ds)
    def model():
        return Prophet(daily_seasonality=True, weekly_seasonality=True,
                       yearly_seasonality=False, uncertainty_samples=0,
                       changepoint_prior_scale=.01)
    holdout = 14 * 24
    check = model().fit(frame.iloc[:-holdout], seed=42)
    predicted = check.predict(frame.iloc[-holdout:][['ds']]).yhat.clip(lower=0)
    mae = float((predicted.to_numpy() - frame.y.iloc[-holdout:].to_numpy()).__abs__().mean())
    fitted = model().fit(frame, seed=42)
    future = pd.DataFrame({'ds': pd.date_range(start, periods=7*24, freq='h')})
    output = fitted.predict(future)
    rows = [{'time': stamp.isoformat(), 'prediction': round(max(0, float(value)), 3)}
            for stamp, value in zip(output.ds, output.yhat)]
    if any(not math.isfinite(r['prediction']) for r in rows):
        raise ValueError('Non-finite forecast')
    days = []
    for i in range(0, len(rows), 24):
        block = rows[i:i+24]
        peak = max(block, key=lambda r: r['prediction'])
        days.append({'date': block[0]['time'][:10], 'prediction': round(sum(r['prediction'] for r in block), 1),
                     'peakHour': peak['time'][11:16], 'peakPrediction': peak['prediction'], 'hours': len(block)})
    return rows, days, mae


def run(directory, now=None, lookback=180):
    if not 60 <= lookback <= 365:
        raise ValueError('Training window must be between 60 and 365 days')
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(SF).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    result = fetch({'$select': 'max(dispatch_dttm) as latest', '$where': "unit_type='MEDIC'"})
    latest = datetime.fromisoformat(result[0]['latest'])
    if latest > now.astimezone(SF).replace(tzinfo=None) + timedelta(hours=1):
        raise ValueError('Source timestamp lies in the future')
    if today - latest > timedelta(days=3):
        raise ValueError('Source is more than three days behind; retaining previous forecast')
    # Exclude the latest source day completely; late arrivals can revise previous days.
    end = min(today, latest.replace(hour=0, minute=0, second=0, microsecond=0))
    start = end - timedelta(days=lookback)
    params = {'$select': 'date_trunc_ymd(dispatch_dttm) as day,date_extract_hh(dispatch_dttm) as hour,count(distinct rowid) as dispatch_count',
              '$where': "unit_type='MEDIC' AND dispatch_dttm >= '" + start.isoformat() + "' AND dispatch_dttm < '" + end.isoformat() + "'",
              '$group': 'day,hour', '$order': 'day,hour', '$limit': '10000'}
    raw = fetch(params)
    if len(raw) >= 10000:
        raise ValueError('Source query may be truncated')
    history = normalize(raw, start, end)
    rows, days, mae = forecast(history, today)
    generated = now.isoformat()
    value = {'schemaVersion': 1, 'generatedAt': generated, 'timezone': 'America/Los_Angeles',
             'source': SOURCE, 'sourceLatest': latest.isoformat(), 'observedThrough': (end - timedelta(hours=1)).isoformat(),
             'trainingStart': start.isoformat(), 'trainingHours': len(history),
             'sourceSha256': hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
             'model': 'Prophet seasonal', 'target': 'medic-dispatches', 'unit': 'dispatches',
             'timeField': 'dispatch_dttm', 'identityField': 'rowid',
             'versions': {name: version(name) for name in ('prophet', 'pandas')},
             'validation': {'method': 'last-14-days-holdout', 'hours': 336, 'mae': round(mae, 3)},
             'rows': rows, 'days': days,
             'note': 'Daily estimates from completed historical days; not live dispatch instructions. Local wall-clock hours; DST days use 24 model slots.'}
    directory = Path(directory)
    atomic_json(directory / 'hourly-history.json', {'source': SOURCE, 'target': 'medic-dispatches', 'timeField': 'dispatch_dttm', 'fetchedAt': generated, 'rows': history})
    atomic_json(directory / 'archive' / ('history-medic-dispatches-' + now.strftime('%Y%m%d') + '.json'), {'source': SOURCE, 'target': 'medic-dispatches', 'timeField': 'dispatch_dttm', 'fetchedAt': generated, 'rows': history})
    atomic_json(directory / 'archive' / (now.strftime('%Y%m%dT%H%M%SZ') + '-medic-dispatches.json'), value)
    atomic_json(directory / 'forecast.json', value)
    atomic_json(directory / 'status.json', {'lastAttempt': generated, 'lastSuccess': generated, 'ok': True})
    print('Published:', len(rows), 'hours /', len(days), 'days; observed through', value['observedThrough'], flush=True)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--lookback-days', type=int, default=180)
    args = parser.parse_args()
    try:
        run(args.output_dir, lookback=args.lookback_days)
    except Exception as error:
        # Keep the last successful forecast, report a failed refresh separately.
        status_path = args.output_dir / 'status.json'
        try:
            status = json.loads(status_path.read_text())
        except (OSError, ValueError):
            status = {}
        atomic_json(status_path, {'lastAttempt': datetime.now(timezone.utc).isoformat(),
                                 'lastSuccess': status.get('lastSuccess'), 'ok': False,
                                 'error': type(error).__name__})
        raise


if __name__ == '__main__':
    main()
