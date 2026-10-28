"""Use public release evidence and repo-scoped tokens to propose verified promotions."""

import argparse
import base64
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import yaml

POLICY = json.loads(Path("policies/release.json").read_text())
REPO = POLICY["gitops_repository"]
SOURCE = POLICY["source_repository"]
BRANCHES = POLICY["branches"]


def api(endpoint, method="GET", payload=None):
    command = ["gh", "api", endpoint, "--method", method]
    if payload is not None:
        command += ["--input", "-"]
    output = subprocess.check_output(
        command,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
    )
    return json.loads(output) if output.strip() else None


def content(path, ref, repo=REPO):
    result = api(f"repos/{repo}/contents/{path}?ref={quote(ref, safe='')}")
    return base64.b64decode(result["content"]).decode()


def verified_release(tag):
    if not re.fullmatch(r"release-[0-9]+-[0-9]+", tag):
        raise ValueError("Expected a versioned release tag")
    release = api(f"repos/{SOURCE}/releases/tags/{tag}")
    if (
        release["draft"]
        or release["prerelease"]
        or release["author"]["login"] != "github-actions[bot]"
    ):
        raise ValueError("Release must be published by the source workflow")
    asset = next(a for a in release["assets"] if a["name"] == "release.json")
    raw = subprocess.check_output(
        [
            "gh",
            "api",
            f"repos/{SOURCE}/releases/assets/{asset['id']}",
            "-H",
            "Accept: application/octet-stream",
        ]
    )
    receipt = json.loads(raw)
    validate_receipt(receipt, tag)
    run = api(f"repos/{SOURCE}/actions/runs/{receipt['run_id']}")
    if (
        run["status"] != "completed"
        or run["conclusion"] != "success"
        or run["head_branch"] != "main"
        or run["head_sha"] != receipt["source_commit"]
        or run["path"] != ".github/workflows/release.yml"
    ):
        raise ValueError("Source release workflow has not successfully completed on main")
    return receipt


def validate_receipt(receipt, tag):
    if receipt.get("schema_version") != 2 or receipt.get("release_tag") != tag:
        raise ValueError("Unsupported release evidence")
    if receipt.get("source_repository") != SOURCE:
        raise ValueError("Unexpected source repository")
    if not re.fullmatch(r"[0-9a-f]{40}", receipt.get("source_commit", "")):
        raise ValueError("Invalid source SHA")
    if not re.fullmatch(
        re.escape("ghcr.io/" + SOURCE) + r"@sha256:[0-9a-f]{64}", receipt.get("image", "")
    ):
        raise ValueError("Expected an immutable image in the approved registry repository")
    if set(receipt.get("platforms", {})) != {"linux/amd64", "linux/arm64"}:
        raise ValueError("Both validated image platforms are required")
    for platform, child in receipt["platforms"].items():
        if child.get("platform") != platform or child.get("digest_pull_smoke_test") != "passed":
            raise ValueError("An image platform was not validated")
        if child.get("source_commit") != receipt["source_commit"]:
            raise ValueError("Platform source mismatch")


def validate_health(statuses, environment, image, now=None):
    now = now or datetime.now(UTC)
    context = "aegis/" + environment + "-health"
    relevant = [s for s in statuses if s["context"] == context]
    if not relevant:
        raise ValueError("Missing prior-environment health evidence")
    latest = max(relevant, key=lambda s: s["created_at"])
    when = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))
    if latest["state"] != "success" or latest["creator"]["login"] not in POLICY["health_observers"]:
        raise ValueError("Health must be successful and recorded by an allowlisted operator")
    if latest["description"] != "Healthy " + image:
        raise ValueError("Health evidence describes another image")
    if now - when > timedelta(hours=POLICY["health_max_age_hours"]) or when > now + timedelta(
        minutes=5
    ):
        raise ValueError("Expired or invalid health evidence")


def validate_review(reviews, head_sha, author):
    latest = {}
    for review in reviews:
        login = review["user"]["login"]
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[login] = review
    approved = [
        r
        for login, r in latest.items()
        if login in POLICY["production_reviewers"]
        and login != author
        and r["user"].get("type") != "Bot"
        and r["state"] == "APPROVED"
        and r["commit_id"] == head_sha
    ]
    if not approved:
        raise ValueError(
            "Production requires an independent allowed human approval at the current PR head"
        )


def cache_at(receipt):
    statuses = api(f"repos/{SOURCE}/commits/{receipt['source_commit']}/statuses?per_page=100")
    validate_health(statuses, "kind-cache", receipt["image"])


def health_at(environment, revision, image):
    statuses = api(f"repos/{REPO}/commits/{revision}/statuses?per_page=100")
    validate_health(statuses, environment, image)


def pointer_for(environment, ref):
    return json.loads(content(f"environments/{environment}/release.json", ref))


def verify_pointer(environment, ref):
    pointer = pointer_for(environment, ref)
    receipt = verified_release(pointer["release_tag"])
    values = yaml.safe_load(content(f"environments/{environment}/values.yaml", ref))
    image = values["image"]["repository"] + "@" + values["image"]["digest"]
    if image != receipt["image"] or values["sourceCommit"] != receipt["source_commit"]:
        raise ValueError("Environment values do not match validated source release")
    if pointer["image"] != image or pointer["source_commit"] != receipt["source_commit"]:
        raise ValueError("Release pointer does not match environment")
    catalog = json.loads(content(f"releases/catalog/{pointer['release_tag']}.json", ref))
    if catalog != receipt:
        raise ValueError("Committed catalog differs from source evidence")
    cache_at(receipt)
    if environment != "dev":
        prior = "dev" if environment == "staging" else "staging"
        origin = pointer.get("origin") or {}
        if origin.get("environment") != prior or not re.fullmatch(
            r"[0-9a-f]{40}", origin.get("git_revision", "")
        ):
            raise ValueError("Promotion requires a prior-environment revision")
        previous = pointer_for(prior, origin["git_revision"])
        if previous["image"] != image or previous["release_tag"] != pointer["release_tag"]:
            raise ValueError("Promotion must preserve the previously validated digest")
        health_at(prior, origin["git_revision"], image)
    return pointer, receipt


def verify_pr(number, expected_sha):
    pr = api(f"repos/{REPO}/pulls/{number}")
    if pr["head"]["sha"] != expected_sha:
        raise ValueError("PR head changed during validation")
    environment = next(
        (env for env, branch in BRANCHES.items() if branch == pr["base"]["ref"]), None
    )
    delegated = {
        "platform-system": ("platform-services/aegis-portal/", "aegis/platform-service-policy"),
        "platform-observability": (
            "platform-services/aegis-observability/",
            "aegis/observability-policy",
        ),
    }.get(pr["base"]["ref"])
    if environment is None and delegated is None:
        raise ValueError("Unsupported promotion target branch")
    files = []
    page = 1
    while True:
        batch = api(f"repos/{REPO}/pulls/{number}/files?per_page=100&page={page}")
        files += batch
        if len(batch) < 100:
            break
        page += 1
    if len(files) != pr["changed_files"]:
        raise ValueError("Incomplete PR diff; refusing to validate")
    if delegated is not None:
        prefix, context = delegated
        if (
            not files
            or len(files) > 100
            or any(
                not file["filename"].startswith(prefix)
                or file["status"] not in {"added", "modified"}
                or "previous_filename" in file
                for file in files
            )
        ):
            raise ValueError(
                "Operator-owned PR changes paths outside its dedicated admission scope"
            )
        # This legacy gate only routes scope. The protected branch still requires
        # the dedicated trusted manifest check and independent human approval.
        print("PASS: operator-owned scope; dedicated admission still required:", context)
        return
    env_files = [f["filename"] for f in files if f["filename"].startswith("environments/")]
    allowed = {
        f"environments/{environment}/values.yaml",
        f"environments/{environment}/release.json",
    }
    if any(path not in allowed for path in env_files):
        raise ValueError("A release PR may change only its target environment")
    if env_files:
        verify_pointer(environment, expected_sha)
    if environment == "prod":
        reviews = []
        page = 1
        while True:
            batch = api(f"repos/{REPO}/pulls/{number}/reviews?per_page=100&page={page}")
            reviews += batch
            if len(batch) < 100:
                break
            page += 1
        validate_review(reviews, expected_sha, pr["user"]["login"])
    print("PASS: promotion policy for", environment, "PR", number)


def propose(environment, release_tag=None):
    base = BRANCHES[environment]
    base_sha = api(f"repos/{REPO}/git/ref/heads/{base}")["object"]["sha"]
    origin = None
    if environment == "dev":
        if not release_tag:
            release_tag = api(f"repos/{SOURCE}/releases/latest")["tag_name"]
        receipt = verified_release(release_tag)
    else:
        prior = "dev" if environment == "staging" else "staging"
        source_sha = api(f"repos/{REPO}/git/ref/heads/{BRANCHES[prior]}")["object"]["sha"]
        pointer, receipt = verify_pointer(prior, source_sha)
        health_at(prior, source_sha, pointer["image"])
        origin = {"environment": prior, "git_revision": source_sha}
    cache_at(receipt)
    values = yaml.safe_load(content(f"environments/{environment}/values.yaml", base_sha))
    if values["image"]["repository"] + "@" + values["image"]["digest"] == receipt["image"]:
        print("No proposal needed: environment already references", receipt["image"])
        return
    pointer = {
        "release_tag": receipt["release_tag"],
        "image": receipt["image"],
        "source_commit": receipt["source_commit"],
        "origin": origin,
    }
    branch = "release-" + environment + "-" + receipt["release_tag"]
    existing = api(f"repos/{REPO}/pulls?state=open&base={base}&head=prasanthece42:{branch}")
    if existing:
        number = existing[0]["number"]
    else:
        values["image"]["repository"], values["image"]["digest"] = receipt["image"].split("@")
        values["sourceCommit"] = receipt["source_commit"]
        tree = api(f"repos/{REPO}/git/commits/{base_sha}")["tree"]["sha"]
        entries = {
            f"environments/{environment}/values.yaml": yaml.safe_dump(values, sort_keys=False),
            f"environments/{environment}/release.json": json.dumps(pointer, indent=2) + "\n",
            f"releases/catalog/{receipt['release_tag']}.json": json.dumps(receipt, indent=2) + "\n",
        }
        new_tree = api(
            f"repos/{REPO}/git/trees",
            "POST",
            {
                "base_tree": tree,
                "tree": [
                    {"path": path, "mode": "100644", "type": "blob", "content": data}
                    for path, data in entries.items()
                ],
            },
        )
        commit = api(
            f"repos/{REPO}/git/commits",
            "POST",
            {
                "message": f"Promote {receipt['release_tag']} to {environment}",
                "tree": new_tree["sha"],
                "parents": [base_sha],
            },
        )
        api(f"repos/{REPO}/git/refs", "POST", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
        pr = api(
            f"repos/{REPO}/pulls",
            "POST",
            {
                "head": branch,
                "base": base,
                "title": f"Promote {receipt['release_tag']} to {environment.upper()}",
                "body": f"Validated image: `{receipt['image']}`\n\n"
                f"Source: `{receipt['source_commit']}`\n\n"
                "Reuses the tested digest; does not rebuild. "
                "Production requires fresh human approval.",
            },
        )
        number = pr["number"]
    subprocess.run(
        [
            "gh",
            "workflow",
            "run",
            "validate.yml",
            "--repo",
            REPO,
            "--ref",
            branch,
            "-f",
            f"pr_number={number}",
        ],
        check=True,
    )
    if environment == "dev":
        subprocess.run(
            ["gh", "pr", "merge", str(number), "--repo", REPO, "--auto", "--squash"], check=True
        )
    print(f"PR ready for checks: https://github.com/{REPO}/pull/{number}")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    proposal = commands.add_parser("propose")
    proposal.add_argument("environment", choices=BRANCHES)
    proposal.add_argument("--release-tag")
    check = commands.add_parser("check-pr")
    check.add_argument("number", type=int)
    check.add_argument("head_sha")
    args = parser.parse_args()
    if args.command == "propose":
        propose(args.environment, args.release_tag)
    else:
        verify_pr(args.number, args.head_sha)


if __name__ == "__main__":
    main()
