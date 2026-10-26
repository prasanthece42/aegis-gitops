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
| GitHub chart-validation run | PASS: [40249510939](https://github.com/prasanthece42/aegis-gitops/actions/runs/40249510939) |

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

## Verified publication

The user explicitly approved creating and pushing the private
[prasanthece42/aegis-gitops](https://github.com/prasanthece42/aegis-gitops) repository.
[Chart validation run 40249510939](https://github.com/prasanthece42/aegis-gitops/actions/runs/40249510939)
passed on source commit `be7ff7df5bd24770b2d55ede1c64cc9f46eff844`.

The workflow downloaded checksum-pinned Helm 4.2.4 and kubeconform 0.8.0, checked
Bash syntax, linted/rendered each environment, validated all 12 Kubernetes resources,
and rejected the three invalid-input cases. The final evidence-only documentation
commit uses [skip ci] because it records this already completed run.

There is no publication blocker remaining. Continuous reconciliation, direct private
GHCR pulls into Kind, STAGING/PROD installs, and promotion remain outside this phase.
