import json
from types import SimpleNamespace

import pytest

from scripts import validate_stacks


def records(root, stack=True):
    folder = root / "applications/commerce-demo/environments/dev"
    folder.mkdir(parents=True)
    values = {"image": {"digest": "sha256:" + "a" * 64}}
    if stack:
        values.update(plan=[], stackSha256="sha256:" + "b" * 64)
    state = {
        "app_id": "commerce-demo",
        "environment": "dev",
        "chart_version": "1.0.0",
        "namespace": "aegis-commerce-demo-dev",
        "effective_values": values,
    }
    pointer = folder / "release.json"
    pointer.write_text(json.dumps({"desired_state": state}))
    (folder / "values.yaml").write_text(json.dumps(values))
    (root / "charts/multi-service/1.0.0").mkdir(parents=True)
    return pointer


def test_complete_stack_uses_helm_and_strict_schema_validation(tmp_path, monkeypatch):
    records(tmp_path)
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="apiVersion: v1\nkind: Service\n")

    monkeypatch.setattr(validate_stacks.subprocess, "run", execute)
    assert validate_stacks.validate(tmp_path, tmp_path / "reports") == 1
    assert calls[0][0] == "helm"
    assert "charts/multi-service/1.0.0" in calls[0][3]
    assert calls[1][0:3] == ["kubeconform", "-strict", "-summary"]


def test_legacy_single_service_does_not_use_the_new_chart_path(tmp_path, monkeypatch):
    records(tmp_path, stack=False)
    monkeypatch.setattr(
        validate_stacks.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Unexpected stack rendering"),
    )
    assert validate_stacks.validate(tmp_path, tmp_path / "reports") == 0


@pytest.mark.parametrize("mutation", ["values", "namespace", "path"])
def test_changed_app_binding_fails_before_rendering(tmp_path, mutation, monkeypatch):
    pointer = records(tmp_path)
    if mutation == "values":
        pointer.with_name("values.yaml").write_text("{}")
    else:
        raw = json.loads(pointer.read_text())
        raw["desired_state"]["namespace" if mutation == "namespace" else "app_id"] = "another-app"
        pointer.write_text(json.dumps(raw))
    monkeypatch.setattr(
        validate_stacks.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Unexpected rendering"),
    )
    with pytest.raises(ValueError):
        validate_stacks.validate(tmp_path, tmp_path / "reports")
