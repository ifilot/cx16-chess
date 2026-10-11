# Extended difficulty strength test — 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

The actual banked 65C02 engine played **1,200 games** against local Stockfish 16:
**400 games per difficulty**, using **100 distinct opening positions**.
The tournament took **2 hours 40 minutes** with 16 workers.

Normal has the highest point estimate in this run. Its estimated advantage over
Easy is **33 Elo**, but the paired 95% interval is **−11 to +77**. All three
pair comparisons include zero, so the experiment still does not establish a
strict ordering. The earlier Easy-over-Normal result does not persist here.

| Difficulty | Cap | Wins / draws / losses | Points | Estimated Elo | 95% interval |
| --- | --- | --- | --- | --- | --- |
| Easy | 2 s | 146 / 51 / 203 | 171.5 / 400 (42.9%) | 1357 | 1321–1391 |
| Normal (Medium in the UI) | 10 s | 172 / 34 / 194 | 189 / 400 (47.3%) | 1390 | 1359–1419 |
| Hard | 20 s | 158 / 53 / 189 | 184.5 / 400 (46.1%) | 1381 | 1349–1413 |

Ratings are on **Stockfish's UCI_Elo scale**. The intervals describe sampling
uncertainty under this benchmark, including opening-position variation; they
do not measure uncertainty in Stockfish's calibration to human ratings.

## Paired comparisons

The same opening position, colour and opponent combinations were used for every
level. Bootstrap comparisons resample the same whole opening groups across levels.

| Comparison | Estimated Elo difference | Paired 95% interval |
| --- | --- | --- |
| Normal minus Easy | +33 | −11 to +77 |
| Hard minus Easy | +24 | −24 to +73 |
| Hard minus Normal | −9 | −54 to +37 |

The [earlier 48-game-per-level run](../difficulty-2026-10-10/RESULTS.md) estimated
Normal minus Easy at −76, with an interval of −246 to +59. This larger experiment
substantially narrows the uncertainty and gives Normal a higher point estimate
against both opponent settings. It provides no evidence for a large Easy
advantage. Small strength differences remain uncertain, and deeper search has
not produced a clearly separated difficulty ladder in this benchmark.

The engine binary is the same as in the earlier test. The opening suite is
larger and uses longer forced lines, so the change in ratings cannot be
attributed solely to increased sample size.

## Opponents and search statistics

Each opponent cell contains 200 games: 100 as White and 100 as Black.

| Difficulty | Points vs Stockfish 1320 | Points vs Stockfish 1500 |
| --- | --- | --- |
| Easy | 104 / 200 | 67.5 / 200 |
| Normal | 114.5 / 200 | 74.5 / 200 |
| Hard | 112 / 200 | 72.5 / 200 |

| Difficulty | Mean depth | Mean nodes / search | Mean bridge elapsed (emulated s) |
| --- | --- | --- | --- |
| Easy | 3.41 | 1198 | 2.41 |
| Normal | 4.71 | 5419 | 9.89 |
| Hard | 5.35 | 10278 | 18.52 |

The larger budgets produce deeper searches. The bridge elapsed column includes
position replay and mailbox overhead; search limits are soft because the engine
checks time periodically. Long games reduce the budget as the clock runs down.

## Method and validation

- The [recorded opening suite](openings.json) contains 100 distinct positions
  after 8, 10 or 12 plies. Lines start from the 16 familiar opening stems in
  `tools/match.py`, then sample moves within 50 centipawns of Stockfish's best
  candidate at depth 8. Final positions were checked within 100 centipawns of
  equality at depth 10. Generation uses seed 16 and full-strength Stockfish.
  Saving the suite makes the starting positions reproducible.
- Every position was played in both colours against UCI_Elo 1320 and 1500 at
  each difficulty. Stockfish used `Threads=1`, `Hash=16`,
  `UCI_LimitStrength=true`, and 0.1 host seconds per move.
- The actual `ENGINE.PRG` ran at **8 MHz emulated time**. Each X16 side received
  an 1800-second virtual clock, with move budget
  `max(2, min(difficulty_cap, remaining_seconds // 30))`. Elapsed bridge cycles
  were charged to that clock. This includes replay/mailbox overhead and
  approximates the game's clock rather than reproducing GUI costs exactly.
- Ratings solve the average expected score against the two Elo anchors.
  Intervals use 20,000 bootstrap samples of whole opening groups, with seed 16.
  Each group contains both colours and both opponents; paired comparisons use
  identical sampled groups across levels.
- [Validation](validation.json) checked all 1,200 legal PGNs, colours, opponents,
  opening prefixes, recorded results, and per-move search traces. There are
  **53,070 recorded engine searches**. Natural endings were 1060 checkmates,
  126 threefold repetitions, 10 fifty-move draws, one insufficient-material
  draw, and one stalemate. **Two Hard games ended on clock forfeits**, against
  Stockfish 1500 after 282 and 296 plies. There were no move-limit adjudications.

The [emulator optimizations](../emulator-performance-2026-10-11/RESULTS.md)
preserved moves, scores, depths, nodes, principal variations and engine clock
ticks in 34 baseline/candidate comparisons. Emulator and engine hashes are
recorded with the tournament configuration.

## Artifacts and reproduction

- [Summary and paired comparisons](summary.json), [configuration](configuration.json),
  [opening suite](openings.json), [validation](validation.json), and [run log (archive)](evidence.zip).
- PGNs: [Easy (archive)](evidence.zip), [Normal (archive)](evidence.zip), [Hard (archive)](evidence.zip).
- `games.jsonl` contains per-game totals and each engine move's ply, budget,
  chosen move, depth, evaluation, node count, clock ticks and emulated elapsed time.
- Runner: [tools/rate_difficulties.py](../../../tools/rate_difficulties.py).

With python-chess, Stockfish and the optimized AgentBridge executable available,
run from the repository root using the saved opening suite:

```sh
python3 tools/rate_difficulties.py --games-per-opponent 200 --workers 16 \
  --date 2026-10-11 --emulator ../x16-emulator/build/x16emu \
  --openings docs/engine/difficulty-2026-10-11/openings.json \
  --out docs/engine/difficulty-2026-10-11
python3 tools/validate_difficulty_run.py docs/engine/difficulty-2026-10-11
```

Matching configurations resume checkpointed games. A fresh experiment or changed
engine, emulator or opening suite requires a new output directory.
