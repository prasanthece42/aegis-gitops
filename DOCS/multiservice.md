# Managed application stack validation

`validate-stacks.yml` adds the `stack-chart` check for DEV/STAGING/PROD branch PRs.
It renders managed multi-service application pointers with the exact versioned
`charts/multi-service` family and runs strict Kubernetes schema validation. It does
not connect to Kubernetes or execute application code. With no stack applications,
it passes without changing the existing sample or single-service chart workflow.

Before enabling multi-service delivery, review/install this workflow and require
`stack-chart` on the protected environment branches. The existing delivery-request
and delivery-policy workflows also need reviewed immutable pins to the new platform
helpers. No branch protections, helper pins or live deployments are changed by this
source candidate.

Application bootstrap copies the exact reviewed chart bytes into GitOps and binds
the namespace, resource/storage budget and Argo project. The platform worker
independently recreates each delivery plan from its signed request, current catalog
and complete release receipt. Native chart validation is an additional check, not
deployment authorization. Source and installed-state activation are separate.
