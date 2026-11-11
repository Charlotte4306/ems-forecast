"""The CLI runs notebook cells in order without duplicating capacity formulas."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt

from ems.capacity_notebook import run_capacity_notebook
import run_queuing


def write_notebook(path, sources):
    path.write_text(json.dumps({'cells': [
        {'cell_type': 'markdown', 'source': ['Ignored explanatory text']},
        *[{'cell_type': 'code', 'source': [source]} for source in sources],
    ]}), encoding='utf-8')


class CapacityCliTests(unittest.TestCase):
    def test_cells_share_state_and_output_override_preserves_computation(self):
        original_cwd = Path.cwd()
        original_show = plt.show
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebook = root / 'capacity.ipynb'
            output = root / 'reports'
            write_notebook(notebook, [
                "from pathlib import Path\nOUT_DIR = Path('default')\nrate = [2, 5]\n",
                "workload = [value * 1.05 for value in rate]\n",
                "OUT_DIR.mkdir(exist_ok=True)\n(OUT_DIR / 'values.json').write_text(__import__('json').dumps(workload))\n",
            ])
            with contextlib.redirect_stdout(io.StringIO()):
                result = run_capacity_notebook(notebook, output, project_root=root)
            self.assertEqual(result['rate'], [2, 5])
            self.assertEqual(json.loads((output / 'values.json').read_text()), [2.1, 5.25])
            self.assertFalse((root / 'default/values.json').exists())
        self.assertEqual(Path.cwd(), original_cwd)
        self.assertIs(plt.show, original_show)

    def test_default_destination_comes_from_the_notebook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebook = root / 'capacity.ipynb'
            write_notebook(notebook, [
                "from pathlib import Path\nOUT_DIR = Path('notebook-reports')\nOUT_DIR.mkdir()\n",
                "(OUT_DIR / 'result.txt').write_text('same workflow')\n",
            ])
            with contextlib.redirect_stdout(io.StringIO()):
                run_capacity_notebook(notebook, project_root=root)
            self.assertEqual((root / 'notebook-reports/result.txt').read_text(), 'same workflow')

    def test_runtime_error_is_propagated_and_process_state_is_restored(self):
        original_cwd, original_show = Path.cwd(), plt.show
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebook = root / 'capacity.ipynb'
            write_notebook(notebook, ["raise ValueError('missing forecast')"])
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'missing forecast'):
                run_capacity_notebook(notebook, project_root=root)
        self.assertEqual(Path.cwd(), original_cwd)
        self.assertIs(plt.show, original_show)

    def test_syntax_is_checked_before_a_cell_can_write_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebook = root / 'capacity.ipynb'
            write_notebook(notebook, [
                "from pathlib import Path\nPath('should-not-exist').write_text('partial output')",
                'if : invalid syntax',
            ])
            with self.assertRaises(SyntaxError):
                run_capacity_notebook(notebook, project_root=root)
            self.assertFalse((root / 'should-not-exist').exists())

    def test_cli_delegates_to_the_notebook_runner(self):
        with patch('ems.capacity_notebook.run_capacity_notebook') as run:
            run_queuing.main(['--output-dir', 'reports'])
            run.assert_called_once_with(output_dir=Path('reports'))


if __name__ == '__main__':
    unittest.main()
