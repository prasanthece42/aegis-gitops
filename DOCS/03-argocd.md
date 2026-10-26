# Phase 4 — Argo CD local reconciliation

The Application `sample-api-local` watches this private repository's main branch,
renders charts/sample-api with DEV values plus environments/local/values.yaml,
and reconciles only the aegis-dev namespace on the in-cluster Kubernetes API.

The local profile records the actual scanned arm64 image manifest loaded during
Phase 3. Its pull policy is Never; a missing cached image fails rather than pulling
a different remote image. Normal dev/staging/prod values retain registry references.
After recreating Kind, load the referenced native image before enabling the Application,
or intentionally rebuild/scan and commit its new local manifest digest.

Argo renders Helm templates; it does not run helm upgrade or maintain Helm release
history. Existing Phase 3 Helm metadata is historical; the application repository's
manual Helm bootstrap now refuses to overwrite the Argo-managed Application.
Annotation-based tracking preserves chart selector/instance labels while allowing
the Argo Application name to differ from the Helm releaseName sample-api.

## Declarative files

| File | Purpose |
| --- | --- |
| argocd/config/argocd-cm.yaml | Annotation tracking and 30-second polling with small jitter. |
| argocd/projects/aegis-local.yaml | Allow only this repo, local cluster, DEV namespace, and the required resource kinds. |
| argocd/projects/default-deny.yaml | Remove source/destination access from the default project. |
| argocd/applications/sample-api-local.yaml | Main branch, chart path, values, automatic sync, prune, self-heal, retry, and namespace policy. |
| environments/local/values.yaml | Git-tracked desired state for the native local Kind image. |

A repository Secret is generated on the workstation, never stored in Git. It contains
a read-only SSH deploy key scoped to this repository and project. Argo's pinned
known-hosts ConfigMap verifies GitHub's SSH host key; no insecure SSH bypass is used.
The deploy key is persistent and should be revoked on retirement. It cannot push
commits or read other private repositories. No GitHub account token is copied to Kind.

Only local DEV is automatically synchronized. STAGING/PROD Applications and promotion
approvals are later work. The Argo controller retains the upstream installation's
Kubernetes permissions; AppProject boundaries constrain this Application rather than
claiming the controller itself has namespace-only RBAC.

## Bootstrap and verification

Use the application repository's install-local-argocd.sh, register-argocd-repository.sh,
connect-local-argocd.sh, and verify-local-argocd.sh scripts. All target an explicit
isolated kubeconfig/context. The root project/Application definitions are applied
once by workstation bootstrap; this is not an app-of-apps setup. Subsequent workload
changes are read from Git automatically.

## Verified real Git flow

- Setup commit 8c5ef9f: Synced/Healthy, one replica.
- Commit 25dcd8c: changed local replicaCount to two; Argo polled and applied it automatically.
- A live scale to three produced OutOfSync; self-healing restored two without a new Git commit.
- Revert 6400f50: Argo automatically restored one replica and healthy HTTP.

No manual Argo sync/refresh or Helm upgrade drove these stages. The AppProject
rejected a temporary forbidden-destination application with automated sync disabled;
that test definition was removed. Argo server /healthz and manual-Helm guard passed.

GitHub validation passed for [setup](https://github.com/prasanthece42/aegis-gitops/actions/runs/40250659921),
[scale](https://github.com/prasanthece42/aegis-gitops/actions/runs/40250732778), and
[revert](https://github.com/prasanthece42/aegis-gitops/actions/runs/40250770351).
Full evidence and the local receipt are in the sibling application's
[Phase 4 report](https://github.com/prasanthece42/aegis-cicd/blob/main/DOCS/18-phase-4-report.md).

This phase connects GitOps changes to Kubernetes. Publishing a new GHCR image still
does not automatically modify GitOps. Cross-repository release updates are a separate
integration; no automatic source-to-production delivery is claimed.
