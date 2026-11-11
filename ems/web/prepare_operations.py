"""Bundle reproducible H24 forecasts and existing capacity reports for the web.

Run offline: python -m ems.web.prepare_operations --source-ref <revision>
The HTTP server needs only the resulting JSON; no ML dependencies at runtime.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from ems.paths import ROOT
from ems.web.prepare_dashboard import parse_predictions


def capacity_rows(raw, expected):
    rows = list(csv.DictReader(io.StringIO(raw)))
    if [(r['timestamp'].replace(' ', 'T'), float(r['actual_dispatches'])) for r in rows] != expected:
        raise ValueError('Capacity timestamps/actuals differ from forecast results')
    result = []
    names = {'prophet_h24': 'Prophet 24h', 'sarimax_h24': 'SARIMAX 24h', 'lstm_h24': 'LSTM 24h block'}
    for row in rows:
        item = {'time': row['timestamp'].replace(' ', 'T'), 'need': float(row['need_actual']), 'plans': {}}
        for key, name in names.items():
            item['plans'][key] = {}
            for policy, label in [('mean', 'Trung bình'), ('p90', 'P90')]:
                plans = {}
                for field, prefix in [('hourly', 'plan_hourly'), ('shift8', 'plan_shift | 3 ca × 8h'), ('shift12', 'plan_shift | 2 ca × 12h')]:
                    value = row[f'{prefix} | {name} | {label}']
                    plans[field] = float(value) if value else None
                item['plans'][key][policy] = plans
        result.append(item)
    return result


def prepare(source_ref, destination=ROOT / 'outputs/web/dataset.json'):
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', source_ref + '^{commit}'], cwd=ROOT, text=True).strip()
    sources = {}

    def read(path):
        raw = subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=ROOT)
        sources[path] = hashlib.sha256(raw).hexdigest()
        return raw.decode('utf-8-sig')

    destination = Path(destination)
    value = json.loads(destination.read_text(encoding='utf-8'))
    profiles = value['profiles']
    prophet_path = 'outputs/prophet/day_ahead_24h/test_selected/predictions_24h.csv'
    prophet = parse_predictions(read(prophet_path), 24)
    expected = [(r['time'], r['actual']) for r in prophet]
    if len(expected) != 6796:
        raise ValueError('Expected 6796 scored hours')
    sar_path = 'outputs/sarimax/norefit/pred_sarimax.csv'
    sar = list(csv.DictReader(io.StringIO(read(sar_path))))
    meta = json.loads(read('outputs/sarimax/norefit/metrics.json'))
    if meta.get('refit') is not False:
        raise ValueError('SARIMAX must use the no-refit experiment')
    # Isolate source code/data/weights so this UI branch never changes model files.
    archive = subprocess.check_output(['git', 'archive', revision, 'ems', 'data', 'checkpoints/lstm'], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='ems-web-inference-') as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter='data')
        script = r'''
import json, torch, numpy as np
from ems.models.lstm.preprocess import load_data, load_scalers, scale_data, create_block_sequences, make_dataloader
from ems.models.lstm.model import VanillaLSTM
from ems.models.lstm.evaluate import predict_24h_blocks
from ems.models.lstm.config import DEVICE
torch.set_num_threads(2)
_,_,xv,yv,xt,yt=load_data()
fs,ts=load_scalers()
xv,yv=scale_data(xv,yv,fs,ts)
xt,yt=scale_data(xt,yt,fs,ts)
x,y=create_block_sequences(np.concatenate([xv[-24:],xt]),np.concatenate([yv[-24:],yt]),24,24,24)
c=torch.load('checkpoints/lstm/vanilla_24h_block_best.pth',map_location='cpu',weights_only=True)
if c['run_name']!='vanilla_24h_block': raise ValueError('Wrong checkpoint')
m=VanillaLSTM(forecast_horizon=24).to(DEVICE)
m.load_state_dict(c['model_state'])
a,p=predict_24h_blocks(m,make_dataloader(x,y,128),ts,n_target_hours=len(yt))
print(json.dumps({'actual':a.tolist(),'prediction':p.tolist()}))
'''
        inference = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-c', script], cwd=tmp, text=True))
    for path in ['checkpoints/lstm/vanilla_24h_block_best.pth', 'checkpoints/lstm/feat_scaler.pkl', 'checkpoints/lstm/tgt_scaler.pkl', 'ems/models/lstm/preprocess.py']:
        raw = subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=ROOT)
        sources[path] = hashlib.sha256(raw).hexdigest()
    if len(sar) != len(expected) or len(inference['prediction']) != len(expected):
        raise ValueError('Forecast length mismatch')
    sar_rows, lstm_rows = [], []
    for i, base in enumerate(prophet):
        r = sar[i]
        timestamp = r.get('timestamp', r.get('ds', '')).replace(' ', 'T')
        if timestamp != base['time'] or float(r['actual']) != base['actual'] or abs(inference['actual'][i] - base['actual']) > 1e-4:
            raise ValueError('Models must share timestamps and actuals')
        sar_rows.append({**base, 'prediction': float(r['pred'])})
        lstm_rows.append({**base, 'prediction': inference['prediction'][i]})
    for key, name, rows, path in [('prophet_h24', 'Prophet', prophet, prophet_path), ('sarimax_h24', 'SARIMAX', sar_rows, sar_path), ('lstm_h24', 'LSTM', lstm_rows, 'checkpoints/lstm/vanilla_24h_block_best.pth')]:
        profiles[key] = {'name': name, 'horizon': 24, 'rows': rows, 'source': path, 'revision': revision, 'sha256': sources[path], 'trainEnd': '2024-12-31T23:00:00', 'description': 'Phát hành lúc 00:00; dự báo cả ngày, không cập nhật bằng thực tế trong ngày.'}
    capacity = capacity_rows(read('outputs/queuing/vehicle_plans_hourly.csv'), expected)
    value['operations'] = {'revision': revision, 'rho': 0.8, 'hourCount': 6796, 'shiftHourCount': 6792, 'excludedHours': 4, 'ratios': [2, 3, 5, 10, 20], 'sources': sources, 'rows': capacity,
                           'reports': {name: list(csv.DictReader(io.StringIO(read(f'outputs/queuing/{name}.csv')))) for name in ['evaluation_hourly', 'evaluation_shifts']}}
    # Validate numeric values before replacing an existing usable snapshot.
    body = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    destination.write_text(body, encoding='utf-8')
    print(f'Prepared 3 H24 models / {len(capacity)} hours from {revision}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-ref', required=True)
    parser.add_argument('--destination', type=Path, default=ROOT / 'outputs/web/dataset.json')
    args = parser.parse_args()
    prepare(args.source_ref, args.destination)
