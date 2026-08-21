# lead-finder-site-builder

Finds local businesses that have no website or a bad one, ranks them as
prospects, then prepares everything needed to send them a finished demo site
and a message.

This file is the briefing for whoever works on this repository. It is written
for Claude Code, which reads it automatically at the start of a session. If you
work with a different assistant, hand it the contents of this file first. It is
plain English and nothing in it is specific to one tool.

## Run things with the virtual environment

Always use `venv/Scripts/python.exe`, never a bare `python`.

```
venv/Scripts/python.exe scripts/find_leads.py "picerija Novi Sad"
venv/Scripts/python.exe scripts/audit_site.py example.com
venv/Scripts/python.exe app.py
```

Never start `app.py` with a plain shell command when a preview tool is
available.

## The rule the architecture rests on

Anything that gives the same answer every time, meaning searching, filtering,
scoring, downloading, moving files and reading colours, is a Python script. The
model is used only where judgement is required: describing what a place looks
like, choosing sections for a trade, writing copy, writing the outreach message.

This is why `find_stock_photos.py` is handed a query plan instead of inventing
search terms, and why `sort_assets.py` refuses to move anything until the
categories are filled in.

## Code conventions

- No comments anywhere in the code, and no explanatory headers at the top of
  files. Names carry the meaning. `ARHITEKTURA.md` is the only place code is
  explained, one sentence per file.
- Everything is written in English: identifiers, config keys, CSV columns,
  printed output, the browser interface, and the docs.
- Every tunable number lives in `config.yaml`, never inline in a script.
- Anything personal to one user, such as their name and their portfolio links,
  belongs in `config.local.yaml`. That file is gitignored and merged over
  `config.yaml` when settings load, so `config.yaml` can stay public and ship
  with those fields empty.
- Secrets come from `.env` through `python-dotenv` and are never printed.
- No heavy dependencies. `requests`, `beautifulsoup4`, `python-dotenv`,
  `flask`, `PyYAML` and `Pillow` are the whole list.
- The browser interface is plain HTML, CSS and JavaScript. No component
  libraries.

## Data

CSV files under `data/` are the database. `place_id` is the key that survives
across searches, which is what lets a rerun refresh the data while keeping the
`status` column the user typed by hand. Never reorder or rename CSV columns
without migrating existing files.

`data/`, `.env`, `config.local.yaml`, `assets/` and `ARHITEKTURA.md` never get
committed.

## Building a website for a lead

`/build-brief <place_id>` prepares a folder on the Desktop:

```
<Business>/
├── brief.md      the full instruction for the site, self contained
├── assets/       licensed photographs, grouped by purpose
└── site/         empty, this is where the website goes
```

When asked to build the site, read that folder's `brief.md` and follow the
"Build prompt" section in it literally. `/build-site <folder>` does this.

The stack is decided per business and written into the brief. Plain HTML, CSS
and JavaScript is the default and the right answer for most one page local
business sites, because the folder can be sent as is and opened by double
clicking. A framework is fine when the site actually needs one, as long as it
builds to a static bundle that runs on any host with no server behind it.

Whatever the stack, the site is mobile first, and it is never called finished
until it has been served and looked at in a browser at 360px and at desktop
width.

## Git

Work on a branch per phase, open a pull request, then merge it. Commit messages
in English. Do not add co-author trailers.

## Boundaries that are deliberate, do not remove them

- The tool never sends a message anywhere and holds no credentials for any
  messaging account. It only drafts.
- Site images come from Pexels, chosen by trade
  from `stock_photos.plans` in `config.yaml`, or from the client.
- The monthly Google call limit in `config.yaml` stays below the free tier.
- Nothing scrapes Google Maps or CompanyWall. The tool generates links a human
  clicks.
