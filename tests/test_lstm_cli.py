"""Notebook-trained checkpoints must give the same forecasts through the CLI."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

from ems.models.lstm import experiment, preprocess, train as training, evaluate
from ems.models.lstm.config import FEATURE_COLS, N_FEATURES
from ems.models.lstm.model import build_model
from ems.paths import ROOT


class NotebookCliTests(unittest.TestCase):
    def test_default_names_match_the_notebook_and_other_names_remain_distinct(self):
        notebook = json.loads((ROOT / 'notebooks/lstm_experiment.ipynb').read_text(encoding='utf-8'))
        source = '\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code')
        for horizon, variable in ((1, 'RUN_NAME_1H'), (24, 'RUN_NAME_24B')):
            expected = re.search(variable + r'\s*=\s*"([^"]+)"', source).group(1)
            self.assertEqual(experiment.notebook_run_name('vanilla', 24, horizon), expected)
        self.assertEqual(experiment.notebook_run_name('vanilla', 168, 24), 'vanilla_seq168_block24')
        self.assertEqual(experiment.notebook_run_name('attention', 24, 1), 'attention_seq24')

    def test_missing_new_checkpoint_does_not_silently_load_legacy_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            # The legacy checkpoint's presence must not change the requested experiment.
            (Path(directory) / 'vanilla_seq24_best.pth').write_bytes(b'legacy')
            for horizon in (1, 24):
                with self.subTest(horizon=horizon), patch.object(experiment, 'CKPT_DIR', directory), \
                     patch.object(experiment, 'load_data') as load_data, \
                     contextlib.redirect_stderr(io.StringIO()) as error:
                    with self.assertRaises(SystemExit) as caught:
                        experiment.main(['--evaluate-only', '--forecast-horizon', str(horizon)])
                    self.assertEqual(caught.exception.code, 2)
                    self.assertIn('Missing notebook checkpoint', error.getvalue())
                    load_data.assert_not_called()

    def test_notebook_training_then_cli_evaluation_matches_for_both_horizons(self):
        previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)
        try:
            for horizon in (1, 24):
                with self.subTest(horizon=horizon), tempfile.TemporaryDirectory() as directory:
                    self.check_round_trip(horizon, Path(directory))
        finally:
            torch.set_num_threads(previous_threads)

    def check_round_trip(self, horizon, directory):
        rng = np.random.default_rng(42)
        parts = []
        for size in (64, 48, 28):
            parts.extend([pd.DataFrame(rng.normal(size=(size, N_FEATURES)), columns=FEATURE_COLS),
                          pd.DataFrame({'call_count': rng.integers(1, 20, size=size)})])
        test_frame = pd.DataFrame({'ds': pd.date_range('2026-01-01', periods=28, freq='h'),
                                   'y': parts[-1].call_count.to_numpy()})
        name = experiment.notebook_run_name('vanilla', 24, horizon)
        with patch.object(preprocess, 'load_data', return_value=parts), \
             patch.object(preprocess, 'CKPT_DIR', str(directory)), \
             patch.object(training, 'CKPT_DIR', str(directory)), \
             contextlib.redirect_stdout(io.StringIO()):
            # Use the same loader/model/train calls as notebook cells 5–13.
            if horizon == 1:
                train_dl, val_dl, test_dl, features, target = preprocess.build_dataloaders(24, 8, verbose=False)
            else:
                train_dl, val_dl, test_dl, features, target = preprocess.build_block_dataloaders(24, 24, 8, verbose=False)
            torch.manual_seed(42)
            model = build_model('vanilla', forecast_horizon=horizon)
            training.train(model, train_dl, val_dl, run_name=name, num_epochs=1, verbose=False)
            if horizon == 1:
                expected_y, expected_prediction = evaluate.predict(model, test_dl, target)
            else:
                expected_y, expected_prediction = evaluate.predict_24h_blocks(model, test_dl, target, n_target_hours=28)

            with patch.object(experiment, 'CKPT_DIR', str(directory)), \
                 patch.object(experiment, 'OUTPUT_DIR', directory), \
                 patch.object(experiment, 'load_data', return_value=parts), \
                 patch.object(experiment, 'load_scalers', return_value=(features, target)), \
                 patch.object(experiment, 'load_hourly_data', return_value={'test': test_frame}), \
                 patch.object(experiment, 'train') as unexpected_training, \
                 patch.object(evaluate, 'plot_loss_curve'), \
                 patch.object(evaluate, 'plot_predictions'):
                experiment.main(['--evaluate-only', '--forecast-horizon', str(horizon), '--batch-size', '8'])
                unexpected_training.assert_not_called()
            result = pd.read_csv(directory / f'test_predictions_{name}.csv')
            self.assertEqual(result.ds.tolist(), test_frame.ds.astype(str).tolist())
            np.testing.assert_allclose(result.y, expected_y, atol=1e-6)
            np.testing.assert_allclose(result.yhat, expected_prediction, atol=1e-6)
            metadata = json.loads((directory / f'metrics_{name}.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['n_hours'], 28)
            self.assertEqual(metadata['forecast_horizon'], horizon)


if __name__ == '__main__':
    unittest.main()
