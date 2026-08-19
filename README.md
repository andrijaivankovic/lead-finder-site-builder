# lead-finder-site-builder

Most prospecting tools stop at a list of businesses. This one carries a single
business all the way to a finished website and a written message you can send.

## What problem this solves

Plenty of small local businesses have no website at all, or one that was built
years ago and no longer works on a phone. They are good customers for anyone who
builds websites, but finding them takes hours of walking around a city, looking
things up, and writing notes.

This tool does that part for you. You type what you are looking for and where,
for example `bakery Novi Sad`, and it returns a ranked list of businesses,
putting the ones that need a website most at the top. From there it will check
what they already have, gather photographs you are legally allowed to use, write
a full instruction for the website, and draft the message you send the owner.

You still make every real decision. The tool prepares the work.

## The six steps

```
find  ->  rank  ->  check the old site  ->  gather photos  ->  build  ->  write
```

**1. Find.** You search for a trade and a place. The tool asks either Google or
OpenStreetMap and brings back local businesses, including the one thing that
matters most: whether they have a website.

**2. Rank.** Every business gets a score. No website is worth 50 points. A
website that exists but is in bad shape is worth 30. A good rating adds 20, a
healthy number of reviews adds 20, having a phone number adds 10, and almost no
reviews takes 30 away.

The idea behind those numbers: a business with 200 reviews and a 4.6 rating that
has no website is clearly doing well but is invisible online, and that is the
ideal person to approach. A business with six reviews is either brand new or on
its way out, and is not worth your afternoon.

Every one of those numbers lives in `config.yaml` and you can change them
without touching any code.

**3. Check the old site.** For every business that already has a website, the
tool opens it and scores it from 0 to 100. It looks at whether the site opens at
all, whether it has a security certificate, whether it adapts to a phone screen,
how long it takes to load, how many years since it was last touched, what it was
built with, and whether it has the basics that search engines need.

Each problem it finds comes back as a plain sentence you can put straight into a
message, for example "the site does not adapt to phones, and around 70% of
people look you up on a phone".

A bad site scores lower than 60, which adds 30 points to that business and moves
it up your list. So the ranking covers both people who have nothing and people
who have something broken.

**4. Gather photographs.** Once the tool knows the trade, for example a pizzeria
or a dentist, it already knows what to look for. `config.yaml` holds a ready set
of searches for each trade, split by where the photographs belong on the page:
the image at the top, the gallery, section backgrounds, the interior.

Those searches go to Pexels, whose photographs are free to use commercially, so
they can go straight onto a demo site. Every folder gets a `sources.json` naming
the photographer and linking the original.

Nothing has to be described and no account is needed beyond the Pexels key. If
you do want the images closer to one particular place, you can add a few words
such as "modern, white, lots of glass" and the search narrows. Skipping that is
the normal case.

**5. Build.** It writes a folder on your Desktop containing everything the
website needs: the business details, the visual direction, the list of sections,
search keywords for that trade and city, the photographs, and a complete
instruction for building the site. Then the site gets built into that folder.

**6. Write.** It drafts three versions of the outreach message, one for email,
a shorter one for Viber or WhatsApp, and a very short one for an Instagram
message. It records who you contacted and reminds you who has not answered after
four days.

It does not send anything. See "Things it will not do" below.

## Requirements

Python 3.11 or newer. Nothing else. There is no database to install, no server
to configure, and no account you must have before you can try it.

## Installing it

Open a terminal and run these four commands.

```bash
git clone https://github.com/andrijaivankovic/lead-finder-site-builder.git
cd lead-finder-site-builder
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt
```

The third command creates a private folder called `venv` that holds this
project's libraries, so it cannot interfere with anything else on your computer.
That is why every command below starts with `venv/Scripts/python.exe` instead of
plain `python`.

On macOS and Linux that path is `venv/bin/python` instead.

You can now run a search:

```bash
venv/Scripts/python.exe scripts/find_leads.py "bakery Novi Sad"
```

This works immediately with no account and no key, using OpenStreetMap. Read on
if you want the better data.

## Adding your API keys

Two services can be connected. Neither is required to start.

**Pexels** provides the photographs. It is free, has no paid tier, and never
asks for a card.

**Google Places** provides better business data, in particular ratings and
review counts, which two of the five ranking rules depend on. Without it the
tool uses OpenStreetMap, which is free but has no ratings, so the ordering is
rougher.

Create the file that holds your keys:

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste your keys after the equals signs. The
file is ignored by Git and will never be uploaded anywhere.

[SETUP.md](SETUP.md) walks through creating both accounts, click by click,
including the quota that protects you from being charged. Read the Google
section before running anything against Google.

## Adding your details for the outreach messages

The messages sign off with your name and link to websites you have built. Put
those in `config.yaml`, under `outreach`:

```yaml
outreach:
  sender_name: "Your Name"
  portfolio_links:
    - url: "https://a-site-you-built.example/"
      what: "cafe, warm and quiet, one page"
```

The `what` line matters. The tool picks the link closest to the business it is
writing to, so a grill owner sees the grill site rather than the bakery.

If you plan to pull future updates of this project, put those values in a file
called `config.local.yaml` instead, using the same shape. That file is ignored
by Git, so updates will never conflict with your details.

## Using it

### Searching from the terminal

```bash
venv/Scripts/python.exe scripts/find_leads.py "bakery Novi Sad"
venv/Scripts/python.exe scripts/find_leads.py "dentist Berlin" --limit 60
```

Add `--no-audit` to skip checking existing websites, which makes a search much
faster when you only want to see whether a place is worth searching at all.

### Checking one website on its own

```bash
venv/Scripts/python.exe scripts/audit_site.py example.com
```

You get a score out of 100 and a list of problems written as sentences you can
quote to the owner.

### The table in your browser

```bash
venv/Scripts/python.exe app.py
```

Then open `http://localhost:5000`. This runs entirely on your own computer.
Nothing is published and no one else can reach it.

The page shows your results as a table you can sort by clicking any column. You
can filter to businesses without a website, set a minimum rating or review
count, and set a status on each row, which is saved the moment you choose it.
Each row links to the business on the map, to its website if it has one, and to
a company register search for finding the owner.

### Preparing a website

The three commands below are Claude Code commands. You type them in a Claude
Code session opened inside this folder.

```
/build-brief <place_id>
```

Asks you a handful of questions about the business, collects the photographs,
and creates a folder on your Desktop containing `brief.md`, an `assets` folder,
and an empty `site` folder.

```
/build-site "Business Name"
```

Reads that brief, builds the website into `site`, then serves it and checks it
at phone width and desktop width before telling you it is done.

```
/draft-outreach <place_id>
```

Shows you who is overdue a follow up, then writes the three versions of the
message for the business you named.

The button labelled "Create brief" next to each row in the browser copies the
first command for you, already filled in with the right business.

## Where your results are kept

Every search writes a file into the `data` folder, named after what you
searched for, for example `data/leads_bakery-novi-sad.csv`.

That file is the database. There is no database.

A `.csv` file is a plain table that opens in Excel, in Google Sheets, or in any
text editor. Run the same search again a month later and the tool updates the
existing file rather than replacing it: business details are refreshed, but any
status you typed by hand is left exactly as you wrote it.

### Why a plain file instead of a real database

A database is worth its complexity when several people write to it at once, when
there are hundreds of thousands of records, or when you need to ask complicated
questions of the data. None of that applies here. You are one person, on one
computer, with a few thousand rows at most.

What a plain file gives you instead:

- You can open it and read it. When something looks wrong, you see it with your
  own eyes rather than needing a program to look for you.
- You can edit it by hand. The status column is meant to be typed into, and a
  spreadsheet is the natural place to do that.
- Backing up is copying a file. Sending your results to someone is sending a
  file.
- There is nothing to install, nothing to start, and nothing to migrate when a
  column is added.

The honest drawbacks: if you leave the file open in Excel, Windows locks it and
the tool cannot write, so it will tell you to close Excel and try again. And
everything in the file is text, so the code converts numbers on the way in and
out.

If this ever grows past ten thousand businesses, or two people start using it at
once, a database becomes the right answer. Until then it would be solving a
problem you do not have.

## Costs and staying inside the free allowance

Pexels is free with no card involved.

Google is different and deserves care. Google will not answer at all until you
have added a card, and there is no way around that. What protects you is a
quota.

The tool asks Google for phone numbers, ratings and review counts. Those are
Google's more expensive fields, which puts each search in the tier with the
smallest free monthly allowance, around 1,000 calls per month. This project
therefore stops itself at 900 calls per month, counted in `data/usage.json`.

That counter is your second line of defence, not your first. Set a daily quota
in the Google Cloud Console as well, following
[SETUP.md](SETUP.md#2-google-cloud--places-api-new). Only the quota can actually
refuse a call. The counter in this tool can only stop this tool, and a budget
alert emails you without stopping anything.

For scale, one search that pulls its full results costs 3 calls and returns up to
60 businesses, so 900 calls is roughly 300 full searches a month.

## Things it will not do, on purpose

**It never sends a message.** It writes drafts, and you send them yourself from
your own account. The project holds no password, token or login for email,
Viber, WhatsApp or Instagram, and it should never be given one. You log a
message as sent after you have actually sent it.

**Google's photographs never end up on a website you build.** Those pictures
belong to the owners and the customers who took them. The tool downloads them
only so you can see what a place looks like. Every image that goes on a site
comes from Pexels or from the client.

**Nothing is scraped.** Not Google Maps, not the company register. The tool
builds links for a human to click.

**Google's terms allow their data to be kept for 30 days at most**, with one
exception: the `place_id`, the identifier of a business, may be kept forever.
Treat the files in `data` as a working copy, not an archive.

## Using it with something other than Claude Code

Most of this project has nothing to do with any assistant.

Every Python script is an ordinary command line program. Searching, ranking,
checking websites, downloading photographs, sorting images, the record of who
you contacted, and the whole browser interface all run on their own. You can use
them from a plain terminal with no assistant at all.

What remains are the three places where judgement is needed: describing what a
place looks like, writing the website, and writing the message. Those are the
Claude Code commands.

If you use a different assistant, `CLAUDE.md` in this folder holds the project
rules, and the files under `commands` hold the three procedures. Both are plain
English. Hand them to your assistant and it can follow them.

## Licence

MIT. See [LICENSE](LICENSE).

Photographs downloaded through this tool stay under the Pexels licence. Each
folder of images ships a `sources.json` naming the photographer and linking the
page the photograph came from.
