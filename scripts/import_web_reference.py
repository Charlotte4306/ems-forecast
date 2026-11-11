"""Keep the supplied HTML's DOM, CSS, and motion; externalize assets for CSP.

Usage: python scripts/import_web_reference.py <reference.html>
Data binding lives separately in web/app.mjs, not in this importer.
"""
import argparse
import hashlib
from pathlib import Path
import re


def convert(source, root):
    html = source.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    runtime = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    html = re.sub(r"<style>.*?</style>", '<link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/template-bindings.css">', html, flags=re.S)
    html = re.sub(r'<link[^>]+(?:fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>', '', html)
    html = html.replace('<title>', '<link rel="stylesheet" href="/assets/fonts.css"><title>', 1)
    html = html.replace('EMSForecast — Bản mẫu HTML 7 màn hình', 'EMSForecast — Dự báo nhu cầu và kế hoạch xe')
    html = re.sub(r"<script>.*?</script>", '<script type="module" src="/app.mjs"></script>', html, flags=re.S)
    # Inline declarations retain their precedence, including SVG background layers.
    rules = {}
    def tag_style(match):
        tag = match.group(0)
        style = re.search(r'\sstyle="([^"]*)"', tag)
        if not style:
            return tag
        value = style.group(1)
        name = rules.setdefault(value, f"reference-inline-{len(rules)+1}")
        tag = tag[:style.start()] + tag[style.end():]
        if 'class="' in tag:
            tag = tag.replace('class="', f'class="{name} ', 1)
        else:
            tag = tag.replace('>', f' class="{name}">', 1)
        return tag
    html = re.sub(r'<[^>]+\sstyle="[^"]*"[^>]*>', tag_style, html)
    for value, name in rules.items():
        declarations = ';'.join(v.strip() + ' !important' for v in value.split(';') if v.strip())
        css += f'\n.{name}' + '{' + declarations + '}'

    runtime = re.sub(r'var observed = \[[^;]+;', 'var observed = window.EMS.observed;', runtime)
    runtime = re.sub(r'var forecast = \[[^;]+;', 'var forecast = window.EMS.forecast;', runtime)
    runtime = re.sub(r'var heatDays = \[.*?\n  \];', 'var heatDays = window.EMS.heatDays;', runtime, flags=re.S)
    runtime = runtime.replace(" + ' lượt/giờ · minh họa'", " + ' lượt/giờ · dữ liệu lịch sử'")
    runtime = runtime.replace("[['28/09 · 00:00',45,'start'],['12:00',300,'start'],['29/09 · 00:00',585,'start'],['12:00',840,'start'],['23:00',1110,'end']]", 'window.EMS.timelineLabels')
    runtime = runtime.replace('var peakX = X(1, 18), peakY = Y(20);', 'var peakX = X(1, window.EMS.peakHour), peakY = Y(window.EMS.peakValue);')
    runtime = runtime.replace('function Y(v){ return 204 - 6.4 * v; }', 'function Y(v){ return 204 - 192 * v / window.EMS.chartMax; }')
    runtime = runtime.replace('[[30,12],[20,76],[10,140],[0,204]]', 'window.EMS.overviewGrid')
    runtime = runtime.replace("var target = parseInt(node.getAttribute('data-count'), 10);", "var target = parseFloat(node.getAttribute('data-count'));")
    runtime = runtime.replace("fmt(Math.round(target * eased))", "Number(target * eased).toLocaleString('vi-VN', {maximumFractionDigits: Number(node.dataset.decimals || 0)})")
    runtime = runtime.replace('return 45 + i * ((W - 60) / (n - 1));', 'return 45 + i * ((W - 60) / Math.max(1, n - 1));')
    runtime = runtime.replace('px(i, ser.data.length).toFixed(1)', '(ser.day === undefined ? px(i, ser.data.length) : X(ser.day, i)).toFixed(1)')
    start = runtime.index('  // Dự báo nhu cầu:')
    end = runtime.index('  // Sai lệch theo giờ', start)
    runtime = runtime[:start] + "  window.EMS.charts.forEach(function(item){ drawChart(item.id, item.config); });\n" + runtime[end:]
    runtime = re.sub(r'var diffs = \[[^;]+;', 'var diffs = window.EMS.diffs;', runtime)
    runtime = runtime.replace('var zeroY = 78, scale = 13,', 'var zeroY = 78, scale = window.EMS.diffScale,')
    start = runtime.index('  var btnCsv =')
    end = runtime.index('  /* ---------- Cài đặt:', start)
    runtime = runtime[:start] + "  document.getElementById('btn-csv').addEventListener('click', window.EMS.download);\n" + runtime[end:]
    runtime = runtime.replace('  var reduced =', "  var reduced =")
    runtime = runtime.replace("matches;", "matches || document.body.classList.contains('reduce-motion');", 1)
    runtime = runtime.replace('    if(!reduced){\n', '    if(!reduced){\n')
    runtime = runtime.replace('      cx +=', "      if(document.body.classList.contains('reduce-motion')){ requestAnimationFrame(loop); return; }\n      cx +=")
    runtime = runtime.replace('})();', '})();', 1)
    runtime = runtime.replace("if(setStatus) setStatus.textContent = 'Không có thay đổi'; });", "window.EMS.saveSettings(); if(setStatus) setStatus.textContent = 'Đã lưu trên trình duyệt này'; });")
    runtime = runtime.replace("if(motionSwitch){ motionSwitch.setAttribute('aria-checked','false'); document.body.classList.remove('reduce-motion'); if(motionState) motionState.textContent = 'Tắt'; }", 'window.EMS.restoreSettings();')
    runtime = runtime.replace("showScreen(b.getAttribute('data-screen'));", "showScreen(b.getAttribute('data-screen')); history.replaceState(null, '', '#' + b.getAttribute('data-screen'));")
    runtime = runtime.replace("  var gotoHist =", "  if(window.EMS.initialScreen) showScreen(window.EMS.initialScreen);\n  var gotoHist =")
    (root / 'web/index.html').write_text(html, encoding='utf-8')
    (root / 'web/styles.css').write_text(css, encoding='utf-8')
    (root / 'web/template-runtime.mjs').write_text(runtime, encoding='utf-8')
    print('Imported reference:', hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    args = parser.parse_args()
    convert(args.reference, Path(__file__).resolve().parents[1])
