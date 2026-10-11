"""Measure aggregate emulator throughput at different worker counts."""
import argparse
import json
import multiprocessing
from multiprocessing.util import Finalize
from pathlib import Path
import time

from engine_bridge import EngineBridge

engine = None


def initialize(executable):
    global engine
    engine = EngineBridge(emu=executable)
    Finalize(None, engine.close, exitpriority=10)


def search(number):
    return engine.search('startpos', time_limit=10, fresh=True)['seconds']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, nargs='+', default=[1, 4, 8, 12, 16])
    parser.add_argument('--searches', type=int, default=32)
    parser.add_argument('--emulator', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.searches < 1 or any(workers < 1 for workers in args.workers):
        parser.error('searches and workers must be positive')
    rows = []
    for workers in args.workers:
        started = time.perf_counter()
        with multiprocessing.Pool(workers, initialize, (args.emulator,)) as pool:
            seconds = pool.map(search, range(args.searches))
        elapsed = time.perf_counter() - started
        row = dict(workers=workers, searches=args.searches, wall_seconds=elapsed,
                   aggregate_emulated_seconds_per_host_second=sum(seconds) / elapsed)
        rows.append(row)
        print(json.dumps(row), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
