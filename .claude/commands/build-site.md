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

- Static only. No framework, no build step, no package manager. Double clicking
  `site/index.html` must show the finished site.
- Image paths are relative, `../assets/<purpose>/<file>`.
- Every visible word is in the language the brief names.
- No lorem ipsum. Write real copy for this business.
- Never invent reviews, staff names, prices or opening hours. Put a clear
  placeholder in the site language and list every placeholder in an HTML
  comment at the bottom of `index.html`.
- `<title>`, `<meta name="description">` and `<meta name="viewport">` are
  mandatory.

## 3. Check it

Open the finished page in the preview browser and look at it at 360px wide
before anything else, then at desktop width. Read the console for errors.
Confirm every image actually loads.

Fix what you find, then take a screenshot at both widths and show them.

## 4. Report

Say which files you wrote, list the placeholders the owner has to fill in, and
give one sentence on what this site does better than whatever the business has
now.

Do not write the outreach message here. That is `/draft-outreach`.
