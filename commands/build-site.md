---
description: Build the website for a prepared brief folder
argument-hint: <folder or business name>
allowed-tools: Bash, Read, Write, Edit, Glob
---

Build the website described by the brief in `$1`.

`$1` may be a full path, or just the business name, in which case look for a
folder with that name on the Desktop.

## 1. Read the brief

Read `$1/brief.md` in full before writing anything. The section named
**Build prompt** is the instruction and it stands on its own — follow it
literally rather than substituting your own preferences.

List `$1/assets/` so you know the exact filenames available, and read
`$1/assets/sources.json` for what each photograph actually shows. Use those
descriptions to place images sensibly: do not put an oven photograph in a team
section.

## 2. Build

Write `index.html`, `style.css` and `script.js` into `$1/site/`.

Hard rules, repeated because they are the ones most often broken:

- The stack is whatever `brief.md` says under **Build prompt**. Do not quietly
  swap it. Whatever it is, the production build must end up as a static bundle
  that runs on any host with no server behind it.
- Image paths are relative, `../assets/<purpose>/<file>`.
- Every visible word is in the language the brief names.
- No lorem ipsum. Write real copy for this business.
- Never invent reviews, staff names, prices or opening hours. Put a clear
  placeholder in the site language and list every placeholder in an HTML
  comment at the bottom of `index.html`.
- `<title>`, `<meta name="description">` and `<meta name="viewport">` are
  mandatory.

## 3. Serve it and look at it

This step is not optional. Never say a site is finished without having opened
it.

Add an entry to `.claude/launch.json` for this site and start it with the
preview tool. For a plain HTML site that is a static file server rooted at the
brief folder, so `../assets/` resolves; for a framework it is that stack's dev
command.

Then look at it at 360px wide before anything else, then at desktop width. Read
the browser console for errors. Confirm every image actually loads rather than
assuming the paths are right.

Fix what you find, re-check, then screenshot both widths and show them.

Leave the server running so they can click around, and tell them the address.

## 4. Report

Say which files you wrote, list the placeholders the owner has to fill in, and
give one sentence on what this site does better than whatever the business has
now.

Do not write the outreach message here. That is `/draft-outreach`.
