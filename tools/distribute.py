"""Create a reproducible binary distribution containing only runtime files."""
import hashlib
import shutil
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from package_graphics import ROOT, RUNTIME


def main():
    destination = ROOT / 'build/dist/CHESS'
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    names = ('CHESS.PRG', 'MENU.BIN', 'UI.BIN') + RUNTIME
    for name in names:
        base, extension = name.split('.')
        assert 1 <= len(base) <= 8 and 1 <= len(extension) <= 3, name
        shutil.copyfile(ROOT / 'src' / name, destination / name)
    (destination / 'README.TXT').write_text(
        'CX16 Chess\n\nKeep all files in this directory together on your X16 SD card.\n'
        'Load CHESS.PRG and run it. Emulator: x16emu -prg CHESS.PRG -run\n\n'
        'Source, license and credits: https://github.com/ifilot/cx16-chess\n')
    manifest = {name: {'bytes': (destination / name).stat().st_size,
                       'sha256': hashlib.sha256((destination / name).read_bytes()).hexdigest()}
                for name in names}
    (destination / 'HASHES.TXT').write_text(''.join(f'{info["sha256"]}  {name}\n' for name, info in manifest.items()))
    archive = destination.parent / 'CHESS.ZIP'
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as output:
        for path in sorted(destination.iterdir()):
            entry = ZipInfo('CHESS/' + path.name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            output.writestr(entry, path.read_bytes())
    with ZipFile(archive) as packaged:
        assert packaged.testzip() is None, 'Distribution ZIP failed CRC verification'
        for name, info in manifest.items():
            data = packaged.read('CHESS/' + name)
            assert hashlib.sha256(data).hexdigest() == info['sha256'], name
    print(f'Distribution: {archive} ({archive.stat().st_size} bytes; {len(names)} runtime files)')


if __name__ == '__main__':
    main()
