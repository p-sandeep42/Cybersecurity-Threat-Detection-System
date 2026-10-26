# Local performance benchmark

Real Requests-to-Waitress HTTP; single SQLite process; 10,000 successes sharing one IP; 200 subjects; unique sessions; rate limiting disabled only in the disposable lab because the production 120/minute limit is below the 300/minute benchmark load.

Environment: Windows-10-10.0.19045-SP0; Python 3.13.0; Intel64 Family 6 Model 140 Stepping 1, GenuineIntel; 8 logical CPUs.

| Measurement | Observed | Target |
|---|---:|---:|
| Ingestion p95 | 104.22 ms | <500 ms |
| Dashboard p95 (30 requests) | 485.93 ms | <1000 ms |
| Achieved ingestion rate | 5.01 requests/s | 5 requests/s |
| HTTP failures | 0 | 0 |

This measures a fixed benign workload, not attack-heavy worst-case capacity or an SLA. Browser polling adds up to five seconds to visible alert latency. Hardware contention changes results. Raw observations and target flags are in benchmark.json. No operator data was accessed.
