import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_site
import lead_search
import lead_store

ROOT = lead_search.ROOT
RECORD_FILE = "deploy.json"
ASSETS_FOLDER = "assets"
REWRITTEN_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".xml", ".txt", ".webmanifest"}
LEFT_OUT_FILES = {".DS_Store", "Thumbs.db", "assets.json", "sources.json"}
LEFT_OUT_FOLDERS = {"node_modules", ".astro", ".git", ".vercel"}
FINISHED_STATES = {"READY", "ERROR", "CANCELED"}


class DeployError(Exception):
    pass


def token():
    load_dotenv(ROOT / ".env")
    key = (os.getenv("VERCEL_TOKEN") or "").strip()
    if not key:
        raise DeployError("VERCEL_TOKEN is empty in .env. SETUP.md, section 5, shows where to get one.")
    return key


def has_token():
    try:
        token()
    except DeployError:
        return False
    return True


def _scope():
    load_dotenv(ROOT / ".env")
    team = (os.getenv("VERCEL_TEAM_ID") or "").strip()
    return {"teamId": team} if team else {}


def read_record(folder):
    path = Path(folder).expanduser() / RECORD_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def project_name(folder, wanted=""):
    earlier = read_record(folder).get("project")
    if earlier:
        return earlier
    name = lead_store.to_slug(wanted or Path(folder).expanduser().name, "site")[:90].strip("-")
    return name or "site"


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


def _headers(key, extra=None):
    headers = {"Authorization": "Bearer {}".format(key)}
    headers.update(extra or {})
    return headers


def _check(response, doing):
    if response.status_code in (401, 403):
        raise DeployError("Vercel refused the token while {}. Check VERCEL_TOKEN, and VERCEL_TEAM_ID if the projects belong to a team.".format(doing))
    if response.status_code == 429:
        raise DeployError("Vercel's rate limit was reached while {}. Wait a few minutes and run it again.".format(doing))
    if response.status_code >= 400:
        try:
            message = (response.json().get("error") or {}).get("message") or response.text
        except ValueError:
            message = response.text
        raise DeployError("Vercel answered {} while {}: {}".format(response.status_code, doing, str(message)[:300]))


def upload(files, key, options):
    entries = []
    for name, data in sorted(files.items()):
        digest = hashlib.sha1(data).hexdigest()
        try:
            response = requests.post(
                options["api"] + "/v2/files",
                params=_scope(),
                headers=_headers(key, {
                    "Content-Type": "application/octet-stream",
                    "x-vercel-digest": digest,
                    "Content-Length": str(len(data)),
                }),
                data=data,
                timeout=options["upload_timeout_seconds"],
            )
        except requests.RequestException as error:
            raise DeployError("Uploading {} to Vercel failed: {}".format(name, error))
        _check(response, "uploading {}".format(name))
        entries.append({"file": name, "sha": digest, "size": len(data)})
    return entries


def _create(name, entries, key, options):
    body = {
        "name": name,
        "files": entries,
        "target": "production",
        "projectSettings": {
            "framework": None,
            "buildCommand": None,
            "installCommand": None,
            "devCommand": None,
            "outputDirectory": None,
        },
    }
    try:
        response = requests.post(
            options["api"] + "/v13/deployments",
            params=dict(_scope(), skipAutoDetectionConfirmation="1"),
            headers=_headers(key),
            json=body,
            timeout=60,
        )
    except requests.RequestException as error:
        raise DeployError("Creating the Vercel deployment failed: {}".format(error))
    _check(response, "creating the deployment")
    return response.json()


def _wait_until_ready(deployment, key, options):
    deadline = time.monotonic() + options["ready_timeout_seconds"]
    while deployment.get("readyState") not in FINISHED_STATES:
        if time.monotonic() > deadline:
            raise DeployError("The deployment was not ready after {} seconds.".format(options["ready_timeout_seconds"]))
        time.sleep(options["poll_seconds"])
        try:
            response = requests.get(
                "{}/v13/deployments/{}".format(options["api"], deployment["id"]),
                params=_scope(),
                headers=_headers(key),
                timeout=30,
            )
        except requests.RequestException as error:
            raise DeployError("Asking Vercel about the deployment failed: {}".format(error))
        _check(response, "checking the deployment")
        deployment = response.json()
    if deployment.get("readyState") != "READY":
        raise DeployError(
            "The deployment ended as {}: {}".format(deployment.get("readyState"), deployment.get("errorMessage") or "no reason given")
        )
    return deployment


def production_address(deployment, name):
    aliases = [alias for alias in deployment.get("alias") or [] if alias.endswith(".vercel.app")]
    preferred = "{}.vercel.app".format(name)
    if preferred in aliases:
        return preferred
    candidates = sorted((alias for alias in aliases if alias.startswith(name)), key=len)
    if candidates:
        return candidates[0]
    return deployment.get("url") or ""


def is_public(address):
    try:
        response = requests.get("https://" + address, timeout=20, allow_redirects=False)
    except requests.RequestException:
        return False
    return response.status_code == 200


def deploy(folder, settings, wanted_name=""):
    folder = Path(folder).expanduser()
    options = settings["deploy"]
    key = token()
    name = project_name(folder, wanted_name)
    files = bundle(folder)
    entries = upload(files, key, options)
    deployment = _wait_until_ready(_create(name, entries, key, options), key, options)
    address = production_address(deployment, name)
    record = {
        "project": name,
        "url": "https://{}".format(address) if address else "",
        "deployment_url": "https://{}".format(deployment["url"]) if deployment.get("url") else "",
        "public": bool(address) and is_public(address),
        "files": len(entries),
        "deployed_at": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / RECORD_FILE).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Publishes a built site on Vercel and prints its public address.")
    parser.add_argument("folder", help="The business folder that holds brief.md and site/")
    parser.add_argument("--name", default="", help="Vercel project name, used on the first deploy only")
    arguments = parser.parse_args()

    try:
        record = deploy(arguments.folder, lead_search.load_settings(), arguments.name)
    except DeployError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    print("\nPublished {} files as Vercel project {}.".format(record["files"], record["project"]))
    print("Address: {}".format(record["url"]))
    if not record["public"]:
        print(
            "\nWARNING: that address does not open without a Vercel login. In the project's settings on "
            "vercel.com, under Deployment Protection, set Vercel Authentication to Standard Protection or "
            "turn it off, then run this again."
        )
        raise SystemExit(2)
    print()


if __name__ == "__main__":
    main()
