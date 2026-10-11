# Emulator test throughput — 2026-10-11

The optimized AgentBridge emulator achieved **12.4% higher throughput** in a
34-search baseline/candidate comparison. Host wall time fell from **52.86 s to
47.02 s**. These are workload- and host-specific measurements.

The baseline was AgentBridge commit
`464e447f4fba9151d1446f07750635812f40adfc`, already built with `-O3` and LTO.
The changes are installed in the sibling `x16-emulator` checkout and preserved
in [tools/emulator-fast.patch](../../../tools/emulator-fast.patch).

## Changes

- **AgentBridge:** check for incoming requests only while execution is paused;
  avoid resolving the current CPU bank when there are no breakpoints.
- **I²C:** sample the bus once per CPU instruction. Its input pins do not change
  between the repeated cycle calls in the original main loop, so those extra
  calls cannot generate another transition.
- **PSG:** when all channel output routes are disabled, resolve the first sample
  normally, then advance the shared noise LFSR with exact linear transforms.
  Oscillator phases and per-channel noise latches retain their scalar-rendered
  values. This skips silent waveform/mixing work without changing future sound.

Most pixel composition was already skipped outside AgentBridge captures.
Raster/frame timing and sprite collision processing continue to run. PCM and
Yamaha synthesis/timers also continue to run. No emulated CPU frequency or search
budget was increased.

## Verification

- All four emulator test suites passed: AgentBridge JSON, input, API, and the
  new PSG idle test. The latter compares optimized output and all hidden channel
  and noise state against scalar synthesis in 300 randomized cases.
- All **34 engine searches** matched moves, scores, completed depths, nodes,
  principal variations, replay counts, legality flags and engine clock ticks.
  Cases cover eight opening/middlegame/endgame positions at fixed depth 3 and
  2/10/20-second caps, plus repetition-history replay and warm transposition tables.
- Measured elapsed bridge cycles differed by at most **9 CPU cycles**
  (1.125 microseconds at 8 MHz), from instruction-boundary polling rounding.

[Full benchmark outputs and binary hashes](benchmark.json) and
[verification details](verification.json) are saved alongside this report.

## Worker scaling

The probe ran 32 fresh ten-second searches per worker setting, including process
startup. Aggregate throughput is emulated seconds completed per host second.

| Workers | Host seconds | Aggregate throughput |
| --- | --- | --- |
| 1 | 51.07 | 6.58 |
| 4 | 13.70 | 24.53 |
| 8 | 7.61 | 44.15 |
| 12 | 6.90 | 48.72 |
| 16 | 6.39 | 52.58 |

Sixteen workers were fastest among the tested settings and were used for the
[1,200-game tournament](../difficulty-2026-10-11/RESULTS.md). Scaling gains
diminish above eight workers. [Raw measurements](workers.json) preserve the values.

## Reproduction

Build the baseline commit separately, apply the saved patch to the candidate
checkout, and build both in Release mode. Run from the chess repository:

```sh
python3 tools/benchmark_emulator.py --baseline /path/to/baseline/x16emu \
  --candidate ../x16-emulator/build/x16emu --out /tmp/emulator-benchmark.json
python3 tools/benchmark_workers.py --workers 1 4 8 12 16 \
  --emulator ../x16-emulator/build/x16emu --out /tmp/emulator-workers.json
```

The comparison exits with a failure status if engine results or clock ticks
differ, or if elapsed-cycle rounding differs by more than 16 cycles.
