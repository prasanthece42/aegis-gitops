# GitOps repository architecture — Phase 3

Historical Helm bootstrap design. [Phase 4](03-argocd.md) now supplies continuous
Argo CD reconciliation and a tracked local profile.

The chart owns one Deployment, ClusterIP Service, and ServiceAccount per Helm release.
The environment directory owns its Namespace manifest and values. The namespace is
created separately before Helm installation, avoiding conflicting namespace ownership.

The namespace enforces Kubernetes Restricted Pod Security. The workload adds resource
requests/limits and a bounded memory-backed /tmp. Token mounting is disabled because
the API never calls Kubernetes. RollingUpdate uses maxUnavailable=0 and maxSurge=1,
so a ready replacement should exist before an old replica is removed.

A startup probe allows a bounded initialization window. Readiness controls Service
traffic eligibility. Liveness can restart an unresponsive container. They use /health
because this API has no external dependencies. Future dependency readiness belongs
in a distinct endpoint rather than making liveness depend on external services.

Only repository/digest/pull policy, replicas, resources, Service port, environment,
source revision, and imagePullSecret names are configurable. Security settings are
fixed chart defaults, reducing opportunities to disable them accidentally. The JSON
schema rejects a tag in the digest field, an empty digest, and zero replicas.

Chart inputs are declarative desired state. Helm currently applies them from the
workstation; it does not continually repair drift. Argo CD will take ownership of
continuous reconciliation when Phase 4 is explicitly approved. CI validates templates
and schemas only; it never deploys application resources with kubectl.

A local native-image override is generated outside this repository. Its manifest
digest is resolved from Kind's containerd image store and its digest alias refers
to that actual local manifest. It is not substituted under the published GHCR digest.
