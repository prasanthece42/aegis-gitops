# Phase 5 release management

The application publishes a tested amd64/arm64 OCI index, durable public receipt and
exact OCI bundle. Local delivery verifies source workflow identity and bundle hash,
imports the same root digest into Kind, and records cache health on the source commit.
GHCR remains private. Repository histories were scanned before their approved public
visibility change. The former Argo SSH deploy key has been revoked; Argo uses HTTPS.

| Branch | Environment | Argo policy | Merge control |
| --- | --- | --- | --- |
| main | DEV | Automatic sync/self-heal | Required chart and promotion-policy checks |
| staging | STAGING | Explicit sync | Checks and recent healthy DEV at exact revision/digest |
| prod | PROD | Explicit sync | Checks, healthy STAGING and fresh independent human approval |

All branches enforce PR controls for administrators, strict current checks, linear
history, no force-push/deletion, and resolved conversations. Sensitive chart, policy,
workflow and tool paths require CODEOWNERS review. PROD dismisses stale approvals and
requires approval of the last push by another actor. No script auto-approves PROD.

scripts/promotion.py reads public release receipts and validates their successful
source release workflow, source SHA, root index and both platform test receipts.
The workflow writes its own PR using a short-lived GITHUB_TOKEN. It explicitly dispatches
validation because bot-token PR creation does not reliably trigger normal PR workflows.
GitHub may additionally require approval to execute a bot PR validation workflow;
that execution approval is distinct from a human production PR review.

Validation uses policy code from trusted main, compares exact PR head and changed
paths, and rejects cross-environment edits. Promotion requires an allowlisted operator's
latest successful health status at the exact prior environment revision and image,
less than 24 hours old. A failed observation blocks promotion. Reviews must be current,
independent, human and allowlisted. Receipts/statuses are unsigned operator/workflow
evidence, not signed runtime attestations.

The policy tests cover release identity, digest preservation, expired/failed health,
and missing, stale, self or bot reviews. To run them in a colon-free virtual environment:

```bash
python3.12 -m venv /tmp/aegis-gitops-venv
/tmp/aegis-gitops-venv/bin/pip install --require-hashes -r requirements-dev.txt
/tmp/aegis-gitops-venv/bin/pytest
bash scripts/validate-chart.sh
```

## Actual verification

- DEV PR #1 merged; Argo became Synced/Healthy at the chosen release digest.
- STAGING PR #2 merged; explicit Argo sync deployed two healthy replicas at that digest.
- PROD PR #3 is open: missing human approval intentionally fails policy. No PROD sync occurred.
- DEV failure drill PR #4 lowered memory to 8Mi; the new pod was OOMKilled.
- A STAGING promotion attempt against failed DEV was rejected by the health gate.
- Rollback PR #5 restored memory; Argo recovered DEV without changing the image.

Source release: [40259693000](https://github.com/prasanthece42/aegis-cicd/actions/runs/40259693000).
Index digest: sha256:e02908653b52ef077cbcde43874edb49449f1bc47af5a7e469e17f0bc8fee8ef.
Production review: [PR #3](https://github.com/prasanthece42/aegis-gitops/pull/3).

For full code explanations, local commands, failure evidence and limitations, read the
[application release guide](https://github.com/prasanthece42/aegis-cicd/blob/main/DOCS/20-release-management-guide.md)
and [Phase 5 report](https://github.com/prasanthece42/aegis-cicd/blob/main/DOCS/21-phase-5-report.md).
The background local bridge awaits separate approval. No AWS resources are provisioned.
