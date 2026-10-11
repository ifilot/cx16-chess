"""Compare baseline/candidate emulator throughput and engine behaviour.

Records full outputs for fixed-depth and 2/10/20-second searches. Includes warm
transposition tables and reversible history replay. Wall times are host times;
guest time is measured separately. Polling may round to a different instruction
by a few cycles, so at most 16 CPU cycles of elapsed-time difference are allowed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from depth_bench import POSITIONS
from engine_bridge import CPU_HZ, EngineBridge


def measure(executable):
    rows = []
    with EngineBridge(emu=executable) as engine:
        for name, fen in POSITIONS.items():
            for depth, cap in ((3, 0), (0, 2), (0, 10), (0, 20)):
                started = time.perf_counter()
                result = engine.search(fen, depth=depth, time_limit=cap, fresh=True)
                rows.append(dict(position=name, depth=depth, cap=cap,
                                 wall_seconds=time.perf_counter() - started, result=result))
                print(f'{executable.name}: {name}, depth={depth}, cap={cap}', flush=True)
        # Two cycles of knight moves return to startpos, with repetition history.
        moves = [(0x06, 0x25, 0), (0x76, 0x55, 0), (0x25, 0x06, 0), (0x55, 0x76, 0)]
        for fresh in (True, False):
            started = time.perf_counter()
            result = engine.search('startpos', time_limit=10, fresh=fresh, moves=moves)
            rows.append(dict(position='repetition-' + str(fresh), depth=0, cap=10,
                             wall_seconds=time.perf_counter() - started, result=result))
    return rows


def compare(baseline, candidate):
    differences = []
    for a, b in zip(baseline, candidate):
        ra, rb = a['result'], b['result']
        changed = {key: [ra[key], rb[key]] for key in ra
                   if key not in ('seconds', 'nps') and ra[key] != rb[key]}
        cycle_delta = round((rb['seconds'] - ra['seconds']) * CPU_HZ)
        if abs(cycle_delta) > 16:
            changed['elapsed_cycle_delta'] = cycle_delta
        if changed:
            differences.append(dict(position=a['position'], depth=a['depth'], cap=a['cap'], changes=changed))
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    baseline = measure(args.baseline)
    candidate = measure(args.candidate)
    differences = compare(baseline, candidate)
    baseline_time = sum(row['wall_seconds'] for row in baseline)
    candidate_time = sum(row['wall_seconds'] for row in candidate)
    report = dict(baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                  candidate_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
                  engine_sha256=hashlib.sha256((Path(__file__).resolve().parents[1] / 'src/ENGINE.PRG').read_bytes()).hexdigest(),
                  baseline=baseline, candidate=candidate, differences=differences,
                  baseline_wall_seconds=baseline_time, candidate_wall_seconds=candidate_time,
                  throughput_ratio=baseline_time / candidate_time)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Throughput ratio {report["throughput_ratio"]:.3f}; {len(differences)} differences', flush=True)
    raise SystemExit(bool(differences))


if __name__ == '__main__':
    main()
