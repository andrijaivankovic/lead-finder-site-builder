import argparse
import json
import random
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_brief
import check_site
import find_stock_photos
import lead_search
import lead_store
import outreach_log

ROOT = lead_search.ROOT
CODE = Path(__file__).resolve().parent.parent
COMMAND_FILE = "commands/autopilot.md"
MESSAGES_FILE = "outreach.md"
MESSAGE_HEADINGS = ["Email", "Viber or WhatsApp", "Instagram"]
CHECK_PROMPT = "Reply with the single word OK."
DESKTOP_COPIES = "Library/Application Support/Claude/claude-code"
POLL_SECONDS = 1.0

REGIONS = {
    "us": "United States",
    "english": "English-speaking countries",
    "europe": "Europe",
    "world": "Anywhere in the list",
}

STACKS = {
    "plain": {"name": "Plain HTML, CSS and JavaScript", "needs_a_build": False},
    "astro": {"name": "Astro, built to static files", "needs_a_build": True},
    "vite": {"name": "Vite, built to static files", "needs_a_build": True},
}

SITE_FLAGS = ["faq", "careers", "show_reviews", "animations", "ai_media"]
SEARCH_FLAGS = ["only_without_website", "require_phone"]
BUILDER_FIELDS = ["command", "model", "timeout_minutes"]
ACTIVE_STATES = {"searching", "building"}

UNATTENDED = """You are running unattended. The autopilot in the lead-finder browser page
started you, nobody reads this session while it runs, and nobody will answer a
question. Never ask one: wherever the instructions below would ask, take the
default they name.

`{{venv python}}` is `{python}` here. Only these work: reading any file, writing
files inside {output} and inside {scratch}, and running `{python} scripts/...`.
Everything else is refused, so do not try other commands. There is no browser
and no web access.
"""


class AutopilotError(Exception):
    pass


def settings_file(root=None):
    return lead_store.data_dir(root or ROOT) / "autopilot_settings.json"


def _read_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def options(settings=None, root=None):
    settings = settings or lead_search.load_settings()
    merged = json.loads(json.dumps(settings["autopilot"]))
    return lead_search.merge_settings(merged, _read_json(settings_file(root)))


def _whole(value, low, high, label):
    if isinstance(value, bool):
        raise AutopilotError("{} has to be a whole number.".format(label))
    try:
        number = int(str(value).strip())
    except ValueError:
        raise AutopilotError("{} has to be a whole number, not {}.".format(label, value))
    if not low <= number <= high:
        raise AutopilotError("{} has to be between {} and {}, not {}.".format(label, low, high, number))
    return number


def _flag(value, label):
    if not isinstance(value, bool):
        raise AutopilotError("{} has to be on or off.".format(label))
    return value


def _text(value, longest, label, required=False):
    if not isinstance(value, str):
        raise AutopilotError("{} has to be text.".format(label))
    value = value.strip()
    if required and not value:
        raise AutopilotError("{} cannot be empty.".format(label))
    if len(value) > longest:
        raise AutopilotError("{} can be at most {} characters.".format(label, longest))
    return value


def _trades(value):
    if not isinstance(value, list):
        raise AutopilotError("The trades have to be a list.")
    cleaned = []
    for item in value:
        trade = _text(item, 40, "A trade", required=True)
        if trade.lower() not in [known.lower() for known in cleaned]:
            cleaned.append(trade)
    if not cleaned:
        raise AutopilotError("Pick at least one trade for the random choice.")
    return cleaned


def clean(payload, current):
    payload = payload or {}
    result = json.loads(json.dumps(current))

    if "sites_per_run" in payload:
        result["sites_per_run"] = _whole(payload["sites_per_run"], 1, 10, "Sites per run")
    if "search_limit" in payload:
        result["search_limit"] = _whole(payload["search_limit"], 10, 500, "Businesses to look through")
    for key in SEARCH_FLAGS:
        if key in payload:
            result[key] = _flag(payload[key], key)
    if "cities_from" in payload:
        if payload["cities_from"] not in REGIONS:
            raise AutopilotError("Random cities come from one of: {}.".format(", ".join(REGIONS)))
        result["cities_from"] = payload["cities_from"]
    if "trades" in payload:
        result["trades"] = _trades(payload["trades"])

    site = payload.get("site") or {}
    for key in SITE_FLAGS:
        if key in site:
            result["site"][key] = _flag(site[key], key)
    if "language" in site:
        result["site"]["language"] = _text(site["language"], 40, "The site language", required=True)
    if "stack" in site:
        if site["stack"] not in STACKS:
            raise AutopilotError("The stack is one of: {}.".format(", ".join(STACKS)))
        result["site"]["stack"] = site["stack"]
    if "style" in site:
        result["site"]["style"] = _text(site["style"], 300, "The style note")

    builder = payload.get("builder") or {}
    if "command" in builder:
        result["builder"]["command"] = _text(builder["command"], 500, "The Claude Code command")
    if "model" in builder:
        result["builder"]["model"] = _text(builder["model"], 100, "The model")
    if "timeout_minutes" in builder:
        result["builder"]["timeout_minutes"] = _whole(builder["timeout_minutes"], 5, 240, "The time limit")

    return result


def save(payload, settings=None, root=None):
    cleaned = clean(payload, options(settings, root))
    stored = {
        "sites_per_run": cleaned["sites_per_run"],
        "search_limit": cleaned["search_limit"],
        "cities_from": cleaned["cities_from"],
        "trades": cleaned["trades"],
        "site": cleaned["site"],
        "builder": {key: cleaned["builder"][key] for key in BUILDER_FIELDS},
    }
    stored.update({key: cleaned[key] for key in SEARCH_FLAGS})
    _write_json(settings_file(root), stored)
    return cleaned


def cities_in(region, opts):
    every = [dict(city) for city in opts["cities"]]
    if region == "us":
        return [city for city in every if city["country"] == "United States"]
    if region == "english":
        return [city for city in every if city["language"] == "English"]
    if region == "europe":
        return [city for city in every if city["region"] == "europe"]
    return every


def random_city(opts, rng=None):
    pool = cities_in(opts["cities_from"], opts)
    if not pool:
        raise AutopilotError("autopilot.cities in config.yaml has no city for {}.".format(opts["cities_from"]))
    return (rng or random).choice(pool)


def resolve_city(text, opts):
    wanted = lead_store.to_slug(text or "", "")
    if not wanted:
        raise AutopilotError("Type a city, or pick a random one.")
    for city in opts["cities"]:
        names = [city["name"]] + list(city.get("aliases") or [])
        if any(lead_store.to_slug(name, "") == wanted for name in names):
            return dict(city)
    return {"name": text.strip(), "country": "", "language": "", "region": ""}


def pick_trade(text, opts, rng=None):
    text = (text or "").strip()
    if text:
        return text
    if not opts["trades"]:
        raise AutopilotError("Name a trade, or pick some for the random choice in the settings.")
    return (rng or random).choice(opts["trades"])


def site_language(city, opts):
    chosen = opts["site"]["language"].strip()
    if chosen.lower() != "city":
        return chosen
    return (city or {}).get("language") or ""


def project_folder(name, settings):
    return build_brief.output_dir(settings) / build_brief.folder_name(name)


def _number(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _known_facts(row):
    return sum(1 for column in ("address", "opening_hours") if (row.get(column) or "").strip())


def choose_candidates(rows, opts, settings, root=None):
    contacted = {row["place_id"] for row in outreach_log.load(root or ROOT)}
    ordered = sorted(
        rows, key=lambda row: (-_number(row.get("score")), -_known_facts(row), (row.get("name") or "").lower())
    )
    chosen = []
    folders = set()
    for row in ordered:
        folder = build_brief.folder_name(row.get("name") or "")
        if (row.get("status") or "").strip() or row["place_id"] in contacted or folder in folders:
            continue
        if opts["only_without_website"] and (row.get("website") or "").strip():
            continue
        if opts["require_phone"] and not (row.get("phone") or "").strip():
            continue
        if (project_folder(row.get("name") or "", settings) / "brief.md").exists():
            continue
        chosen.append(row)
        folders.add(folder)
        if len(chosen) >= opts["sites_per_run"]:
            break
    return chosen


def answers_file(place_id, root=None):
    slug = lead_store.to_slug(place_id, "lead")
    return lead_store.data_dir(root or ROOT) / "autopilot" / "answers" / "{}.json".format(slug)


def stock_folder(name, root=None):
    return (root or ROOT) / "assets" / "stock" / lead_store.to_slug(name, "unnamed")


def _photo_count(folder):
    return len(_read_json(Path(folder) / "sources.json").get("photos", []))


def prepare(place_id, city=None, trade="", settings=None, collect=None, on_event=None):
    settings = settings or lead_search.load_settings()
    opts = options(settings)
    lead, _ = build_brief.find_lead(place_id)
    path = answers_file(lead["place_id"])
    previous = _read_json(path)
    if city is None:
        city = {"name": previous.get("city", ""), "country": previous.get("country", ""), "language": ""}
        city["language"] = previous.get("language", "") if opts["site"]["language"].lower() == "city" else ""

    folder = stock_folder(lead["name"])
    if not (folder / "sources.json").exists():
        plan = find_stock_photos.plan_for_category(lead.get("category") or trade, settings, lead["name"])
        try:
            (collect or find_stock_photos.collect)(plan, folder, settings, on_event)
        except find_stock_photos.StockPhotoError as error:
            raise AutopilotError(str(error))

    stack = STACKS[opts["site"]["stack"]]
    answers = {key: opts["site"][key] for key in SITE_FLAGS}
    answers["show_reviews"] = answers["show_reviews"] and bool(str(lead.get("rating") or "").strip())
    answers.update(
        {
            "stack": stack["name"],
            "stack_needs_a_build": stack["needs_a_build"],
            "stack_reason": "Chosen in the autopilot settings.",
        }
    )
    language = site_language(city, opts)
    if language:
        answers["language"] = language
    if opts["site"]["style"].strip():
        answers["style"] = opts["site"]["style"].strip()
    if city.get("name"):
        answers["city"] = city["name"]
    if city.get("country"):
        answers["country"] = city["country"]
    _write_json(path, answers)

    return {
        "place_id": lead["place_id"],
        "name": lead["name"],
        "category": lead.get("category", ""),
        "city": city.get("name", ""),
        "country": city.get("country", ""),
        "language": language,
        "answers_file": str(path),
        "stock_folder": str(folder),
        "stock_photos": _photo_count(folder),
        "project_folder": str(project_folder(lead["name"], settings)),
        "stack_needs_a_build": stack["needs_a_build"],
        "sender_name": settings["outreach"]["sender_name"],
        "portfolio_links": settings["outreach"]["portfolio_links"],
    }


def drop_photos(place_id, files):
    lead, _ = build_brief.find_lead(place_id)
    folder = stock_folder(lead["name"]).resolve()
    removed = []
    for name in files:
        target = (folder / name).resolve()
        if folder not in target.parents or not target.is_file():
            raise AutopilotError("{} is not a photograph in {}.".format(name, folder))
        target.unlink()
        removed.append(str(target.relative_to(folder)).replace("\\", "/"))
    return removed


def _version_key(path, base):
    parts = path.relative_to(base).parts[0].split(".")
    return tuple(int(part) if part.isdigit() else 0 for part in parts)


def find_builder(opts):
    configured = (opts["builder"]["command"] or "").strip()
    if configured:
        expanded = Path(configured).expanduser()
        if expanded.is_file():
            return str(expanded)
        return shutil.which(configured)

    on_path = shutil.which("claude")
    if on_path:
        return on_path
    home = Path.home()
    for candidate in (home / ".local" / "bin" / "claude", home / ".claude" / "local" / "claude"):
        if candidate.is_file():
            return str(candidate)
    base = home / DESKTOP_COPIES
    copies = sorted(
        base.glob("*/*/claude.app/Contents/MacOS/claude"), key=lambda path: _version_key(path, base), reverse=True
    )
    return str(copies[0]) if copies else None


def venv_python():
    windows = CODE / "venv" / "Scripts" / "python.exe"
    return "venv/Scripts/python.exe" if windows.exists() else "venv/bin/python"


def _scratch_folder(root=None):
    return lead_store.data_dir(root or ROOT) / "autopilot"


def _command_text():
    text = (CODE / COMMAND_FILE).read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def render_prompt(place_id, settings, root=None):
    header = UNATTENDED.format(
        python=venv_python(),
        output=build_brief.output_dir(settings),
        scratch=_scratch_folder(root),
    )
    body = _command_text().replace("$ARGUMENTS", place_id).replace("$1", place_id)
    return "{}\n{}\n".format(header, body)


def _edit_rule(folder):
    return "Edit(//{}/**)".format(Path(folder).resolve().as_posix().lstrip("/"))


def builder_command(executable, prompt, opts, settings, needs_a_build=False, root=None):
    output = build_brief.output_dir(settings)
    allowed = [
        "Read",
        "Glob",
        "Grep",
        "Bash({} scripts/*)".format(venv_python()),
        _edit_rule(output),
        _edit_rule(_scratch_folder(root)),
    ]
    if needs_a_build:
        allowed += ["Bash(npm *)", "Bash(npx *)"]
    command = [executable, "-p", prompt, "--permission-mode", "dontAsk", "--allowedTools"] + allowed
    command += ["--add-dir", str(Path(output).resolve()), "--output-format", "json", "--no-session-persistence"]
    model = (opts["builder"]["model"] or "").strip()
    if model:
        command += ["--model", model]
    return command


def _parse_reply(text):
    text = (text or "").strip()
    for candidate in [text] + text.splitlines()[::-1]:
        try:
            reply = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(reply, dict):
            return reply
    return {"is_error": True, "result": text[-500:] or "Claude Code printed nothing."}


def _not_logged_in(reply):
    words = str(reply.get("result") or "").lower()
    return bool(reply.get("is_error")) and ("not logged in" in words or "/login" in words or "invalid api key" in words)


def _end(process):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_builder(command, log_path, timeout_seconds, stop_event=None, cwd=None):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    reply_path = log_path.with_suffix(".json")
    started = time.monotonic()
    ending = ""

    with open(reply_path, "w", encoding="utf-8") as reply_file, open(log_path, "w", encoding="utf-8") as log:
        try:
            process = subprocess.Popen(
                command, cwd=str(cwd or CODE), stdout=reply_file, stderr=log, stdin=subprocess.DEVNULL
            )
        except OSError as error:
            return {
                "ok": False,
                "result": "Claude Code could not be started: {}".format(error),
                "not_logged_in": False,
                "timed_out": False,
                "stopped": False,
            }
        while process.poll() is None:
            if stop_event is not None and stop_event.is_set():
                ending = "stopped"
            elif time.monotonic() - started > timeout_seconds:
                ending = "timed_out"
            if ending:
                _end(process)
                break
            time.sleep(POLL_SECONDS)

    reply = _parse_reply(reply_path.read_text(encoding="utf-8", errors="replace"))
    return {
        "ok": not ending and process.returncode == 0 and not reply.get("is_error"),
        "result": str(reply.get("result") or ""),
        "not_logged_in": _not_logged_in(reply),
        "timed_out": ending == "timed_out",
        "stopped": ending == "stopped",
    }


def check_builder(opts, settings=None):
    executable = find_builder(opts)
    if not executable:
        return {
            "state": "missing",
            "path": "",
            "message": "No Claude Code was found on this computer.",
        }
    command = [executable, "-p", CHECK_PROMPT, "--permission-mode", "dontAsk", "--output-format", "json"]
    command += ["--no-session-persistence"]
    if (opts["builder"]["model"] or "").strip():
        command += ["--model", opts["builder"]["model"].strip()]
    seconds = opts["builder"]["check_timeout_seconds"]
    try:
        finished = subprocess.run(
            command, cwd=str(CODE), capture_output=True, text=True, timeout=seconds, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        return {"state": "error", "path": executable, "message": "Claude Code did not answer within {} seconds.".format(seconds)}
    except OSError as error:
        return {"state": "error", "path": executable, "message": "Claude Code could not be started: {}".format(error)}

    reply = _parse_reply(finished.stdout)
    if _not_logged_in(reply):
        return {
            "state": "logged_out",
            "path": executable,
            "message": "Claude Code was found but is not logged in.",
        }
    if reply.get("is_error") or finished.returncode:
        detail = str(reply.get("result") or finished.stderr or "no reply").strip()[-300:]
        return {"state": "error", "path": executable, "message": "Claude Code answered with an error: {}".format(detail)}
    return {"state": "ready", "path": executable, "message": "Claude Code is logged in and answering."}


def messages(folder):
    path = Path(folder) / MESSAGES_FILE
    if not path.exists():
        return []
    found = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## "):
            found.append({"title": line[3:].strip(), "lines": []})
        elif found:
            found[-1]["lines"].append(line)
    return [{"title": item["title"], "text": "\n".join(item["lines"]).strip()} for item in found]


def verify_project(folder):
    folder = Path(folder)
    if not (folder / "brief.md").exists():
        return ["brief.md was never written."]
    _, problems = check_site.check(folder)
    written = {item["title"].lower() for item in messages(folder) if item["text"]}
    missing = [heading for heading in MESSAGE_HEADINGS if heading.lower() not in written]
    if missing:
        problems.append("{} has no {} message.".format(MESSAGES_FILE, " or ".join(missing)))
    return problems


def runs_folder(root=None):
    return _scratch_folder(root) / "runs"


def _now():
    return datetime.now().isoformat(timespec="seconds")


class Run:
    def __init__(self, state, root=None):
        self.state = state
        self.path = runs_folder(root) / "{}.json".format(state["id"])

    def save(self):
        _write_json(self.path, self.state)

    def update(self, **fields):
        self.state.update(fields)
        self.save()
        return self.state


def new_run(city, trade, root=None):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = stamp
    number = 2
    while (runs_folder(root) / "{}.json".format(run_id)).exists():
        run_id = "{}-{}".format(stamp, number)
        number += 1
    run = Run(
        {
            "id": run_id,
            "started": _now(),
            "finished": "",
            "city": city,
            "trade": trade,
            "query": "{} {}".format(trade, city["name"]),
            "state": "searching",
            "message": "",
            "builder": "",
            "builder_problem": "",
            "leads_file": "",
            "found": 0,
            "candidates": [],
        },
        root,
    )
    run.save()
    return run


def _candidate(row):
    return {
        "place_id": row["place_id"],
        "name": row.get("name", ""),
        "address": row.get("address", ""),
        "phone": row.get("phone", ""),
        "score": row.get("score", ""),
        "state": "waiting",
        "folder": "",
        "photos": 0,
        "problems": [],
        "summary": "",
        "log": "",
        "command": "/autopilot {}".format(row["place_id"]),
        "sent": [],
    }


def _build_one(candidate, run, settings, opts, stop_event, build):
    log = runs_folder() / run.state["id"] / "{}.log".format(lead_store.to_slug(candidate["place_id"], "lead"))
    candidate.update(state="building", log=str(log), started=_now())
    run.save()
    build_brief.output_dir(settings).mkdir(parents=True, exist_ok=True)

    prompt = render_prompt(candidate["place_id"], settings)
    needs_a_build = STACKS[opts["site"]["stack"]]["needs_a_build"]
    command = builder_command(run.state["builder"], prompt, opts, settings, needs_a_build)
    outcome = build(command, log, opts["builder"]["timeout_minutes"] * 60, stop_event)

    if outcome["not_logged_in"]:
        run.state["builder_problem"] = "Claude Code is not logged in, so this run stopped building."
        candidate["state"] = "paste"
    elif outcome["stopped"]:
        candidate["state"] = "stopped"
    else:
        problems = verify_project(candidate["folder"])
        if outcome["timed_out"]:
            minutes = opts["builder"]["timeout_minutes"]
            problems.insert(0, "Claude Code ran past the {} minute limit and was stopped.".format(minutes))
        elif not outcome["ok"]:
            problems.insert(0, "Claude Code ended with an error: {}".format(outcome["result"][:300]))
        candidate.update(state="attention" if problems else "done", problems=problems)
        candidate["summary"] = outcome["result"][:800]
    candidate["finished"] = _now()
    run.save()


def _work_on(candidate, run, settings, opts, stop_event, collect, build, building):
    candidate["state"] = "photos"
    run.save()
    try:
        prepared = prepare(candidate["place_id"], run.state["city"], run.state["trade"], settings, collect)
    except (AutopilotError, build_brief.BriefError) as error:
        candidate.update(state="failed", problems=[str(error)])
        run.save()
        return
    candidate.update(folder=prepared["project_folder"], photos=prepared["stock_photos"])

    if not building or not run.state["builder"] or run.state["builder_problem"]:
        candidate["state"] = "paste"
        run.save()
        return
    _build_one(candidate, run, settings, opts, stop_event, build)


def execute(run, settings, stop_event, search=None, collect=None, build=None, building=True, report=None):
    opts = options(settings)
    state = run.state
    say = report or (lambda text: None)

    run.update(state="searching", message="Searching for {} in {}.".format(state["trade"], state["city"]["name"]))
    say(state["message"])
    city = state["city"]
    try:
        result = (search or lead_search.run_search)(
            state["query"],
            limit=opts["search_limit"],
            audit=not opts["only_without_website"],
            place={
                "term": state["trade"],
                "name": city["name"],
                "lookup": city.get("area") or city["name"],
                "country_code": city.get("code", ""),
            },
        )
    except lead_search.SearchError as error:
        say(str(error))
        return run.update(state="failed", message=str(error), finished=_now())

    rows = result.get("rows") or []
    chosen = choose_candidates(rows, opts, settings)
    builder = (find_builder(opts) or "") if building else ""
    run.update(
        leads_file=result["path"].name if result.get("path") else "",
        found=len(rows),
        builder=builder,
        candidates=[_candidate(row) for row in chosen],
    )
    if not chosen:
        message = (
            "Found {} businesses for {}, and none of them fits the settings: not contacted yet, not built "
            "before{}{}.".format(
                len(rows),
                state["query"],
                ", without a website" if opts["only_without_website"] else "",
                ", with a phone number" if opts["require_phone"] else "",
            )
        )
        say(message)
        return run.update(state="done", message=message, finished=_now())

    run.update(state="building", message="Picked {} of {} businesses.".format(len(chosen), len(rows)))
    say(state["message"])
    for candidate in state["candidates"]:
        if stop_event.is_set():
            break
        say("{}: preparing".format(candidate["name"]))
        _work_on(candidate, run, settings, opts, stop_event, collect, build or run_builder, building)
        say("{}: {}".format(candidate["name"], candidate["state"]))

    for candidate in state["candidates"]:
        if candidate["state"] == "waiting":
            candidate["state"] = "stopped"
    stopped = stop_event.is_set()
    return run.update(
        state="stopped" if stopped else "done",
        message=_outcome(state["candidates"], len(rows)),
        finished=_now(),
    )


OUTCOME_WORDS = [
    ("done", "built"),
    ("attention", "with problems to look at"),
    ("paste", "waiting for the command to be pasted"),
    ("failed", "could not be prepared"),
    ("stopped", "stopped"),
]


def _outcome(candidates, found):
    counts = [
        "{} {}".format(sum(1 for item in candidates if item["state"] == state), words)
        for state, words in OUTCOME_WORDS
        if any(item["state"] == state for item in candidates)
    ]
    return "Picked {} of {} businesses: {}.".format(len(candidates), found, ", ".join(counts))


class Runner:
    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.stop_event = threading.Event()
        self.run_id = ""

    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, city_text="", random_pick=False, trade_text="", settings=None, **hooks):
        with self.lock:
            if self.busy():
                raise AutopilotError("A run is already going. Stop it, or wait for it to finish.")
            settings = settings or lead_search.load_settings()
            opts = options(settings)
            city = random_city(opts) if random_pick else resolve_city(city_text, opts)
            run = new_run(city, pick_trade(trade_text, opts))
            self.stop_event = threading.Event()
            self.run_id = run.state["id"]
            self.thread = threading.Thread(target=self._guarded, args=(run, settings, hooks), daemon=True)
            self.thread.start()
            return run.state

    def _guarded(self, run, settings, hooks):
        try:
            execute(run, settings, self.stop_event, **hooks)
        except Exception as error:
            run.update(state="failed", message="Unexpected failure: {}".format(error), finished=_now())

    def stop(self):
        if not self.busy():
            return False
        self.stop_event.set()
        return True

    def wait(self, seconds=None):
        if self.thread is not None:
            self.thread.join(seconds)


def load_run(run_id, runner=None, root=None):
    if not run_id or "/" in run_id or "\\" in run_id or run_id.startswith("."):
        return None
    run = Run({"id": run_id}, root)
    if not run.path.exists():
        return None
    run.state = _read_json(run.path)
    alive = runner is not None and runner.busy() and runner.run_id == run_id
    if run.state.get("state") in ACTIVE_STATES and not alive:
        for candidate in run.state.get("candidates", []):
            if candidate["state"] in ("waiting", "photos", "building"):
                candidate["state"] = "stopped"
        run.update(state="interrupted", message="The page was closed or restarted while this run was going.")
    return run


def list_runs(runner=None, root=None, limit=20):
    folder = runs_folder(root)
    if not folder.exists():
        return []
    found = []
    for path in sorted(folder.glob("*.json"), reverse=True)[:limit]:
        run = load_run(path.stem, runner, root)
        if run:
            found.append(
                {key: run.state.get(key) for key in ("id", "started", "query", "state", "found")}
                | {"sites": len(run.state.get("candidates", []))}
            )
    return found


def _site_url(page, settings):
    base = build_brief.output_dir(settings).resolve()
    relative = Path(page).resolve().relative_to(base).as_posix()
    return "/sites/" + quote(relative)


def view(run, settings=None):
    settings = settings or lead_search.load_settings()
    state = json.loads(json.dumps(run.state))
    for candidate in state.get("candidates", []):
        folder = Path(candidate["folder"]) if candidate["folder"] else None
        found = messages(folder) if folder else []
        page = check_site.entry_page(folder) if folder else None
        candidate["messages"] = found
        candidate["site_url"] = _site_url(page, settings) if page else ""
        if candidate["state"] in ("paste", "stopped") and found and page:
            candidate["problems"] = verify_project(folder)
            candidate["state"] = "attention" if candidate["problems"] else "done"
    return state


def mark_sent(run, place_id, channel, settings=None):
    settings = settings or lead_search.load_settings()
    candidate = next((item for item in run.state.get("candidates", []) if item["place_id"] == place_id), None)
    if candidate is None:
        raise AutopilotError("That business is not part of this run.")
    try:
        row = outreach_log.record_send(ROOT, place_id, candidate["name"], channel, settings)
    except outreach_log.OutreachError as error:
        raise AutopilotError(str(error))
    candidate.setdefault("sent", []).append({"channel": channel, "on": row["sent_at"]})
    run.save()
    return row


def _print_json(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Runs a city start to finish with the saved autopilot settings.")
    commands = parser.add_subparsers(dest="action", required=True)

    commands.add_parser("settings", help="Print the autopilot settings in force")

    prepare_command = commands.add_parser("prepare", help="Download the stock photographs and write the answers")
    prepare_command.add_argument("place_id", help="The place_id, or the business name")
    prepare_command.add_argument("--city", help="The city the lead is in, when the answers do not say yet")
    prepare_command.add_argument("--trade", default="", help="Trade to search photographs for when the lead has none")

    drop_command = commands.add_parser("drop-photo", help="Remove stock photographs that do not belong")
    drop_command.add_argument("place_id", help="The place_id, or the business name")
    drop_command.add_argument("files", nargs="+", help="Paths as sources.json writes them, such as hero/hero_1.jpg")

    run_command = commands.add_parser("run", help="Search a city and build the best candidates")
    where = run_command.add_mutually_exclusive_group(required=True)
    where.add_argument("--city", help="The city to search")
    where.add_argument("--random", action="store_true", help="Pick a random city from autopilot.cities")
    run_command.add_argument("--trade", default="", help="The trade, or a random one from the settings")
    run_command.add_argument(
        "--no-build", action="store_true", help="Stop after the photographs and print the command for each lead"
    )

    commands.add_parser("check-builder", help="Ask Claude Code for one word to see whether it can build")
    arguments = parser.parse_args()

    try:
        settings = lead_search.load_settings()
        opts = options(settings)
        if arguments.action == "settings":
            _print_json({key: value for key, value in opts.items() if key != "cities"})
        elif arguments.action == "prepare":
            city = resolve_city(arguments.city, opts) if arguments.city else None
            _print_json(prepare(arguments.place_id, city, arguments.trade, settings))
        elif arguments.action == "drop-photo":
            _print_json({"removed": drop_photos(arguments.place_id, arguments.files)})
        elif arguments.action == "check-builder":
            _print_json(check_builder(opts, settings))
        else:
            city = random_city(opts) if arguments.random else resolve_city(arguments.city, opts)
            run = new_run(city, pick_trade(arguments.trade, opts))
            print("\n{} ({})\n".format(run.state["query"], city.get("country") or "country not in the list"))
            execute(run, settings, threading.Event(), building=not arguments.no_build, report=lambda text: print("  " + text))
            for candidate in run.state["candidates"]:
                print("\n{}: {}".format(candidate["name"], candidate["state"]))
                if candidate["folder"]:
                    print("  folder: {}".format(candidate["folder"]))
                if candidate["state"] == "paste":
                    print("  paste into Claude Code: {}".format(candidate["command"]))
                for problem in candidate["problems"]:
                    print("  - {}".format(problem))
            print()
    except (AutopilotError, build_brief.BriefError, lead_search.SearchError) as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
