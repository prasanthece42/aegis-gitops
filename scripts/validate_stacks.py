"""Render and schema-check managed stacks. Never contacts Kubernetes or executes app code."""

import json
import re
import subprocess
from pathlib import Path


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2:
        raise ValueError("Expected a bounded regular managed-app record")

    def distinct(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate managed configuration key")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=distinct)


def validate(root, reports):
    pointers = sorted((root / "applications").glob("*/environments/*/release.json"))
    if len(pointers) > 300:
        raise ValueError("Managed application inventory exceeds its review budget")
    count = 0
    for path in pointers:
        pointer = read(path)
        state = pointer["desired_state"]
        values = state["effective_values"]
        if "plan" not in values and "stackSha256" not in values:
            continue  # Existing single-service validation stays in its original workflow.
        app_id, environment, version = state["app_id"], state["environment"], state["chart_version"]
        if (
            not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", app_id)
            or len(app_id) > 40
            or environment not in {"dev", "staging", "prod"}
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
        ):
            raise ValueError("Invalid application/chart binding")
        if path != root / f"applications/{app_id}/environments/{environment}/release.json":
            raise ValueError("Stack pointer is outside its app/environment")
        values_path = path.with_name("values.yaml")
        if read(values_path) != values or state["namespace"] != f"aegis-{app_id}-{environment}":
            raise ValueError("Actual stack values differ from the desired-state pointer")
        chart = root / "charts/multi-service" / version
        if chart.is_symlink() or not chart.is_dir():
            raise ValueError("Reviewed multi-service chart is missing")
        reports.mkdir(parents=True, exist_ok=True)
        rendered = reports / f"{app_id}-{environment}.yaml"
        result = subprocess.run(
            [
                "helm",
                "template",
                app_id,
                str(chart),
                "--namespace",
                state["namespace"],
                "--kube-version",
                "1.35.0",
                "--values",
                str(values_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        rendered.write_text(result.stdout)
        subprocess.run(
            ["kubeconform", "-strict", "-summary", "-kubernetes-version", "1.35.0", str(rendered)],
            check=True,
        )
        count += 1
    return count


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(f"PASS: {validate(root, root / 'reports/stacks')} managed stack(s) schema-validated")
