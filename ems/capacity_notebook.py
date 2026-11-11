"""Execute the existing capacity notebook headlessly, without a Jupyter kernel.

The notebook is the source of truth for this synchronization step. Its input
paths, formulas, calibration and test-selection policy are deliberately kept
unchanged; this runner does not correct their methodological limitations.
Only trusted repository notebooks should be passed to this Python API.
"""
import json
import os
from pathlib import Path

from ems.paths import ROOT

DEFAULT_NOTEBOOK = ROOT / 'notebooks/queueing_theory.ipynb'


def run_capacity_notebook(notebook=DEFAULT_NOTEBOOK, output_dir=None, project_root=ROOT):
    notebook = Path(notebook).resolve()
    project_root = Path(project_root).resolve()
    destination = Path(output_dir).resolve() if output_dir is not None else None
    document = json.loads(notebook.read_text(encoding='utf-8'))
    # Compile all code first so a syntax error is reported before any cell runs.
    cells = [(index + 1, compile(''.join(cell['source']),
                               f'{notebook}:cell-{index + 1}', 'exec'))
             for index, cell in enumerate(document['cells']) if cell['cell_type'] == 'code']
    if not cells:
        raise ValueError('Capacity notebook has no executable code cells')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    namespace = {'__name__': '__main__', '__file__': str(notebook)}
    original_directory, original_show = Path.cwd(), plt.show
    # Each original cell saves its figure before show(). Close figures on CLI
    # just as the notebook backend does, rather than opening interactive windows.
    plt.show = lambda *args, **kwargs: plt.close('all')
    try:
        os.chdir(project_root)
        print(f'[Capacity] Source notebook: {notebook}')
        for number, code in cells:
            print(f'[Capacity] Running cell {number}', flush=True)
            exec(code, namespace)
            # The configuration cell initializes OUT_DIR before later cells
            # write any reports. Override the destination only, not calculations.
            if destination is not None and 'OUT_DIR' in namespace:
                destination.mkdir(parents=True, exist_ok=True)
                namespace['OUT_DIR'] = destination
        print(f"[Capacity] Reports: {namespace.get('OUT_DIR', destination)}")
        return namespace
    finally:
        plt.close('all')
        plt.show = original_show
        os.chdir(original_directory)
