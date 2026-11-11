"""Download the three official Google Fonts weights used by the HTML reference."""
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
url = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap'
request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
css = urllib.request.urlopen(request, timeout=20).read().decode()
rules = []
for weight, font_url in re.findall(r'font-weight: (\d+);.*?url\(([^)]+)\)', css, re.S):
    path = ROOT / 'web/assets' / f'ibm-plex-sans-{weight}.ttf'
    path.write_bytes(urllib.request.urlopen(font_url, timeout=20).read())
    rules.append('@font-face{font-family:"IBM Plex Sans";font-style:normal;'
                 f'font-weight:{weight};font-display:swap;'
                 f'src:url("/assets/{path.name}") format("truetype");' + '}')
    print(weight, path.stat().st_size)
if len(rules) != 3:
    raise ValueError('Expected exactly three font weights')
(ROOT / 'web/assets/fonts.css').write_text('\n'.join(rules) + '\n', encoding='utf-8')
