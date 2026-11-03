import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_site
import lead_search
import lead_store

ROOT = lead_search.ROOT
HOST = "Cloudflare Pages"
RECORD_FILE = "deploy.json"
ASSETS_FOLDER = "assets"
PROJECT_NAME_LENGTH = 58
REWRITTEN_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".xml", ".txt", ".webmanifest"}
LEFT_OUT_FILES = {".DS_Store", "Thumbs.db", "assets.json", "sources.json"}
LEFT_OUT_FOLDERS = {"node_modules", ".astro", ".git", ".wrangler"}
FAILED_STATUSES = {"failure", "canceled"}


class DeployError(Exception):
    pass


def _environment(name):
    load_dotenv(ROOT / ".env")
    return (os.getenv(name) or "").strip()


def token():
    key = _environment("CLOUDFLARE_API_TOKEN")
    if not key:
        raise DeployError("CLOUDFLARE_API_TOKEN is empty in .env. SETUP.md, section 5, shows where to get one.")
    return key


def has_token():
    try:
        token()
    except DeployError:
        return False
    return True


def read_record(folder):
    path = Path(folder).expanduser() / RECORD_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def project_name(folder, wanted=""):
    name = lead_store.to_slug(wanted or Path(folder).expanduser().name, "site")[:PROJECT_NAME_LENGTH].strip("-")
    return name or "site"


def shared_project(options):
    return lead_store.to_slug(options.get("shared_project") or "", "")[:PROJECT_NAME_LENGTH].strip("-")


def branch_name(text, length):
    words = lead_store.to_slug(text, "site").split("-")
    kept = []
    for word in words:
        if kept and len("-".join(kept + [word])) > length:
            break
        kept.append(word)
    return "-".join(kept)[:length].strip("-") or "site"


def numbered(name, number, length):
    suffix = "-{}".format(number)
    return name[:length - len(suffix)].strip("-") + suffix


def destination(folder, options, wanted="", own=False):
    earlier = read_record(folder)
    if earlier.get("host") == HOST and earlier.get("project") and not (own and earlier.get("branch")):
        return earlier["project"], earlier.get("branch") or "", True
    shared = shared_project(options)
    if shared and not own:
        return shared, branch_name(wanted or Path(folder).expanduser().name, options["branch_length"]), False
    return project_name(folder, wanted or earlier.get("branch") or ""), "", False


def _kept(path, root):
    parts = path.relative_to(root).parts
    return path.is_file() and path.name not in LEFT_OUT_FILES and not LEFT_OUT_FOLDERS.intersection(parts)


def bundle(folder):
    folder = Path(folder).expanduser()
    page = check_site.entry_page(folder)
    if page is None:
        raise DeployError("{} has no site/index.html to publish.".format(folder))

    site_root = page.parent
    files = {}
    for path in sorted(site_root.rglob("*")):
        if not _kept(path, site_root):
            continue
        data = path.read_bytes()
        if path.suffix.lower() in REWRITTEN_SUFFIXES:
            data = data.replace(b"../" + ASSETS_FOLDER.encode() + b"/", ASSETS_FOLDER.encode() + b"/")
        files[path.relative_to(site_root).as_posix()] = data

    assets = folder / ASSETS_FOLDER
    if assets.is_dir():
        for path in sorted(assets.rglob("*")):
            if _kept(path, assets):
                files["{}/{}".format(ASSETS_FOLDER, path.relative_to(assets).as_posix())] = path.read_bytes()
    return files


def asset_hash(name, data):
    extension = Path(name).suffix.lstrip(".").encode()
    return hashlib.sha256(base64.b64encode(data) + extension).hexdigest()[:32]


def _send(method, url, doing, **arguments):
    try:
        return requests.request(method, url, **arguments)
    except requests.RequestException as error:
        raise DeployError("{} failed: {}".format(doing[0].upper() + doing[1:], error))


def _result(response, doing):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code in (401, 403):
        raise DeployError(
            "Cloudflare refused the token while {}. It needs the permission Account, Cloudflare Pages, Edit.".format(doing)
        )
    if response.status_code == 429:
        raise DeployError("Cloudflare's rate limit was reached while {}. Wait a few minutes and run it again.".format(doing))
    if response.status_code >= 400 or payload.get("success") is False:
        reasons = "; ".join(str(error.get("message", "")) for error in payload.get("errors") or []) or response.text
        raise DeployError("Cloudflare answered {} while {}: {}".format(response.status_code, doing, reasons[:300]))
    return payload.get("result")


def _api(method, path, key, options, doing, **arguments):
    arguments.setdefault("timeout", 60)
    arguments["headers"] = dict(arguments.get("headers") or {}, Authorization="Bearer {}".format(key))
    return _result(_send(method, options["api"] + path, doing, **arguments), doing)


def account_id(key, options):
    configured = _environment("CLOUDFLARE_ACCOUNT_ID")
    if configured:
        return configured
    accounts = _api("GET", "/accounts", key, options, "listing your accounts") or []
    if len(accounts) == 1:
        return accounts[0]["id"]
    if not accounts:
        raise DeployError(
            "The token is valid but cannot see which Cloudflare account it belongs to, as a token made for Pages "
            "alone cannot. Copy the Account ID from the right side of Workers & Pages in the dashboard into "
            "CLOUDFLARE_ACCOUNT_ID in .env."
        )
    raise DeployError(
        "The token sees {} Cloudflare accounts, so it is not clear which to publish under. Put that account's ID "
        "into CLOUDFLARE_ACCOUNT_ID in .env.".format(len(accounts))
    )


def find_project(account, name, key, options):
    path = "/accounts/{}/pages/projects/{}".format(account, name)
    response = _send(
        "GET", options["api"] + path, "looking up the project", headers={"Authorization": "Bearer {}".format(key)}, timeout=30
    )
    if response.status_code == 404:
        return None
    return _result(response, "looking up the project")


def create_project(account, name, key, options):
    return _api(
        "POST",
        "/accounts/{}/pages/projects".format(account),
        key,
        options,
        "creating the project",
        json={"name": name, "production_branch": options["production_branch"]},
    )


def free_project(account, name, key, options):
    for number in range(2, options["name_attempts"] + 1):
        candidate = numbered(name, number, PROJECT_NAME_LENGTH)
        if find_project(account, candidate, key, options) is None:
            return candidate
    raise DeployError(
        "Projects {} to {} already exist and belong to other sites. Publish it with --name and a different "
        "name.".format(name, numbered(name, options["name_attempts"], PROJECT_NAME_LENGTH))
    )


def is_taken(address):
    try:
        response = requests.get("https://" + address, timeout=20, allow_redirects=False)
    except requests.RequestException:
        return False
    return response.status_code < 400


def free_branch(branch, subdomain, options):
    length = options["branch_length"]
    for number in range(1, options["name_attempts"] + 1):
        candidate = branch if number == 1 else numbered(branch, number, length)
        if candidate != options["production_branch"] and not is_taken("{}.{}".format(candidate, subdomain)):
            return candidate
    raise DeployError(
        "Every address tried for {} in the shared project is already in use, up to {}. Publish it with --name "
        "and a different name.".format(branch, numbered(branch, options["name_attempts"], length))
    )


def upload(files, account, name, key, options):
    upload_token = _api(
        "GET", "/accounts/{}/pages/projects/{}/upload-token".format(account, name), key, options, "asking for an upload token"
    )["jwt"]
    manifest = {"/" + path: asset_hash(path, data) for path, data in files.items()}
    contents = {asset_hash(path, data): (path, data) for path, data in files.items()}
    missing = _api(
        "POST", "/pages/assets/check-missing", upload_token, options, "checking which files Cloudflare already has",
        json={"hashes": sorted(contents)},
    ) or []

    batch, size = [], 0
    for digest in missing:
        path, data = contents[digest]
        encoded = base64.b64encode(data).decode()
        if batch and size + len(encoded) > options["upload_batch_bytes"]:
            _upload_batch(batch, upload_token, options)
            batch, size = [], 0
        batch.append({
            "key": digest,
            "value": encoded,
            "metadata": {"contentType": mimetypes.guess_type(path)[0] or "application/octet-stream"},
            "base64": True,
        })
        size += len(encoded)
    if batch:
        _upload_batch(batch, upload_token, options)

    _api(
        "POST", "/pages/assets/upsert-hashes", upload_token, options, "confirming the upload",
        json={"hashes": sorted(contents)},
    )
    return manifest, len(missing)


def _upload_batch(batch, upload_token, options):
    _api(
        "POST", "/pages/assets/upload", upload_token, options, "uploading {} files".format(len(batch)),
        json=batch, timeout=options["upload_timeout_seconds"],
    )


def _wait_until_live(account, name, deployment, key, options):
    deadline = time.monotonic() + options["ready_timeout_seconds"]
    while True:
        stage = deployment.get("latest_stage") or {}
        if stage.get("status") in FAILED_STATUSES:
            raise DeployError("The deployment stopped at {}: {}.".format(stage.get("name"), stage.get("status")))
        if stage.get("name") == "deploy" and stage.get("status") == "success":
            return deployment
        if time.monotonic() > deadline:
            raise DeployError("The deployment was not live after {} seconds.".format(options["ready_timeout_seconds"]))
        time.sleep(options["poll_seconds"])
        deployment = _api(
            "GET", "/accounts/{}/pages/projects/{}/deployments/{}".format(account, name, deployment["id"]),
            key, options, "checking the deployment",
        )


def _host(address):
    return urlparse(address if "//" in address else "https://" + address).netloc


def _unique(addresses):
    ordered = []
    for address in addresses:
        if address and address not in ordered:
            ordered.append(address)
    return ordered


def stable_addresses(project):
    return _unique([project.get("subdomain") or ""] + list(project.get("domains") or []))


def deployment_addresses(deployment):
    return _unique([_host(alias) for alias in deployment.get("aliases") or []] + [_host(deployment.get("url") or "")])


def is_public(address):
    try:
        response = requests.get("https://" + address, timeout=20, allow_redirects=False)
    except requests.RequestException:
        return False
    return response.status_code == 200


def first_public(addresses, options):
    deadline = time.monotonic() + options["public_wait_seconds"]
    while addresses:
        for address in addresses:
            if is_public(address):
                return address
        if time.monotonic() > deadline:
            return ""
        time.sleep(options["poll_seconds"])
    return ""


def deploy(folder, settings, wanted_name="", own=False):
    folder = Path(folder).expanduser()
    options = settings["deploy"]
    key = token()
    name, branch, known = destination(folder, options, wanted_name, own)
    files = bundle(folder)
    account = account_id(key, options)
    project = find_project(account, name, key, options)
    if project is not None and not known and not branch:
        name, project = free_project(account, name, key, options), None
    if project is None:
        project = create_project(account, name, key, options)
    elif branch and not known:
        branch = free_branch(branch, project["subdomain"], options)
    manifest, sent = upload(files, account, name, key, options)
    deployment = _api(
        "POST", "/accounts/{}/pages/projects/{}/deployments".format(account, name), key, options, "creating the deployment",
        files={"manifest": (None, json.dumps(manifest)), "branch": (None, branch or options["production_branch"])},
        timeout=options["upload_timeout_seconds"],
    )
    started = deployment_addresses(deployment)
    deployment = _wait_until_live(account, name, deployment, key, options)
    if branch:
        stable = ["{}.{}".format(branch, project["subdomain"])]
    else:
        stable = stable_addresses(find_project(account, name, key, options) or project)
    unique = [address for address in _unique(deployment_addresses(deployment) + started) if address not in stable]
    public = first_public(stable, options)
    fallback = "" if public else next((address for address in unique if is_public(address)), "")
    address = public or fallback or (stable + unique or [""])[0]
    record = {
        "host": HOST,
        "project": name,
        "branch": branch,
        "url": "https://{}".format(address) if address else "",
        "deployment_url": deployment.get("url") or "",
        "public": bool(public or fallback),
        "stable": bool(public),
        "files": len(files),
        "uploaded": sent,
        "deployed_at": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / RECORD_FILE).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Publishes a built site on Cloudflare Pages and prints its public address.")
    parser.add_argument("folder", help="The business folder that holds brief.md and site/")
    parser.add_argument("--name", default="", help="Name the address is made from, used on the first publish only")
    parser.add_argument(
        "--own", action="store_true",
        help="Move a demo out of the shared project into a project of its own, for a business that said yes",
    )
    arguments = parser.parse_args()

    settings = lead_search.load_settings()
    try:
        record = deploy(arguments.folder, settings, arguments.name, arguments.own)
    except DeployError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    if record["branch"]:
        print("\nPublished {} files ({} new) in the shared Cloudflare Pages project {}, as {}.".format(
            record["files"], record["uploaded"], record["project"], record["branch"]
        ))
    else:
        print("\nPublished {} files ({} new) as Cloudflare Pages project {}.".format(
            record["files"], record["uploaded"], record["project"]
        ))
    print("Address: {}".format(record["url"]))
    if record["public"] and not record["stable"]:
        print(
            "\nNOTE: the lasting address was not answering yet, so this is the address of this one deployment. "
            "It keeps working, but shows this version only. Publish again in a few minutes to get the address "
            "that follows every update."
        )
    if arguments.own and record["public"]:
        print(
            "\nTo put it on the business's own domain, open project {} under Workers & Pages in the Cloudflare "
            "dashboard and add the domain under Custom domains.".format(record["project"])
        )
    if not record["public"]:
        print(
            "\nWARNING: that address did not open within {} seconds. A new project's address can take a few "
            "minutes to appear, so run this again shortly.".format(settings["deploy"]["public_wait_seconds"])
        )
        raise SystemExit(2)
    print()


if __name__ == "__main__":
    main()
