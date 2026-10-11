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

    def quit(self):
        self.send('quit')
        self.process.communicate(timeout=10)


def cleanup():
    if ours:
        ours.quit()
    if opponent:
        opponent.quit()


def initialize(config):
    global ours, opponent, settings
    settings = config
    ours = X16Engine()
    opponent = LocalStockfish(config['stockfish'])
    opponent.configure({'UCI_LimitStrength': True, 'Threads': 1, 'Hash': 16})
    Finalize(None, cleanup, exitpriority=10)


def play(job):
    level, anchor, number = job
    opening_index = number // 2
    white = number % 2 == 0
    board = chess.Board()
    for move in OPENINGS[opening_index % len(OPENINGS)].split():
        board.push_uci(move)
    opponent.configure({'UCI_Elo': anchor})
    ours.new_game()
    remaining = 1800.0
    nodes = searches = 0
    depth_total = seconds_total = 0
    budgets = []
    termination = None
    started = time.monotonic()
    while not board.is_game_over(claim_draw=True) and board.ply() < 399:
        if (board.turn == chess.WHITE) == white:
            budget = max(2, min(LEVELS[level], int(remaining) // 30))
            ours.time_per_move = budget
            move = ours.play(board)
            elapsed = ours.last['seconds']
            remaining -= elapsed
            budgets.append(budget)
            nodes += ours.last['nodes']
            depth_total += ours.last['depth']
            seconds_total += elapsed
            searches += 1
            if remaining <= 0:
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
    name = f'CX16-CHESS {level} (X16 {LEVELS[level]}s cap)'
    game.headers.update(Event='X16 difficulty strength test', Site='Local AgentBridge / Stockfish',
                        Date=settings['date'].replace('-', '.'), Round=str(number + 1),
                        White=name if white else f'Stockfish 16 UCI_Elo {anchor}',
                        Black=f'Stockfish 16 UCI_Elo {anchor}' if white else name,
                        Result=result, Termination=termination)
    for key, value in (('X16Clock', '1800 seconds; max(2, min(cap, remaining/30))'),
                       ('StockfishMoveTime', str(settings['sf_time'])), ('OpeningPair', str(opening_index))):
        game.headers[key] = value
    points = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}[result]
    record = dict(level=level, opponent_elo=anchor, number=number, opening_pair=opening_index,
                  white=white, result=result, points=points if white else 1 - points,
                  termination=termination, plies=board.ply(), searches=searches,
                  nodes=nodes, depth_total=depth_total, emulated_seconds=seconds_total,
                  budget_min=min(budgets), budget_max=max(budgets),
                  wall_seconds=round(time.monotonic() - started, 3))
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


def summarize(records, anchors):
    summaries = {}
    for level, cap in LEVELS.items():
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
            mean_search_seconds=sum(r['emulated_seconds'] for r in rows) / searches,
            per_opponent={str(anchor): dict(games=sum(r['opponent_elo'] == anchor for r in rows),
                points=sum(r['points'] for r in rows if r['opponent_elo'] == anchor)) for anchor in anchors})
    return summaries


def paired_comparisons(records, anchors):
    """Resample the same opening groups across levels to compare their ratings."""
    groups = {level: {} for level in LEVELS}
    for row in records:
        groups[row['level']].setdefault(row['opening_pair'], []).append(row)
    keys = sorted(groups['easy'])
    assert keys and all(sorted(g) == keys for g in groups.values())
    assert all(len(g[key]) == len(groups['easy'][key]) for g in groups.values() for key in keys)
    pairs = [('hard', 'easy'), ('hard', 'normal'), ('normal', 'easy')]
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
                              sum(r['level'] == level for r in records)) for level in LEVELS}
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
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--stockfish', default='/usr/games/stockfish')
    parser.add_argument('--sf-time', type=float, default=.1)
    parser.add_argument('--date', default=datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).date().isoformat())
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.games_per_opponent <= 0 or args.games_per_opponent % 2:
        parser.error('--games-per-opponent must be positive and even')
    if len(set(args.opponents)) != len(args.opponents):
        parser.error('--opponents must be distinct')
    args.out = args.out or ROOT / 'docs/engine' / ('difficulty-' + args.date)
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
                    opponents=args.opponents, levels=LEVELS, clock_seconds=1800,
                    engine_sha256=hashlib.sha256((ROOT / 'src/ENGINE.PRG').read_bytes()).hexdigest())
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
            for level in reversed(LEVELS) for anchor in args.opponents
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
    summaries = summarize(records, args.opponents)
    report = dict(configuration=metadata, summaries=summaries,
                  paired_comparisons=paired_comparisons(records, args.opponents))
    (args.out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    for level in LEVELS:
        rows = sorted((r for r in records if r['level'] == level), key=lambda r: (r['opponent_elo'], r['number']))
        text = ''.join((game_dir / f'{level}-{r["opponent_elo"]}-{r["number"]:02d}.pgn').read_text() for r in rows)
        (args.out / (level + '.pgn')).write_text(text)
        print(level, json.dumps(summaries[level]), flush=True)
    print(f'Saved {args.out / "summary.json"}', flush=True)


if __name__ == '__main__':
    main()
