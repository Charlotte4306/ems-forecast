"""Package only public web assets, serving code and the daily update worker."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
release = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-daily-forecast'
files = [p for p in (root/'web').rglob('*') if p.is_file()]
files += [root/p for p in ['ems/__init__.py', 'ems/paths.py', 'ems/web/__init__.py',
          'ems/web/__main__.py', 'ems/web/server.py', 'ems/live/__init__.py', 'ems/live/update.py',
          'outputs/web/dataset.json', 'deploy/verify_release.py', 'deploy/emsforecast-update.service',
          'deploy/emsforecast-update.timer', 'deploy/requirements-live.txt']]
manifest = {'release': release, 'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
manifest_path = root/'deploy/release-manifest.json'
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
archive = root/'deploy'/ (release+'.tar.gz')
with tarfile.open(archive, 'w:gz') as bundle:
    for p in files:
        bundle.add(p, arcname=p.relative_to(root).as_posix())
    bundle.add(manifest_path, arcname='release-manifest.json')
print(json.dumps({'release':release, 'archive':str(archive), 'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
