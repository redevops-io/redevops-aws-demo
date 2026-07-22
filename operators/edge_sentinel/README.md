# edge_sentinel — ECR supply-chain operator (Mission Runtime `/invoke`)

Scans images in ECR, proposes hardening, rebuilds+pushes, and rolls the cluster.

`sentinel.scan` (also provides `image_scanned`, so it replaces the deploy_app placeholder scanner) ·
`sentinel.harden` (gated — the "harden?" approval; rebuild `--pull` + push) · `sentinel.rollout`
(`kubectl rollout restart`) · `sentinel.rescan` (confirm cleared).

Real mode: ECR image scanning + `docker` + `kubectl`. Injectable `ecr`/`run` seams make the whole
loop testable at $0 (see `missions/harden_images.py` + `tests/test_edge_sentinel.py`).
