"""Run on the existing VPS via SSH stdin: python3 - RELEASE ARCHIVE_SHA256."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen

release, digest = sys.argv[1:]
if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-z-]+', release):
    raise ValueError('Invalid release name')
base = Path('/home/charlotte/apps/emsforecast-releases')
archive = base / (release + '.tar.gz')
if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
    raise ValueError('Archive hash mismatch')
destination = base / release
destination.mkdir(exist_ok=False)
with tarfile.open(archive) as bundle:
    for item in bundle.getmembers():
        if item.issym() or item.islnk() or not (destination / item.name).resolve().is_relative_to(destination):
            raise ValueError('Unsafe archive entry')
    bundle.extractall(destination)
subprocess.run(['python3', str(destination / 'deploy/verify_release.py')], check=True)
service = Path('/etc/systemd/system/emsforecast.service')
previous = service.read_text()
backup = destination / 'previous-emsforecast.service'
backup.write_text(previous)
updated, count = re.subn(r'^WorkingDirectory=.+$', 'WorkingDirectory=' + str(destination), previous, flags=re.M)
if count != 1:
    raise ValueError('Unexpected service configuration')
unit = destination / 'emsforecast.service'
if 'Environment=EMS_LIVE_DIR=' not in updated:
    updated = updated.replace('[Service]', '[Service]\nEnvironment=EMS_LIVE_DIR=/home/charlotte/apps/emsforecast-live', 1)
unit.write_text(updated)

def activate(path):
    subprocess.run(['sudo', '-n', 'install', '-m', '644', str(path), str(service)], check=True)
    subprocess.run(['sudo', '-n', 'systemctl', 'daemon-reload'], check=True)
    subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'emsforecast'], check=True)

try:
    activate(unit)
    for attempt in range(20):
        try:
            with urlopen('http://127.0.0.1:8501/health', timeout=3) as response:
                if b'"ok"' in response.read():
                    break
        except OSError:
            pass
        time.sleep(.5)
    else:
        raise RuntimeError('New release did not become healthy')
    with urlopen('http://127.0.0.1:8501/zenless.css') as response:
        if response.read() != (destination / 'web/zenless.css').read_bytes():
            raise RuntimeError('Service did not load the new release')
except Exception:
    activate(backup)
    raise
current = base.parent / 'emsforecast-current'
temporary_link = current.with_name('emsforecast-current-next')
temporary_link.symlink_to(destination, target_is_directory=True)
temporary_link.replace(current)
print('Activated:', destination)
