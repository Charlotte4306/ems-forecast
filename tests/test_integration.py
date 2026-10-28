"""Check that the integrated packages can still use the committed artifacts."""
import importlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

from ems.paths import ROOT, CHECKPOINT_DIR, OUTPUT_DIR
from ems.data import load_data
from ems.models.lstm.config import DEVICE, N_FEATURES, DATA_DIR, CKPT_DIR
from ems.models.lstm.model import build_model
from ems.models.lstm.preprocess import create_sequences, load_scalers, scale_data
from ems.models.lstm.train import load_checkpoint
from ems.models.prophet.model import load_model, predict


class IntegrationTests(unittest.TestCase):
    def test_model_paths_and_existing_lstm_checkpoint(self):
        self.assertEqual(Path(DATA_DIR), ROOT / "data")
        self.assertEqual(Path(CKPT_DIR), CHECKPOINT_DIR / "lstm")
        frames = load_data()
        test = frames["test"]
        raw = pd.read_csv(ROOT / "data/X_test.csv").head(26)
        target = test[["y"]].head(26).rename(columns={"y": "call_count"})
        feat_scaler, tgt_scaler = load_scalers()
        X, y = scale_data(raw, target, feat_scaler, tgt_scaler)
        X_seq, y_seq = create_sequences(X, y, 24)
        self.assertEqual(X_seq.shape, (2, 24, N_FEATURES))
        np.testing.assert_array_equal(y_seq, y[24:])
        model = build_model("vanilla")
        load_checkpoint(model, "vanilla_seq24")
        model.eval()
        with torch.no_grad():
            result = model(torch.from_numpy(X_seq).to(DEVICE))
        self.assertEqual(tuple(result.shape), (2, 1))
        self.assertTrue(torch.isfinite(result).all())

    def test_prophet_checkpoint_matches_pre_refactor_predictions(self):
        model = load_model(CHECKPOINT_DIR / "prophet/best_model.json")
        test = load_data()["test"].head(48)
        expected = pd.read_csv(OUTPUT_DIR / "prophet/test_predictions.csv").head(48)
        np.testing.assert_allclose(predict(model, test).yhat, expected.yhat,
                                   rtol=1e-10, atol=1e-10)

    def test_lstm_training_can_save_and_restore_after_move(self):
        module = importlib.import_module("ems.models.lstm.train")
        torch.manual_seed(42)
        model = build_model("vanilla", hidden_size=8, num_layers=1, fc_size=4)
        loader = DataLoader(TensorDataset(torch.randn(8, 4, N_FEATURES),
                                         torch.rand(8, 1)), batch_size=4)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "CKPT_DIR", directory):
                history = module.train(model, loader, loader, run_name="smoke", num_epochs=1)
                before = {k: v.detach().clone() for k, v in model.state_dict().items()}
                with torch.no_grad():
                    for value in model.parameters():
                        value.zero_()
                module.load_checkpoint(model, "smoke")
                for name, value in model.state_dict().items():
                    torch.testing.assert_close(value, before[name])
                self.assertTrue(np.isfinite(history["best_val_loss"]))


if __name__ == "__main__":
    unittest.main()
