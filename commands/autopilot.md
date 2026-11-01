---
description: Build one lead start to finish with the saved autopilot settings, asking nothing
argument-hint: <place_id or business name>
allowed-tools: Bash, Read, Write, Edit, Glob
---

Take the lead that `$1` names from a row in a search result to a finished demo
site and three drafted messages, using the autopilot settings saved on the
Settings page of the browser. Ask nothing. Every answer `/build-brief` would
ask for is already in those settings, and every other decision below names its
default.

`{venv python}` below is the Python inside `venv`: `venv/bin/python` on macOS and
Linux, `venv/Scripts/python.exe` on Windows. Check which of the two exists in the
project folder and use that one. Never a bare `python`.

Substitute every `{...}` before running a command. Never paste one into a shell
as it stands.

Never send anything and never log anything as sent. The person reads the
messages and sends them.

## 1. Prepare

```
{venv python} scripts/autopilot.py prepare "$1"
```

It finds the lead, downloads its stock photographs unless they are already
there, and writes the answers from the settings into a file. It prints JSON
naming that `answers_file`, the `stock_folder`, the `project_folder`, the city,
the site language, the sender name and the portfolio links, and whether the
site is to be published: `deploy` and the `deploy_name` to publish it under.

## 2. Check the photographs

Read every `description` in `sources.json` in the stock folder against the
trade, then open every hero and interior photograph and look at it. Remove each
one that plainly shows another kind of business, or another business's name or
logo on a window, a cup or a board:

```
{venv python} scripts/autopilot.py drop-photo "$1" {file} {file}
```

`{file}` is the path as `sources.json` writes it, such as `hero/hero_123.jpg`.
Do not search again. One photograph fewer is fine; somebody else's sign in
front of the owner is not.

## 3. Write the brief

Read the answers file and add what only judgement can give. Leave every value
already in it exactly as it is.

- `sections`, `seo_keywords`, `trade` and, when the file has none, `style`,
  exactly as step 4 of `commands/build-brief.md` describes them.
- `language`, when the file has none: the language most people in that city
  speak.
- `city`, when the file has none, read from the lead's address or its Maps link.

Then:

```
{venv python} scripts/build_brief.py "$1" --answers {answers_file} --stock {stock_folder}
```

## 4. Build the site

Follow steps 1 and 2 of `commands/build-site.md` for the project folder: read
`brief.md` and build exactly what its **Build prompt** asks for.

When the brief asks for GSAP and ScrollTrigger, get the local copies first:

```
{venv python} scripts/add_gsap.py {project_folder}
```

It puts `gsap.min.js` and `ScrollTrigger.min.js` in `site/vendor/` and prints
the two script tags to load them with. Load them from there and never open
those files: they are minified and only fill the session.

For a stack with a build step, install and build from the project folder with
`npm --prefix {project_folder}/site install` and
`npm --prefix {project_folder}/site run build`, so the finished bundle lands in
`site/dist/`.

Then check it:

```
{venv python} scripts/check_site.py {project_folder}
```

Fix every problem it lists and run it again until it passes. When you also
have a browser preview tool, serve the site and look at it at 360px and at
desktop width, as step 3 of `commands/build-site.md` describes. Without one,
the check is the last word, and the person looks at the site in the browser
page afterwards.

## 5. Publish

Skip this step when step 1 printed `deploy` as false. Otherwise, once the check
passes:

```
{venv python} scripts/deploy_site.py {project_folder} --name "{deploy_name}"
```

It publishes the site on Vercel and prints its public address. That address is
the demo the messages point to. When the command fails, or warns that the
address needs a Vercel login, leave the address out of the messages and say why
in the report.

## 6. Draft the messages

Write the three versions exactly as step 3 of `commands/draft-outreach.md`
describes, in the site language, signed with the sender name and carrying every
portfolio link that step 1 printed. Where the sender name is empty, sign with
`[your name]` rather than inventing one.

When step 5 published the site, every version carries its address as the link
to the demo, on its own line, before the portfolio links.

Save them to `outreach.md` in the project folder under exactly these three
headings, so the browser page can show each one with a copy button:

```
## Email
## Viber or WhatsApp
## Instagram
```

The email starts with its `Subject:` line.

## 7. Report

One short paragraph: the folder, whether the check passed, the address the site
was published at or why it was not, the placeholders the owner has to fill in,
and that the messages are in `outreach.md`.
