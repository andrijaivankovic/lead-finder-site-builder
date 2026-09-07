---
description: Build the project folder and website brief for one lead
argument-hint: <place_id>
allowed-tools: Bash, Read, Write
---

Build the website brief for the lead whose place_id is `$1`.

If `$1` is empty, list the top ten leads from the newest file in `data/` and ask
which one, then continue with the place_id they pick.

Work in this order and do not skip the questions.

`{venv python}` below is the Python inside `venv`: `venv/bin/python` on macOS and
Linux, `venv/Scripts/python.exe` on Windows. Check which of the two exists in the
project folder and use that one. Never a bare `python`.

Substitute every `{...}` before running a command. Never paste one into a shell
as it stands.

## 1. Read the lead

```
{venv python} scripts/build_brief.py "$1" --info
```

Report the business name, its trade from the `category` field, the address, the
phone, whether it has a website, and the website problems if any were found.
Keep it to three lines.

## 2. Ask the questions

Before asking anything, open the business and look at it. The lead carries a
Google Maps link, and the name plus the city usually turns up an Instagram or a
Facebook page. Two minutes of that changes every answer below: you see what the
place actually looks like, and often what colours are already on their sign,
their menu or their posts.

Read `brief.default_language` from `config.yaml`, which a `config.local.yaml`
may override. That is the language the sites are written in, and it is also the
language to ask these questions in. Translate them; do not ask in English out of
habit when the setting says otherwise.

Put these to them as choices they pick from, through whatever interactive
question mechanism you have, so they answer by selecting rather than by typing
answers back. Where the mechanism takes several answers at once, group the yes
or no ones into a single question. If you have no such mechanism, fall back to
one numbered block with the default in brackets, and say that pressing enter
accepts all defaults.

1. FAQ section? [yes]
2. Careers section? [yes]
3. Show the rating and review count? [yes]
4. GSAP and ScrollTrigger animations? [yes]
5. Generate AI images and video? [yes]
6. Language of the site? [the configured default]

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

Finally, two optional things, both drawn from what you saw when you opened the
business:

> Their colours, if the sign, the menu or the posts show any. Skip it and the
> palette comes from the trade and the photographs.

> A few words about how the place looks, for example "modern, white, lots of
> glass". Skip it and the trade alone decides.

Ask both in the same language as the questions above, and offer what you saw as
the suggestion rather than handing them an empty field.

The colours go in as `brand_colors`, a list of hex codes. `build_brief.py` reads
that straight from the answers, so it does not have to come from
`sort_assets.py`. With colours the build prompt anchors the palette on what the
business already uses instead of inventing one, which is most of what separates
a demo that looks made for them from a demo that looks like a template.

The words go in as `note`, translated into English first, because Pexels only
searches in English. An empty answer to either is a perfectly good answer and
must not be pushed.

## 3. Collect the photographs

The trade in the `category` field picks a ready set of Pexels searches from
`config.yaml`, so nothing has to be invented:

```
{venv python} scripts/find_stock_photos.py --category "{category}" --business "{name}" --note "{note}"
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
- `brand_colors` is what they answered above, or what `assets.json` from
  `sort_assets.py` holds once a client has sent their own images. Empty when
  there is neither.
- `style` is their optional note tidied up, or a plain description of the trade
  if they skipped it.
- `trade` and `city` in English, for the build prompt.
- `language`, `faq`, `careers`, `show_reviews`, `animations`, `ai_media`,
  `stack` and `stack_reason` are their answers from step 2.

Write that JSON to a temporary file and run:

```
{venv python} scripts/build_brief.py "$1" --answers {answers.json} --stock {stock folder}
```

## 5. Report

Tell them the folder path, that `brief.md` is inside it, how many images were
copied, and that they can now say `/build-site "<folder name>"` to have the site
built into `site/`.

Never write the website itself during this command. This command only prepares
the folder.
