"""Pack banked code and audio into one headerless KERNAL-loadable RAM image."""
from pathlib import Path
import json
import re
import sys
from runtime_files import SOUND_FILES

ROOT = Path(__file__).resolve().parents[1]
BANK_SIZE = 8192
FIRST_BANK, LAST_BANK = 21, 45
CODE_BANKS = {'MENU.BIN': 21, 'UI.BIN': 22, 'DRAG.BIN': 23, 'AUDIO.BIN': 45}


def pack(destination):
    destination = Path(destination)
    banks = {name: int(bank) for name, bank in re.findall(r'#define MUSIC_(\w+)_BANK (\d+)',
                                                       (ROOT / 'assets/sound/music.h').read_text())}
    resources = [(name, bank, destination / name) for name, bank in CODE_BANKS.items()]
    resources.append(('SFX.BIN', 25, ROOT / 'assets/sound/SFX.BIN'))
    resources.extend((name, banks[name.split('.')[0]], ROOT / 'assets/sound' / name)
                     for name in SOUND_FILES if name.endswith('.ZSM'))
    image = bytearray((LAST_BANK - FIRST_BANK + 1) * BANK_SIZE)
    used = set()
    manifest = {}
    for name, bank, path in resources:
        data = path.read_bytes()
        assert data, name
        occupied = set(range(bank, bank + (len(data) + BANK_SIZE - 1) // BANK_SIZE))
        assert not occupied & used and min(occupied) >= FIRST_BANK and max(occupied) <= LAST_BANK, name
        if name in CODE_BANKS:
            assert len(data) <= BANK_SIZE, name
        used.update(occupied)
        offset = (bank - FIRST_BANK) * BANK_SIZE
        image[offset:offset + len(data)] = data
        manifest[name] = {'bank': bank, 'offset': offset, 'bytes': len(data)}
    # Zero padding also initializes UI/audio/drag BSS and the history/player banks.
    (destination / 'CHESS.BIN').write_bytes(image)
    output = ROOT / 'build/banks'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for name, record in manifest.items():
        source = destination / name if name in CODE_BANKS else ROOT / 'assets/sound' / name
        assert image[record['offset']:record['offset'] + record['bytes']] == source.read_bytes()
    print(f'Runtime banks: CHESS.BIN ({len(image)} bytes; {len(resources)} resources, banks 21–45)')


if __name__ == '__main__':
    pack(sys.argv[1])
