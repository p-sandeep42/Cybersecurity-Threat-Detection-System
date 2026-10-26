# Verification artifacts

- [Evaluation](evaluation.md): 15 frozen synthetic scenarios with stipulated ground truth. Known false positives and evasion cases are included, not removed.
- [Benchmark](benchmark.md): 10,000 seeded events, 300 HTTP submissions and 30 dashboard requests; temporary database only.
- [Original benchmark](benchmark-baseline.json): ingestion p95 722.71 ms and 2.15 requests/s before query optimization. The optimized run measured 104.22 ms and 5.01 requests/s under the same workload definition. These are individual local runs, not an SLA.
- [Browser verification](browser-verification.md): real-browser consent, input modes, refresh behavior, automated accessibility checks and inspected screenshots.

Run commands and limitations are in the [application README](../README.md). Reports are generated from actual executions; screenshots and fixture data are synthetic. Retention tests use temporary databases and do not purge your application.
