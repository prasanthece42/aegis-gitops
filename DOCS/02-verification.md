# Phase 3 verification

Verified October 25, 2026 (America/Halifax).

| Check | Result |
| --- | --- |
| Helm lint and rendering | PASS: DEV, STAGING, PROD |
| Kubernetes 1.35 schema validation | PASS: 4 resources per environment, 12 total; no invalid/skipped resources |
| Required image digest | PASS: empty and malformed digest inputs rejected |
| Replica validation | PASS: zero replicas rejected |
| Local server-side validation | PASS: DEV resources accepted by Kubernetes |
| Real DEV installation | PASS: Helm deployed sample-api 0.1.0, one Ready/available replica |
| Runtime security and health | PASS: UID 10001, required security/probes/resources, actual Service HTTP |
| Pod replacement | PASS: new pod identity with same image and healthy endpoint |
| Namespace security | PASS: privileged Pod dry-run rejected by Restricted Pod Security |
| STAGING/PROD deployment | NOT RUN: rendered only |
| GitHub chart-validation run | NOT RUN: publication blocked pending exact-destination approval |

The local image is a scanned native arm64 build, loaded into Kind and selected by its
actual manifest digest using a gitignored local override. The tracked environment
values continue to reference the verified Phase 2 GHCR amd64 digest. A private GHCR
pull into Kind has not been exercised.

Commands: `bash scripts/validate-chart.sh` in this repository; the sibling application's
`bootstrap-local-k8s.sh`, `verify-local-k8s.sh`, and `verify-kind-recovery.sh` executed
against an isolated kubeconfig and kind-aegis-dev context. Its DOCS/15-phase-3-report.md
and deployment receipt contain full evidence and commands.

CI performs static Helm/Kubernetes-schema checks only. No deployment credentials,
Argo CD resources, promotion workflow, or production installation has been added.

## Publication blocker

The Helm chart is fully implemented and committed locally. Automatic approval review
rejected creating/pushing the private `prasanthece42/aegis-gitops` repository because
the user has not explicitly approved that exact new destination. No GitOps remote
was created or pushed. Local chart and Kind checks remain valid; GitHub chart CI
requires that approval before publication.
