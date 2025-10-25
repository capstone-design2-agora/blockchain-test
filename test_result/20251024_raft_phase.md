# Raft Benchmark – Phase Workload (2025-10-24T13:10:53Z)

## Throughput
- Total votes: 100 (success 100, failed 0)
- Wall-clock duration: 37.05 s
- Effective TPS: 2.70 tx/s
- Phase plan: base 70 @ 2 TPS, spike 30 @ 15 TPS

## Block Interval
- Latest observed block: 77
- Average interval (last 50 blocks): 462928881.41 s
- Min/Max interval: 1.00 s / 600644511.00 s

## Confirmation Delay (T_confirmed − T_sent)
- Overall: avg 0.22 s, p95 0.32 s, max 0.42 s (n = 100)
- Phase base: avg 0.21 s, p95 0.32 s, max 0.33 s (n = 70)
- Phase spike: avg 0.23 s, p95 0.32 s, max 0.42 s (n = 30)

## Artifacts
- Summary JSON: `/home/ye422/blockchain-test/quorum-lab/benchmarks/raft_summary_20251024T131053Z.json`
- Detailed CSV: `/home/ye422/blockchain-test/quorum-lab/benchmarks/raft.csv`
- Execution log: `../../../logs/07_benchmark_raft.log`
