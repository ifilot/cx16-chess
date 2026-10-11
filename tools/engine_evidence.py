"""Read completed engine evidence from loose files or a verified run archive."""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

ARCHIVE = 'evidence.zip'
MANIFEST = 'manifest.json'


@lru_cache(maxsize=64)
def archive_for(directory):
    directory = Path(directory).absolute()
    for parent in (directory, *directory.parents):
        candidate = parent / ARCHIVE
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=32)
def opened_archive(path):
    archive = ZipFile(path)
    manifest = json.loads(archive.read(MANIFEST))
    return archive, manifest


def archived_entry(path):
    path = Path(path).absolute()
    archive_path = archive_for(path.parent)
    if archive_path is None:
        return None
    name = path.relative_to(archive_path.parent).as_posix()
    archive, manifest = opened_archive(archive_path)
    if name in manifest['files'] or name in manifest['derived']:
        return archive, manifest, name
    return None


def read_bytes(path):
    entry = archived_entry(path)
    if entry is None:
        return Path(path).read_bytes()
    archive, manifest, name = entry
    if name in manifest['files']:
        return archive.read(name)
    # Aggregate PGNs are exact concatenations of per-game members, so there
    # is only one stored copy of each game. Preserve their original byte order.
    return b''.join(archive.read(member) for member in manifest['derived'][name]['members'])


def read_text(path):
    return read_bytes(path).decode('utf-8')


@contextmanager
def open_text(path):
    entry = archived_entry(path)
    if entry is None:
        with Path(path).open(encoding='utf-8') as stream:
            yield stream
    elif entry[2] in entry[1]['files']:
        with entry[0].open(entry[2]) as raw, io.TextIOWrapper(raw, encoding='utf-8') as stream:
            yield stream
    else:
        with io.StringIO(read_text(path)) as stream:
            yield stream


def records(path, complete_lines=False):
    with open_text(path) as stream:
        for line in stream:
            if line.strip() and (not complete_lines or line.endswith('\n')):
                yield json.loads(line)


def verify_archive(path):
    data = Path(path).read_bytes()
    with ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read(MANIFEST))
        assert manifest['version'] == 1
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate archive members'
        assert set(names) == set(manifest['files']) | {MANIFEST}
        assert not set(manifest['files']) & set(manifest['derived'])
        for name, record in manifest['files'].items():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            payload = archive.read(name)  # ZIP also checks CRC for every member.
            assert len(payload) == record['bytes'], name
            assert hashlib.sha256(payload).hexdigest() == record['sha256'], name
        for name, record in manifest['derived'].items():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            digest, size = hashlib.sha256(), 0
            for member in record['members']:
                payload = archive.read(member)
                digest.update(payload)
                size += len(payload)
            assert size == record['bytes'] and digest.hexdigest() == record['sha256'], name
    return dict(sha256=hashlib.sha256(data).hexdigest(), archive_bytes=len(data),
                stored_files=len(manifest['files']), derived_files=len(manifest['derived']),
                original_files=len(manifest['files']) + len(manifest['derived']),
                original_bytes=sum(r['bytes'] for group in ('files', 'derived') for r in manifest[group].values()))
