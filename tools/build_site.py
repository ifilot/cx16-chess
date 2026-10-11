"""Build the static chess site with Kakuro's checksum-pinned r49 WASM runtime."""
from hashlib import sha256
from pathlib import Path
import html
import json
import shutil
import subprocess
import urllib.request
from zipfile import ZipFile

from package_graphics import RUNTIME

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = 'x16emu_wasm-r49.zip'
URL = f'https://github.com/X16Community/x16-emulator/releases/download/r49/{ARCHIVE}'
DIGEST = '9711036cf5b33504815b278fa872b8ec20aef9cb609fd7b17f3685d91312628f'
RESEARCH = ROOT / 'docs/engine/difficulty-2026-10-10'


def main():
    cache = ROOT / 'build/site-cache'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / ARCHIVE
    if not archive.exists():
        print('Downloading official X16 WebAssembly emulator r49…', flush=True)
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
        if sha256(data).hexdigest() != DIGEST:
            raise ValueError('Emulator archive checksum mismatch')
        archive.write_bytes(data)
    if sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise ValueError(f'Emulator archive checksum mismatch: remove {archive} and retry')

    output = ROOT / 'build/site'
    shutil.rmtree(output, ignore_errors=True)
    shutil.copytree(ROOT / 'site', output)
    (output / 'emulator').mkdir()
    with ZipFile(archive) as package:
        for name in ('x16emu.js', 'x16emu.wasm', 'x16emu.data'):
            (output / 'emulator' / name).write_bytes(package.read(name))

    # Only distribution runtime files: never publish local save slots or defaults.
    names = ('CHESS.PRG', 'MENU.BIN', 'UI.BIN') + RUNTIME
    (output / 'game').mkdir()
    with ZipFile(ROOT / 'build/dist/CHESS.ZIP') as package:
        for name in names:
            (output / 'game' / name).write_bytes(package.read('CHESS/' + name))
    (output / 'game/manifest.json').write_text(json.dumps({'resources': sorted(names)}, indent=2) + '\n')
    shutil.copy2(ROOT / 'build/dist/CHESS.ZIP', output / 'CHESS.ZIP')
    shutil.copy2(ROOT / 'build/graphics/splash.png', output / 'start.png')

    (output / 'research').mkdir()
    for name in ('RESULTS.md', 'summary.json', 'configuration.json', 'rating-comparison.png',
                 'easy.pgn', 'normal.pgn', 'hard.pgn', 'games.jsonl'):
        shutil.copy2(RESEARCH / name, output / 'research' / name)
    # The report's links keep working in the downloaded static tree.
    shutil.copy2(ROOT / 'docs/engine/RESULTS.md', output / 'RESULTS.md')
    summary = json.loads((RESEARCH / 'summary.json').read_text())
    rows = []
    for key, label in (('easy', 'Easy'), ('normal', 'Normal'), ('hard', 'Hard')):
        result = summary['summaries'][key]
        lo, hi = result['confidence_95']
        cells = (label, f'{result["cap_seconds"]} s', result['estimated_elo'],
                 f'{lo}–{hi}', f'{result["wins"]} / {result["draws"]} / {result["losses"]}')
        rows.append('<tr>' + ''.join(f'<td>{html.escape(str(value))}</td>' for value in cells) + '</tr>')
    index = (output / 'index.html').read_text()
    marker = '<!-- STRENGTH_ROWS -->'
    if index.count(marker) != 1:
        raise ValueError('Site template must have exactly one strength table marker')
    (output / 'index.html').write_text(index.replace(marker, '\n'.join(rows)))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    info = {'version': (ROOT / 'VERSION').read_text().strip(), 'commit': commit,
            'emulator': 'r49', 'program_sha256': sha256((output / 'game/CHESS.PRG').read_bytes()).hexdigest()}
    (output / 'build.json').write_text(json.dumps(info, indent=2) + '\n')
    (output / '.nojekyll').touch()
    print(f'Site ready: {output} ({len(names)} runtime files)')


if __name__ == '__main__':
    main()
