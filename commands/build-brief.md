---
description: Build the project folder and website brief for one lead
argument-hint: <place_id>
allowed-tools: Bash, Read, Write
---

Build the website brief for the lead whose place_id is `$1`.

If `$1` is empty, list the top ten leads from the newest file in `data/` and ask
which one, then continue with the place_id they pick.

Work in this order and do not skip the questions.

## 1. Read the lead

```
venv/Scripts/python.exe scripts/build_brief.py "$1" --info
```

Report the business name, its trade from the `category` field, the address, the
phone, whether it has a website, and the website problems if any were found.
Keep it to three lines.

## 2. Ask the questions

Ask them as one numbered block, with the default in brackets, and say that
pressing enter accepts all defaults. Write the questions in Serbian.

1. FAQ sekcija? [da]
2. Sekcija za zapošljavanje? [da]
3. Prikaz ocene i broja recenzija? [da]
4. GSAP + ScrollTrigger animacije? [da]
5. Generisati AI slike i video? [da]
6. Jezik sajta? [srpski]

If the lead has no rating and no review count, say so and recommend "ne" for
question 3, because there is nothing to show.

Then ask a seventh question about the stack, and give a recommendation rather
than a blank choice. Judge it from the trade, the sections chosen and whether
animations were wanted:

- A one page site for a small local business is almost always better as plain
  HTML, CSS and JavaScript. It opens by double clicking, it can be sent as a
  folder, and it drops onto any free host in seconds.
- Reach for a framework only when the site genuinely needs it: many pages, a
  menu or price list that will change often, a booking flow, or content the
  owner will edit themselves. Prefer one that builds to static output, such as
  Astro or Vite, so the result still runs anywhere with no server.

Say which you recommend and why in one sentence, then let them override it.
Record the answer as `stack` and the one sentence as `stack_reason`.

Finally, offer one optional line rather than asking a question they must answer:

> Ako hoćeš da slike budu bliže baš ovom lokalu, dopiši par reči o njemu
> (npr. "moderno, belo, puno stakla"). Ako preskočiš, uzimam slike po delatnosti.

Whatever they write goes in as `note`, translated into English first, because
Pexels only searches in English. "moderno, belo, puno stakla" becomes
"modern white glass". An empty answer is a perfectly good answer and must not be
pushed.

## 3. Collect the photographs

The trade in the `category` field picks a ready set of Pexels searches from
`config.yaml`, so nothing has to be invented:

```
venv/Scripts/python.exe scripts/find_stock_photos.py --category "<category>" --business "<name>" --note "<note>"
```

Drop `--note` when they did not write one.

Then read every `description` in the generated `sources.json` and check it
against the trade. The script filters resolution and orientation only. It cannot
see what is in a picture, so a search for a bright waiting room happily returns
living rooms and hair salons.

If something obviously belongs to a different kind of business, delete the
folder and run it again with better terms through `--query`, then say which ones
you had to correct. If a whole trade keeps coming back wrong, that is a sign its
entry in `config.yaml` under `stock_photos.plans` needs fixing, so say that too.

Report how many photographs came back and where they went.

## 4. Write the brief

Compose the remaining fields yourself:

- `sections` is the section list for the site, in build order, honouring the
  answers above. Base it on the trade: a restaurant needs a menu, a dentist
  needs services and prices, a hairdresser needs a booking call to action.
- `seo_keywords` is eight to twelve phrases that someone in that city would
  actually type, in the site language, mixing the trade, the city and the
  neighbourhood.
- `brand_colors` only if `assets.json` from `sort_assets.py` already holds them,
  otherwise leave the list empty.
- `style` is their optional note tidied up, or a plain description of the trade
  if they skipped it.
- `trade` and `city` in English, for the build prompt.
- `language`, `faq`, `careers`, `show_reviews`, `animations`, `ai_media`,
  `stack` and `stack_reason` are their answers from step 2.

Write that JSON to a temporary file and run:

```
venv/Scripts/python.exe scripts/build_brief.py "$1" --answers <answers.json> --stock <stock folder>
```

## 5. Report

Tell them the folder path, that `brief.md` is inside it, how many images were
copied, and that they can now say `/build-site "<folder name>"` to have the site
built into `site/`.

Never write the website itself during this command. This command only prepares
the folder.
