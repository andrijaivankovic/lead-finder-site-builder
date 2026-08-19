---
description: Draft the three outreach messages for one lead
argument-hint: <place_id or business name>
allowed-tools: Bash, Read, Glob
---

Draft the messages for `$1`. You write them. You never send them, and this
project holds no credentials for any messaging account. That is deliberate.

## 1. Show what is outstanding first

```
venv/Scripts/python.exe scripts/outreach.py --due
```

Report anyone waiting on a follow up before anything else, oldest first. If
`$1` is empty, stop there — the list was the point.

## 2. Gather the material

```
venv/Scripts/python.exe scripts/build_brief.py "$1" --info
```

Read the business folder if it exists: `brief.md` for the style and sections,
`assets/sources.json` for what the photographs show, and `site/` to see whether
the site is actually built. Never claim a site is ready when `site/` is empty.

Read `outreach.sender_name` and `outreach.portfolio_links` from `config.yaml`.
If either is empty, say so and ask, rather than inventing a link or signing with
a made up name.

Each portfolio entry carries a `what` describing the kind of business it was
built for. Pick the one closest to this prospect and lead with it — a grill owner
should see the grill site, not the bakery. Send at most two links in the email
and exactly one in the short messages. Never paste all three.

If nothing in the list is close, pick the one whose mood matches the style
description in the brief, and do not pretend it is the same trade.

## 3. Write three versions

All three in the language the brief names, Serbian unless it says otherwise.

Every version must carry four things:

1. **One concrete detail about that specific business.** The neighbourhood, what
   they are known for, something from their reviews, something visible in the
   photographs. Generic praise reads as a mail merge and gets deleted.
2. **The site already exists and costs nothing to look at.** Not an offer to
   build one. It is built.
3. **A link to previous work**, from `outreach.portfolio_url`.
4. **That the photographs are temporary** and get swapped for their own as soon
   as they say they are interested. Never let them think those are their rooms.

Tone: a student who builds sites, writing to a person. Relaxed, direct, no
corporate vocabulary, no "dear sir or madam", no "revolutionise your online
presence", no emoji storm. Short sentences. It should read like it was typed
once, not generated.

Never invent facts about the business: no fake compliments about food you have
not eaten, no numbers, no claims about their revenue or their competitors.

**Email** — subject line plus five to eight sentences. Enough room to explain
why they got the message.

**Viber or WhatsApp** — three or four sentences. No subject, no greeting
ceremony. Assume it is read on a phone between two other things.

**Instagram DM** — two or three sentences at most. The first line has to survive
being shown as a preview.

Print all three plainly so they can be copied.

## 4. Offer to log it

Do not log anything on your own, because writing a message is not sending it.
Tell them that once they have actually sent it, this records it and sets the
follow up:

```
venv/Scripts/python.exe scripts/outreach.py --sent "<place_id>" --channel email
```

And when a reply arrives:

```
venv/Scripts/python.exe scripts/outreach.py --answered "<place_id>" --response interested
```
