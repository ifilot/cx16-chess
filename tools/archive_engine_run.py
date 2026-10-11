"""Consolidate a completed run; verify every original byte before removing loose evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from engine_evidence import ARCHIVE, MANIFEST, verify_archive, archive_for, opened_archive, read_bytes


def digest(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def consolidate(root):
    root = Path(root)
    target = root / ARCHIVE
    if target.exists():
        return verify_archive(target)
    config = json.loads((root / 'configuration.json').read_text())
    summary = json.loads((root / 'summary.json').read_text())
    checkpoint = (root / 'games.jsonl').read_bytes()
    rows = [json.loads(line) for line in checkpoint.splitlines()]
    assert rows and sum(r['games'] for r in summary['summaries'].values()) == len(rows)
    identities = {(r['level'], r['opponent_elo'], r['number']) for r in rows}
    assert len(identities) == len(rows), 'Duplicate game records'
    assert summary['configuration'] == config
    games = sorted((root / 'games').glob('*.pgn'))
    expected = {f'{r["level"]}-{r["opponent_elo"]}-{r["number"]:02d}.pgn' for r in rows}
    assert {p.name for p in games} == expected, 'Missing or extra per-game PGNs'
    sources = games + [root / 'games.jsonl'] + sorted(root.glob('*.log'))
    aggregates = sorted(root.glob('*.pgn'))
    manifest = dict(version=1, files={}, derived={})
    temporary = target.with_suffix('.zip.tmp')
    # Read independent small source files concurrently on mounted Windows disks.
    with ThreadPoolExecutor(max_workers=16) as pool, ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in zip(sources, pool.map(Path.read_bytes, sources)):
            name = path.relative_to(root).as_posix()
            manifest['files'][name] = digest(data)
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compresslevel=9)
        for path in aggregates:
            selected = sorted((r for r in rows if r['level'] == path.stem),
                              key=lambda r: (r['opponent_elo'], r['number']))
            members = [f'games/{r["level"]}-{r["opponent_elo"]}-{r["number"]:02d}.pgn' for r in selected]
            data = path.read_bytes()
            assembled = b''.join(archive.read(name) for name in members)
            assert selected and assembled == data, f'Aggregate differs from its per-game PGNs: {path}'
            manifest['derived'][path.name] = dict(**digest(data), members=members)
        entry = ZipInfo(MANIFEST, date_time=(1980, 1, 1, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n', compresslevel=9)
    audit = verify_archive(temporary)
    # Recheck the working files, including any uncommitted changes, before any
    # deletion. A changed source leaves both the source and temporary archive.
    def unchanged(path):
        name = path.relative_to(root).as_posix()
        record = manifest['files'].get(name, manifest['derived'].get(name))
        assert digest(path.read_bytes()) == {key: record[key] for key in ('bytes', 'sha256')}, path
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(unchanged, sources + aggregates))
    temporary.replace(target)
    archive_for.cache_clear()
    (root / 'evidence.json').write_text(json.dumps(dict(archive=ARCHIVE, **audit), indent=2) + '\n')
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(Path.unlink, sources + aggregates))
    (root / 'games').rmdir()
    print(f'{root}: {audit["original_files"]} files verified → {ARCHIVE} ({audit["archive_bytes"]:,} bytes)', flush=True)
    return audit


def restore(root, destination):
    root, destination = Path(root), Path(destination)
    verify_archive(root / ARCHIVE)
    _, manifest = opened_archive(root / ARCHIVE)
    destination.mkdir(parents=True, exist_ok=False)
    for path in root.iterdir():
        if path.is_file() and path.name not in (ARCHIVE, 'evidence.json'):
            shutil.copyfile(path, destination / path.name)
    def write(name):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(read_bytes(root / name))
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(write, list(manifest['files']) + list(manifest['derived'])))
    print(f'{root}: restored original evidence and metadata to {destination}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--extract-to', type=Path, help='Restore one run to a new directory, including aggregate PGNs')
    args = parser.parse_args()
    if args.extract_to:
        if len(args.runs) != 1 or args.verify_only:
            parser.error('--extract-to requires exactly one run and cannot be combined with --verify-only')
        restore(args.runs[0], args.extract_to)
        return
    for root in args.runs:
        if args.verify_only:
            result = verify_archive(root / ARCHIVE)
            recorded = json.loads((root / 'evidence.json').read_text())
            assert all(recorded[key] == value for key, value in result.items())
            print(f'{root}: all stored and derived bytes verified', flush=True)
        else:
            consolidate(root)


if __name__ == '__main__':
    main()
