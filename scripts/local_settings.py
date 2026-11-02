import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lead_search

ROOT = lead_search.ROOT
FILE_NAME = "config.local.yaml"
STORED = {
    "outreach": ["sender_name", "portfolio_links", "message_rules", "follow_up_days"],
    "brief": ["default_language", "output_dir"],
}


class LocalSettingsError(Exception):
    pass


def path(root=None):
    return Path(root or ROOT) / FILE_NAME


def _yaml(file):
    if not file.exists():
        return {}
    try:
        return yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise LocalSettingsError("{} could not be read: {}".format(file.name, error))


def _link(item):
    if isinstance(item, dict):
        return {"url": str(item.get("url") or ""), "what": str(item.get("what") or "")}
    return {"url": str(item or ""), "what": ""}


def view(settings):
    outreach, brief = settings["outreach"], settings["brief"]
    return {
        "sender_name": outreach.get("sender_name") or "",
        "portfolio_links": [_link(item) for item in outreach.get("portfolio_links") or []],
        "message_rules": [str(rule) for rule in outreach.get("message_rules") or []],
        "follow_up_days": outreach["follow_up_days"],
        "default_language": brief.get("default_language") or "",
        "output_dir": brief.get("output_dir") or "",
    }


def _text(value, longest, label, required=False):
    if not isinstance(value, str):
        raise LocalSettingsError("{} has to be text.".format(label))
    value = value.strip()
    if required and not value:
        raise LocalSettingsError("{} cannot be empty.".format(label))
    if len(value) > longest:
        raise LocalSettingsError("{} can be at most {} characters.".format(label, longest))
    return value


def _whole(value, low, high, label):
    if isinstance(value, bool):
        raise LocalSettingsError("{} has to be a whole number.".format(label))
    try:
        number = int(str(value).strip())
    except ValueError:
        raise LocalSettingsError("{} has to be a whole number, not {}.".format(label, value))
    if not low <= number <= high:
        raise LocalSettingsError("{} has to be between {} and {}, not {}.".format(label, low, high, number))
    return number


def _portfolio(value):
    if not isinstance(value, list):
        raise LocalSettingsError("The portfolio links have to be a list.")
    links = []
    for number, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise LocalSettingsError("Portfolio link {} has to have an address and a description.".format(number))
        url = _text(item.get("url", ""), 300, "Portfolio link {}".format(number))
        what = _text(item.get("what", ""), 120, "What portfolio link {} was built for".format(number))
        if not url:
            if what:
                raise LocalSettingsError("Portfolio link {} has a description but no address.".format(number))
            continue
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or "." not in parsed.netloc:
            raise LocalSettingsError("Portfolio link {} has to be a full address starting with https://, not {}.".format(number, url))
        links.append({"url": url, "what": what})
    return links


def _rules(value):
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, list):
        raise LocalSettingsError("The message rules have to be a list.")
    rules = [_text(rule, 300, "Message rule {}".format(number)) for number, rule in enumerate(value, start=1)]
    return [rule for rule in rules if rule]


def _folder(value, current):
    folder = _text(value, 300, "The folder for the sites")
    if folder and folder != current and not Path(folder).expanduser().is_dir():
        raise LocalSettingsError(
            "The folder {} does not exist. Create it first, or leave the field empty for the Desktop.".format(folder)
        )
    return folder


def clean(payload, current):
    if not isinstance(payload, dict):
        raise LocalSettingsError("Your details have to come as named fields.")
    result = dict(current)
    if "sender_name" in payload:
        result["sender_name"] = _text(payload["sender_name"], 100, "Your name")
    if "portfolio_links" in payload:
        result["portfolio_links"] = _portfolio(payload["portfolio_links"])
    if "message_rules" in payload:
        result["message_rules"] = _rules(payload["message_rules"])
    if "follow_up_days" in payload:
        result["follow_up_days"] = _whole(payload["follow_up_days"], 1, 90, "Follow up after")
    if "default_language" in payload:
        result["default_language"] = _text(payload["default_language"], 40, "The default site language", required=True)
    if "output_dir" in payload:
        result["output_dir"] = _folder(payload["output_dir"], current.get("output_dir", ""))
    return result


def write(cleaned, root=None):
    public = _yaml(Path(root or ROOT) / "config.yaml")
    stored = _yaml(path(root))
    for section, keys in STORED.items():
        mine = stored.get(section) if isinstance(stored.get(section), dict) else {}
        for key in keys:
            if key in mine or cleaned[key] != (public.get(section) or {}).get(key):
                mine[key] = cleaned[key]
        if mine:
            stored[section] = mine
    try:
        path(root).write_text(yaml.safe_dump(stored, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    except OSError as error:
        raise LocalSettingsError("{} could not be saved: {}".format(FILE_NAME, error))
    return stored


def save(payload, settings=None, root=None):
    settings = settings or lead_search.load_settings()
    cleaned = clean(payload, view(settings))
    write(cleaned, root)
    return cleaned
