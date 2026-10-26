from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from scripts.promotion import validate_health, validate_receipt, validate_review

SHA = "a" * 40
IMAGE = "ghcr.io/prasanthece42/aegis-cicd@sha256:" + "b" * 64
NOW = datetime(2026, 10, 25, 22, 0, tzinfo=UTC)
STATUS = {
    "context": "aegis/dev-health",
    "state": "success",
    "description": "Healthy " + IMAGE,
    "creator": {"login": "prasanthece42"},
    "created_at": NOW.isoformat(),
}
REVIEW = {"user": {"login": "prasanthece42", "type": "User"}, "state": "APPROVED", "commit_id": SHA}


def test_fresh_matching_operator_health_passes():
    validate_health([STATUS], "dev", IMAGE, NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "failure"),
        ("description", "Healthy other"),
        ("creator", {"login": "github-actions[bot]"}),
    ],
)
def test_wrong_or_untrusted_health_fails(field, value):
    status = deepcopy(STATUS)
    status[field] = value
    with pytest.raises(ValueError):
        validate_health([status], "dev", IMAGE, NOW)


def test_stale_health_fails():
    with pytest.raises(ValueError, match="Expired"):
        validate_health([STATUS], "dev", IMAGE, NOW + timedelta(hours=25))


def test_new_failure_supersedes_old_success():
    failed = dict(STATUS, state="failure", created_at=(NOW + timedelta(seconds=1)).isoformat())
    with pytest.raises(ValueError):
        validate_health([STATUS, failed], "dev", IMAGE, NOW + timedelta(seconds=2))


def test_independent_current_human_approval_passes():
    validate_review([REVIEW], SHA, "github-actions[bot]")


@pytest.mark.parametrize(
    "reviews,author",
    [
        ([], "github-actions[bot]"),
        ([REVIEW], "prasanthece42"),
        ([dict(REVIEW, commit_id="c" * 40)], "github-actions[bot]"),
        ([dict(REVIEW, user={"login": "prasanthece42", "type": "Bot"})], "github-actions[bot]"),
        ([REVIEW, dict(REVIEW, state="CHANGES_REQUESTED")], "github-actions[bot]"),
    ],
)
def test_missing_self_stale_bot_or_withdrawn_approval_fails(reviews, author):
    with pytest.raises(ValueError):
        validate_review(reviews, SHA, author)


def test_mutable_image_receipt_fails():
    with pytest.raises(ValueError):
        validate_receipt(
            {
                "schema_version": 2,
                "release_tag": "release-1-1",
                "source_repository": "prasanthece42/aegis-cicd",
                "source_commit": SHA,
                "image": "ghcr.io/prasanthece42/aegis-cicd:latest",
            },
            "release-1-1",
        )
