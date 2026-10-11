"""Rate the real X16 difficulty levels against local, limited-strength Stockfish.

Requires python-chess and AgentBridge. Results are checkpointed after each game;
rerun the same command to resume. Stockfish UCI_Elo estimates are not FIDE ratings.
"""
import argparse
import datetime
import hashlib
import json
import math
import multiprocessing
from multiprocessing.util import Finalize
from pathlib import Path
import random
import subprocess
import time
from zoneinfo import ZoneInfo

import chess
import chess.engine
import chess.pgn

from match import OPENINGS
from x16uci import X16Engine

ROOT = Path(__file__).resolve().parents[1]
LEVELS = {'easy': 2, 'normal': 10, 'hard': 20}
ours = opponent = settings = None


class LocalStockfish:
    """Blocking UCI transport; avoids cross-thread asyncio dependencies."""
    def __init__(self, path):
        self.process = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1)
        self.id = {}
        self.elo_limits = None
        self.send('uci')
        for line in self.wait('uciok'):
            if line.startswith('id '):
                field, value = line[3:].split(' ', 1)
                self.id[field] = value
            elif line.startswith('option name UCI_Elo '):
                fields = line.split()
                self.elo_limits = (int(fields[fields.index('min') + 1]), int(fields[fields.index('max') + 1]))
        self.game = None

    def send(self, text):
        self.process.stdin.write(text + '\n')
        self.process.stdin.flush()

    def wait(self, marker):
        lines = []
        for line in self.process.stdout:
            line = line.strip()
            lines.append(line)
            if line.startswith(marker):
                return lines
        raise RuntimeError('Stockfish exited before ' + marker)

    def configure(self, options):
        for name, value in options.items():
            if isinstance(value, bool):
                value = str(value).lower()
            self.send(f'setoption name {name} value {value}')
        self.send('isready')
        self.wait('readyok')

    def play(self, board, seconds, game):
        if self.game != game:
            self.send('ucinewgame')
            self.send('isready')
            self.wait('readyok')
            self.game = game
        self.send('position startpos moves ' + ' '.join(move.uci() for move in board.move_stack))
        self.send(f'go movetime {round(seconds * 1000)}')
        line = self.wait('bestmove ')[-1]
        return chess.Move.from_uci(line.split()[1])

    def analyse(self, board, depth, multipv=1):
        """Full-strength callers configure UCI_LimitStrength=false first."""
        self.configure({'MultiPV': multipv})
        self.send('position fen ' + board.fen())
        self.send(f'go depth {depth}')
        infos = {}
        for line in self.wait('bestmove '):
            fields = line.split()
            if not line.startswith('info depth ') or 'score' not in fields or 'pv' not in fields:
                continue
            index = int(fields[fields.index('multipv') + 1]) if 'multipv' in fields else 1
            score_index = fields.index('score')
            score = int(fields[score_index + 2]) if fields[score_index + 1] == 'cp' else None
            infos[index] = dict(score=score,
                                pv=[chess.Move.from_uci(move) for move in fields[fields.index('pv') + 1:]])
        if not infos:
            raise RuntimeError('Stockfish returned no analysis')
        return [infos[index] for index in sorted(infos)]

    def quit(self):
        self.send('quit')
        self.process.communicate(timeout=10)


class NativeEngine(LocalStockfish):
    """Native C UCI backend with the same bounded history replay as X16Engine."""
    depth = 0
    time_per_move = 0
    last = None
    noise = 0
    seed = 1

    def new_game(self):
        self.configure({'Noise': self.noise, 'Seed': self.seed})
        self.send('ucinewgame')
        self.send('isready')
        self.wait('readyok')

    def play(self, board):
        if not self.depth or self.time_per_move:
            raise ValueError('Native rating backend requires fixed depth without a time cap')
        base = board.copy()
        history = []
        for _ in range(min(board.halfmove_clock, len(board.move_stack), 85)):
            history.append(base.pop().uci())
        started = time.monotonic()
        self.send('position fen ' + base.fen() +
                  (' moves ' + ' '.join(reversed(history)) if history else ''))
        self.send(f'go depth {self.depth}')
        lines = self.wait('bestmove ')
        fields = next(line.split() for line in reversed(lines) if line.startswith('info depth '))
        move = chess.Move.from_uci(lines[-1].split()[1])
        self.last = dict(move=move.uci(), depth=int(fields[fields.index('depth') + 1]),
                         score=int(fields[fields.index('cp') + 1]),
                         nodes=int(fields[fields.index('nodes') + 1]),
                         seconds=time.monotonic() - started, jiffies=None)
        if move not in board.legal_moves:
            raise ValueError(f'Native engine returned illegal move {move} for {board.fen()}')
        return move


def cleanup():
    global ours, opponent
    if ours:
        ours.quit()
        ours = None
    if opponent:
        opponent.quit()
        opponent = None


def initialize(config):
    global ours, opponent, settings
    settings = config
    ours = NativeEngine(config['native_engine']) if config.get('backend') == 'native' else X16Engine(emu=config.get('emulator'))
    opponent = LocalStockfish(config['stockfish'])
    opponent.configure({'UCI_LimitStrength': True, 'Threads': 1, 'Hash': 16})
    Finalize(None, cleanup, exitpriority=10)


def play(job):
    level, anchor, number = job
    opening_index = number // 2
    white = number % 2 == 0
    board = chess.Board()
    openings = settings.get('openings', OPENINGS)
    for move in openings[opening_index % len(openings)].split():
        board.push_uci(move)
    opponent.configure({'UCI_Elo': anchor})
    ours.noise = settings.get('noise_by_level', {}).get(level, 0)
    # Common random seeds across candidate policies, independent of worker order.
    ours.seed = 1 + ((settings.get('seed', 1) + opening_index * 131 + anchor * 17 + int(white)) % 65535)
    ours.new_game()
    remaining = 1800.0
    nodes = searches = 0
    depth_total = seconds_total = 0
    budgets = []
    engine_moves = []
    termination = None
    started = time.monotonic()
    while not board.is_game_over(claim_draw=True) and board.ply() < 399:
        if (board.turn == chess.WHITE) == white:
            fixed_depth = settings.get('search_mode') == 'depth'
            limit = settings['levels'][level]
            budget = 0 if fixed_depth else max(2, min(limit, int(remaining) // 30))
            ours.depth = limit if fixed_depth else 0
            ours.time_per_move = budget
            move = ours.play(board)
            engine_moves.append(dict(ply=board.ply(), budget=budget,
                                     **{key: ours.last[key] for key in
                                        ('move', 'depth', 'score', 'nodes', 'jiffies', 'seconds')}))
            elapsed = ours.last['seconds']
            remaining -= elapsed
            budgets.append(budget)
            nodes += ours.last['nodes']
            depth_total += ours.last['depth']
            seconds_total += elapsed
            searches += 1
            if settings.get('backend') != 'native' and remaining <= 0:
                termination = 'time forfeit'
                break
        else:
            move = opponent.play(board, settings['sf_time'], game=job)
        assert move in board.legal_moves, (job, move, board.fen())
        board.push(move)
    if termination:
        result = '0-1' if white else '1-0'
    elif board.ply() >= 399 and not board.is_game_over(claim_draw=True):
        result, termination = '1/2-1/2', 'game move limit'
    else:
        result = board.result(claim_draw=True)
        termination = board.outcome(claim_draw=True).termination.name.lower()
    game = chess.pgn.Game.from_board(board)
    fixed_depth = settings.get('search_mode') == 'depth'
    limit = settings['levels'][level]
    platform = 'native C' if settings.get('backend') == 'native' else 'X16'
    name = f'CX16-CHESS {level} ({platform} {limit} ply)' if fixed_depth else f'CX16-CHESS {level} (X16 {limit}s cap)'
    game.headers.update(Event='X16 difficulty strength test', Site='Local AgentBridge / Stockfish',
                        Date=settings['date'].replace('-', '.'), Round=str(number + 1),
                        White=name if white else f'Stockfish 16 UCI_Elo {anchor}',
                        Black=f'Stockfish 16 UCI_Elo {anchor}' if white else name,
                        Result=result, Termination=termination)
    for key, value in (('X16Clock', '1800 seconds; fixed depth, no move time cap' if fixed_depth else '1800 seconds; max(2, min(cap, remaining/30))'),
                       ('StockfishMoveTime', str(settings['sf_time'])), ('OpeningPair', str(opening_index))):
        game.headers[key] = value
    if settings.get('backend') == 'native':
        game.headers['X16Clock'] = 'untimed fixed-depth native C; host time is not X16 time'
    points = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}[result]
    record = dict(level=level, opponent_elo=anchor, number=number, opening_pair=opening_index,
                  white=white, result=result, points=points if white else 1 - points,
                  termination=termination, plies=board.ply(), searches=searches,
                  nodes=nodes, depth_total=depth_total, emulated_seconds=seconds_total,
                  budget_min=min(budgets), budget_max=max(budgets),
                  wall_seconds=round(time.monotonic() - started, 3))
    record['engine_moves'] = engine_moves
    if settings.get('noise_by_level'):
        record.update(noise=ours.noise, seed=ours.seed)
        game.headers['RootNoise'] = str(ours.noise)
        game.headers['RandomSeed'] = str(ours.seed)
    if settings.get('backend') == 'native':
        record['host_search_seconds'] = record.pop('emulated_seconds')
    return record, str(game)


def rating(score, anchors):
    if score <= 0:
        return None
    if score >= 1:
        return None
    low, high = -2000.0, 5000.0
    for _ in range(80):
        value = (low + high) / 2
        expected = sum(1 / (1 + 10 ** ((anchor - value) / 400)) for anchor in anchors) / len(anchors)
        if expected < score:
            low = value
        else:
            high = value
    return round((low + high) / 2)


def summarize(records, anchors, levels=None, search_mode='time'):
    summaries = {}
    for level, cap in (levels or LEVELS).items():
        rows = [r for r in records if r['level'] == level]
        if not rows:
            continue
        points = sum(r['points'] for r in rows)
        groups = {}
        for row in rows:
            groups.setdefault(row['opening_pair'], []).append(row)
        # Resample whole opening groups, preserving colour and opponent pairing.
        # Confidence covers game/opening sampling, not Stockfish calibration.
        randomizer = random.Random(16)
        clusters = list(groups.values())
        scores = []
        for _ in range(20000):
            sample = [r for _ in clusters for r in randomizer.choice(clusters)]
            scores.append(sum(r['points'] for r in sample) / len(sample))
        scores.sort()
        searches = sum(r['searches'] for r in rows)
        summaries[level] = dict(cap_seconds=cap, games=len(rows), points=points,
            wins=sum(r['points'] == 1 for r in rows), draws=sum(r['points'] == .5 for r in rows),
            losses=sum(r['points'] == 0 for r in rows), score=points / len(rows),
            estimated_elo=rating(points / len(rows), anchors),
            confidence_95=[rating(scores[500], anchors), rating(scores[19499], anchors)],
            confidence_score_95=[scores[500], scores[19499]],
            mean_depth=sum(r['depth_total'] for r in rows) / searches,
            mean_nodes=sum(r['nodes'] for r in rows) / searches,
            mean_search_seconds=sum(r.get('host_search_seconds', r.get('emulated_seconds', 0)) for r in rows) / searches,
            per_opponent={str(anchor): dict(games=sum(r['opponent_elo'] == anchor for r in rows),
                points=sum(r['points'] for r in rows if r['opponent_elo'] == anchor)) for anchor in anchors})
        if search_mode == 'depth':
            summaries[level]['target_depth'] = summaries[level].pop('cap_seconds')
    return summaries


def paired_comparisons(records, anchors, levels=None):
    """Resample the same opening groups across levels to compare their ratings."""
    levels = levels or LEVELS
    groups = {level: {} for level in levels}
    for row in records:
        groups[row['level']].setdefault(row['opening_pair'], []).append(row)
    first = next(iter(levels))
    keys = sorted(groups[first])
    assert keys and all(sorted(g) == keys for g in groups.values())
    assert all(len(g[key]) == len(groups[first][key]) for g in groups.values() for key in keys)
    names = list(levels)
    pairs = [(a, b) for a in reversed(names) for b in names[:names.index(a)]]
    differences = {f'{a}_minus_{b}': [] for a, b in pairs}
    cache = {}
    def estimate(points, count):
        score = points / count
        if score not in cache:
            value = rating(score, anchors)
            cache[score] = value if value is not None else (-math.inf if score == 0 else math.inf)
        return cache[score]
    randomizer = random.Random(16)
    for _ in range(20000):
        sample = [randomizer.choice(keys) for _ in keys]
        ratings = {}
        for level, clusters in groups.items():
            rows = [r for key in sample for r in clusters[key]]
            ratings[level] = estimate(sum(r['points'] for r in rows), len(rows))
        for a, b in pairs:
            differences[f'{a}_minus_{b}'].append(ratings[a] - ratings[b])
    actual = {level: estimate(sum(r['points'] for r in records if r['level'] == level),
                              sum(r['level'] == level for r in records)) for level in levels}
    result = {}
    for a, b in pairs:
        key = f'{a}_minus_{b}'
        values = sorted(differences[key])
        result[key] = dict(estimated_difference=actual[a] - actual[b],
                           confidence_95=[values[500], values[19499]])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--games-per-opponent', type=int, default=24)
    parser.add_argument('--opponents', type=int, nargs='+', default=[1320, 1500])
    parser.add_argument('--depths', type=int, nargs='+', help='Fixed depths 1..8 instead of legacy time-capped levels')
    parser.add_argument('--noises', type=int, nargs='+', help='Root score noise in centipawns, 0..2000; requires --depths 1')
    parser.add_argument('--seed', type=int, default=1, help='Reproducible per-game random seed base')
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--stockfish', default='/usr/games/stockfish')
    parser.add_argument('--sf-time', type=float, default=.1)
    parser.add_argument('--emulator', type=Path, help='AgentBridge executable; its SHA-256 is recorded')
    parser.add_argument('--native-engine', type=Path, help='Native C UCI executable; requires --depths')
    parser.add_argument('--openings', type=Path, help='JSON opening suite from generate_openings.py')
    parser.add_argument('--date', default=datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).date().isoformat())
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.native_engine and (not args.depths or args.emulator):
        parser.error('--native-engine requires --depths and cannot be combined with --emulator')
    if args.depths and (len(set(args.depths)) != len(args.depths) or any(d not in range(1, 9) for d in args.depths)):
        parser.error('--depths must be distinct values between 1 and 8')
    levels = {f'ply{d}': d for d in sorted(args.depths)} if args.depths else LEVELS
    if args.noises is not None:
        if args.depths != [1] or len(set(args.noises)) != len(args.noises) or any(n not in range(2001) for n in args.noises):
            parser.error('--noises requires --depths 1 and distinct values between 0 and 2000')
        levels = {f'noise{n}': 1 for n in sorted(args.noises)}
    if args.games_per_opponent <= 0 or args.games_per_opponent % 2:
        parser.error('--games-per-opponent must be positive and even')
    if args.workers < 1 or args.sf_time <= 0:
        parser.error('--workers and --sf-time must be positive')
    if len(set(args.opponents)) != len(args.opponents):
        parser.error('--opponents must be distinct')
    openings = None
    if args.openings:
        suite = json.loads(args.openings.read_text())
        openings = suite['openings']
        positions = set()
        if not isinstance(openings, list) or len(openings) < args.games_per_opponent // 2:
            parser.error('Opening suite must contain one distinct opening per colour pair')
        for line in openings:
            board = chess.Board()
            for move in line.split():
                board.push_uci(move)
            if not board.move_stack or board.is_game_over(claim_draw=True):
                parser.error('Opening must be nonempty and unfinished')
            position = board.fen().split(' ', 4)[0:4]
            key = tuple(position)
            if key in positions:
                parser.error('Opening suite contains duplicate final positions')
            positions.add(key)
        openings = openings[:args.games_per_opponent // 2]
    elif args.games_per_opponent // 2 > len(OPENINGS):
        parser.error('Extended runs require --openings to avoid repeating the fixed opening list')
    args.out = args.out or ROOT / 'build/engine' / ('difficulty-' + args.date)
    if (args.out / 'evidence.zip').exists():
        parser.error('This run is archived; choose a new --out directory for testing')
    sf = LocalStockfish(args.stockfish)
    try:
        low, high = sf.elo_limits
        if any(not low <= anchor <= high for anchor in args.opponents):
            parser.error(f'Stockfish supports UCI_Elo {low}..{high}')
        identity = sf.id
    finally:
        sf.quit()
    metadata = dict(stockfish=str(Path(args.stockfish).resolve()), stockfish_id=identity,
                    sf_time=args.sf_time, date=args.date, games_per_opponent=args.games_per_opponent,
                    opponents=args.opponents, levels=levels, clock_seconds=1800,
                    engine_sha256=hashlib.sha256((ROOT / 'src/ENGINE.PRG').read_bytes()).hexdigest())
    if args.depths:
        metadata['search_mode'] = 'depth'
    if args.noises is not None:
        metadata.update(noise_by_level={f'noise{n}': n for n in sorted(args.noises)}, seed=args.seed,
                        weakness_policy='full-window root scores plus uniform integer noise 0..N; xorshift16')
    if args.native_engine:
        metadata.update(backend='native', native_engine=str(args.native_engine.resolve()),
                        native_engine_sha256=hashlib.sha256(args.native_engine.read_bytes()).hexdigest(),
                        stockfish_sha256=hashlib.sha256(Path(args.stockfish).read_bytes()).hexdigest(),
                        timing_source='host wall time; no X16 clock simulation', clock_seconds=None)
    if args.emulator:
        metadata.update(emulator=str(args.emulator.resolve()),
                        emulator_sha256=hashlib.sha256(args.emulator.read_bytes()).hexdigest())
    if openings:
        metadata.update(openings=openings,
                        opening_suite_sha256=hashlib.sha256(args.openings.read_bytes()).hexdigest())
    args.out.mkdir(parents=True, exist_ok=True)
    meta_path = args.out / 'configuration.json'
    if meta_path.exists():
        assert json.loads(meta_path.read_text()) == metadata, 'Existing run uses different settings/engine; use another --out'
    else:
        meta_path.write_text(json.dumps(metadata, indent=2) + '\n')
    checkpoint = args.out / 'games.jsonl'
    records = [json.loads(line) for line in checkpoint.read_text().splitlines()] if checkpoint.exists() else []
    completed = {(r['level'], r['opponent_elo'], r['number']) for r in records}
    jobs = [(level, anchor, number) for number in range(args.games_per_opponent)
            for level in reversed(levels) for anchor in args.opponents
            if (level, anchor, number) not in completed]
    game_dir = args.out / 'games'
    game_dir.mkdir(exist_ok=True)
    total = len(jobs) + len(completed)
    print(f'Local {identity["name"]}; {len(jobs)} games remaining; {args.workers} workers', flush=True)
    with checkpoint.open('a') as output, multiprocessing.Pool(args.workers, initialize, (metadata,)) as pool:
        for record, pgn in pool.imap_unordered(play, jobs, chunksize=1):
            filename = f'{record["level"]}-{record["opponent_elo"]}-{record["number"]:02d}.pgn'
            (game_dir / filename).write_text(pgn + '\n\n')
            output.write(json.dumps(record) + '\n')
            output.flush()
            records.append(record)
            rows = [r for r in records if r['level'] == record['level']]
            print(f'{len(records):3d}/{total}' +
                  f' {record["level"]:6s} vs {record["opponent_elo"]} '
                  f'{"W" if record["white"] else "B"} {record["result"]} ({record["plies"]} plies); '
                  f'level score {sum(r["points"] for r in rows):g}/{len(rows)}', flush=True)
    summaries = summarize(records, args.opponents, levels, 'depth' if args.depths else 'time')
    report = dict(configuration=metadata, summaries=summaries,
                  paired_comparisons=paired_comparisons(records, args.opponents, levels))
    (args.out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    for level in levels:
        rows = sorted((r for r in records if r['level'] == level), key=lambda r: (r['opponent_elo'], r['number']))
        text = ''.join((game_dir / f'{level}-{r["opponent_elo"]}-{r["number"]:02d}.pgn').read_text() for r in rows)
        (args.out / (level + '.pgn')).write_text(text)
        print(level, json.dumps(summaries[level]), flush=True)
    print(f'Saved {args.out / "summary.json"}', flush=True)
    if args.native_engine:
        from validate_difficulty_run import validate
        validation = validate(args.out)
        (args.out / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
        print(f'Validated {validation["games"]} games', flush=True)


if __name__ == '__main__':
    main()
