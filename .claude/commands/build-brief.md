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

Report the business name, address, phone, whether it has a website, and the
website problems if any were found. Keep it to three lines.

## 2. Ask the six questions

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

## 3. Ask how the place looks

This is the one answer that cannot be defaulted. Ask, in Serbian, what the place
looks like — materials, colours, lighting, whether it is modern or traditional,
who the customers are. Tell them to click the `maps` or `pin` link in the table
and glance at the photos for ten seconds if they do not know.

If `assets/reference/` already holds photographs for this business, read them
first with the Read tool, describe what you see, and ask them to confirm or
correct it rather than write it from scratch.

## 4. Collect the photographs

Turn their description into five to eight Pexels search terms, spread across the
purposes `hero`, `gallery`, `background`, `interior` and, only if the business
plausibly shows staff, `team`. Terms must be in English and must describe the
mood, not the business name.

Write the plan to a temporary JSON file and run:

```
venv/Scripts/python.exe scripts/find_stock_photos.py --plan <plan.json>
```

Report how many photographs came back and where they went.

## 5. Write the brief

Compose the remaining fields yourself:

- `sections` — the section list for the site, in build order, honouring the
  answers above. Base it on the trade: a restaurant needs a menu, a dentist
  needs services and prices, a hairdresser needs a booking call to action.
- `seo_keywords` — eight to twelve phrases that someone in that city would
  actually type, in the site language, mixing the trade, the city and the
  neighbourhood.
- `brand_colors` — only if `assets.json` from `sort_assets.py` already holds
  them, otherwise leave the list empty.
- `style` — their description from step 3, tidied up.
- `language`, `faq`, `careers`, `show_reviews`, `animations`, `ai_media` — their
  answers from step 2.

Write that JSON to a temporary file and run:

```
venv/Scripts/python.exe scripts/build_brief.py "$1" --answers <answers.json> --stock <stock folder>
```

## 6. Report

Tell them the folder path, that `brief.md` is inside it, how many images were
copied, and that they can now say "napravi sajt po brifu iz <folder>" to have
the site built into `site/`.

Never write the website itself during this command. This command only prepares
the folder.
