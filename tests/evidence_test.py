"""Check archival fidelity, deduplication, loose readers and safe failure."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from archive_engine_run import consolidate, restore
from engine_evidence import ARCHIVE, MANIFEST, archive_for, opened_archive, open_text, read_bytes, records, verify_archive


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'games').mkdir()
        config = dict(levels={'ply2': 2})
        (self.root / 'configuration.json').write_text(json.dumps(config))
        (self.root / 'summary.json').write_text(json.dumps(dict(configuration=config, summaries={'ply2': {'games': 2}})))
        self.expected = {}
        self.rows = [dict(level='ply2', opponent_elo=1320, number=n) for n in range(2)]
        for row in self.rows:
            name = f'games/ply2-1320-{row["number"]:02d}.pgn'
            self.expected[name] = f'[Result "1/2-1/2"]\n[Round "{row["number"]}"]\n\n1. e4 e5 1/2-1/2\n\n'.encode()
        self.expected['games.jsonl'] = ''.join(json.dumps(row) + '\n' for row in self.rows).encode()
        self.expected['run.log'] = b'finished\n'
        self.expected['ply2.pgn'] = b''.join(self.expected[name] for name in sorted(self.expected) if name.endswith('.pgn'))
        for name, data in self.expected.items():
            (self.root / name).write_bytes(data)
        self.addCleanup(archive_for.cache_clear)
        self.addCleanup(opened_archive.cache_clear)

    def test_round_trip_and_deduplication(self):
        for name, data in self.expected.items():
            self.assertEqual(read_bytes(self.root / name), data)
        audit = consolidate(self.root)
        self.assertEqual(audit['original_files'], len(self.expected))
        self.assertEqual(audit['derived_files'], 1)
        self.assertFalse((self.root / 'games').exists())
        self.assertTrue((self.root / 'configuration.json').is_file())
        for name, data in self.expected.items():
            self.assertFalse((self.root / name).exists())
            self.assertEqual(read_bytes(self.root / name), data)
            with open_text(self.root / name) as stream:
                self.assertEqual(stream.read(), data.decode())
        self.assertEqual(list(records(self.root / 'games.jsonl')), self.rows)
        with ZipFile(self.root / ARCHIVE) as archive:
            self.assertNotIn('ply2.pgn', archive.namelist())
        self.assertEqual(verify_archive(self.root / ARCHIVE), audit)
        self.assertEqual(consolidate(self.root), audit)
        destination = self.root / 'restored'
        restore(self.root, destination)
        for name, data in self.expected.items():
            self.assertEqual((destination / name).read_bytes(), data)
        self.assertEqual((destination / 'configuration.json').read_bytes(), (self.root / 'configuration.json').read_bytes())

    def test_bad_aggregate_preserves_all_sources(self):
        (self.root / 'ply2.pgn').write_bytes(b'wrong order or incomplete data')
        with self.assertRaises(AssertionError):
            consolidate(self.root)
        for name in self.expected:
            self.assertTrue((self.root / name).is_file())
        self.assertFalse((self.root / ARCHIVE).exists())

    def test_corruption_is_detected(self):
        consolidate(self.root)
        data = (self.root / ARCHIVE).read_bytes()
        with ZipFile(io.BytesIO(data)) as original, ZipFile(self.root / 'damaged.zip', 'w') as damaged:
            for name in original.namelist():
                payload = original.read(name)
                damaged.writestr(name, b'changed' if name == 'run.log' else payload)
        with self.assertRaises(AssertionError):
            verify_archive(self.root / 'damaged.zip')

    def test_partial_live_checkpoint(self):
        with (self.root / 'games.jsonl').open('ab') as stream:
            stream.write(b'{"unfinished":')
        self.assertEqual(list(records(self.root / 'games.jsonl', complete_lines=True)), self.rows)


if __name__ == '__main__':
    unittest.main()
