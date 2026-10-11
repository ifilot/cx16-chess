# Engine test archives

Each completed tournament has an `evidence.zip` and a small `evidence.json`
in its run directory. Reports, configurations, summaries, opening suites,
parity proofs and validation reports remain ordinary files.

## What is stored

The ZIP contains the original `games.jsonl`, all `games/*.pgn`, run/parity
logs, and `manifest.json`. Every stored file has its original byte count and
SHA-256 in the manifest. Aggregate PGNs such as `ply4.pgn` and `noise350.pgn`
are represented by ordered member lists, byte counts and SHA-256 hashes.
Their original contents can be reconstructed exactly without storing a second
copy of every game. `evidence.json` records the whole archive's hash, counts
and sizes. `ARCHIVES.json` indexes the completed run archives.

The consolidation tool checks completion and game identities, compares each
aggregate with the concatenated per-game originals, reads and verifies the
finished ZIP, and rechecks every working source before removing loose files.
The ratings, configurations and recorded search traces are unchanged.

## Read and validate

The analysis tools use `tools/engine_evidence.py` and accept the same logical
paths as before. Reads fall back to loose files for new, unarchived runs.
No extraction is needed for validation, comparison, status reports, parity
or replay. For example, from the repository root:

```sh
python3 tools/archive_engine_run.py docs/engine/native-depth4-elo-2026-10-11 --verify-only
python3 tools/validate_difficulty_run.py docs/engine/native-depth4-elo-2026-10-11
python3 tools/depth_run_status.py --run docs/engine/native-depth4-elo-2026-10-11
```

PGN/analysis tools require python-chess as documented in the main README.
Native replay also requires a compatible engine executable. Configuration
hashes and existing validation safeguards still apply.

## Restore all original files

Standard ZIP tools can extract the raw game members and records. To also
reconstruct aggregate PGNs and copy the retained metadata to a new directory:

```sh
python3 tools/archive_engine_run.py docs/engine/native-depth4-elo-2026-10-11 \
  --extract-to build/engine/restored-ply4
```

The destination must not exist. Extraction verifies every stored and derived
hash before writing. The archived originals stay in place.

## Future experiments

`rate_difficulties.py` defaults to an ignored `build/engine/difficulty-DATE`
directory. Use a fresh `--out` for new tests. Completed archived runs are
immutable and cannot accidentally be resumed or overwritten by the runner.
After finishing a run and retaining its report/configuration/summary, bundle
it with:

```sh
python3 tools/archive_engine_run.py build/engine/difficulty-DATE
```

Commit only the selected completed evidence and its archive, rather than
thousands of loose PGNs. Git history still contains the original committed
files; this consolidation does not rewrite history.
