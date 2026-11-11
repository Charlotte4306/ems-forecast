"""Validate forecast artifacts before comparing vehicle-capacity plans."""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_sarimax_day_ahead(prediction_path, metadata_path, actual, training_end):
    """Require a frozen train-only 24h run aligned with the evaluation target.

    Metadata and predictions are checked together so an old refit CSV cannot
    silently be reused with the new experiment's metadata.
    """
    metadata = json.loads(Path(metadata_path).read_text(encoding='utf-8'))
    if metadata.get('refit') is not False or metadata.get('horizon_hours') != 24:
        raise ValueError('Capacity comparison requires SARIMAX 24h with refit=false')
    fit_end = pd.Timestamp(metadata['final_fit']['end'])
    if pd.isna(fit_end) or fit_end > pd.Timestamp(training_end):
        raise ValueError('SARIMAX parameters were fitted after the common training cutoff')
    frame = pd.read_csv(prediction_path, parse_dates=['timestamp']).set_index('timestamp')
    columns = ['actual', 'pred', 'lo', 'hi']
    if not frame.index.equals(actual.index) or not np.array_equal(frame['actual'].to_numpy(), actual.to_numpy()):
        raise ValueError('SARIMAX timestamps/actuals do not match the shared test hours')
    if not np.isfinite(frame[columns].to_numpy()).all():
        raise ValueError('SARIMAX predictions contain non-finite values')
    if (frame[columns] < 0).any().any() or not ((frame.lo <= frame.pred) & (frame.pred <= frame.hi)).all():
        raise ValueError('SARIMAX predictions or interval bounds are invalid')
    errors = np.abs(frame.actual.to_numpy() - frame.pred.to_numpy())
    reported_mae = metadata['test_metrics']['all_test']['MAE']
    if not np.isclose(errors.mean(), reported_mae, rtol=1e-8, atol=1e-8):
        raise ValueError('SARIMAX CSV does not reproduce the metadata MAE')
    return frame
