#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports
for environment in dev staging prod; do
  values="environments/$environment/values.yaml"
  helm lint charts/sample-api --strict --values "$values"
  helm template sample-api charts/sample-api --namespace "aegis-$environment" \
    --kube-version 1.35.8 --values "$values" > "reports/$environment.yaml"
  kubeconform -strict -summary -kubernetes-version 1.35.0 \
    "environments/$environment/namespace.yaml" "reports/$environment.yaml"
done
for invalid in 'image.digest=latest' 'image.digest=' 'replicaCount=0'; do
  if helm template sample-api charts/sample-api --set "$invalid" > reports/negative-test.log 2>&1; then
    printf 'FAIL: invalid chart values accepted: %s\n' "$invalid" >&2
    exit 1
  fi
  printf 'PASS: chart rejected %s\n' "$invalid"
done
