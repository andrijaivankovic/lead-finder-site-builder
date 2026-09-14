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

Stock is the floor, not the ceiling. A business with no website still has a
Google Maps listing and usually an Instagram page, so you can save a few of
their own photographs into a folder and hand it over as well. Those are sorted
by what is in them, mapped to where they belong on the page, and they take that
place from the stock ones: their storefront becomes the image at the top and
the stock one is dropped, while stock keeps the backgrounds nobody photographs
for themselves. A logo among them also sets the palette.

**5. Build.** It writes a folder, on your Desktop unless you point it somewhere
else, containing everything the website needs: the business details, the visual
direction, the list of sections, search keywords for that trade and city, the
photographs, and a complete instruction for building the site. Then the site
gets built into that folder.

**6. Write.** It drafts three versions of the outreach message, one for email,
a shorter one for Viber or WhatsApp, and a very short one for an Instagram
message. It records who you contacted and reminds you who has not answered after
four days.

It does not send anything. See "Things it will not do" below.

## Requirements

Python 3.11 or newer. Nothing else. There is no database to install, no server
to configure, and no account you must have before you can try it.

It also runs on Python 3.9, which is what macOS still ships, with one cosmetic
cost: `requests` prints a `urllib3 ... LibreSSL` warning above every command.
The warning is harmless, and it disappears if you install a current Python from
python.org or Homebrew and build the `venv` with that one instead.

## Installing it

Open a terminal and run these four commands, on macOS and Linux:

```bash
git clone https://github.com/andrijaivankovic/lead-finder-site-builder.git
cd lead-finder-site-builder
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
```

On Windows the first two are the same and the last two differ, because the
launcher there is called `python` and the private copy lands in a different
folder. These two work in both Command Prompt and PowerShell:

```
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

### What `venv` is, and why every command starts with it

Python programs rely on libraries, which are pieces of code other people wrote
and shared. This project uses six of them.

Installing libraries the ordinary way puts them in one shared pile for your whole
computer. That works until two projects need different versions of the same
library, at which point one of them breaks and the reason is not obvious. It also
does not stay still: libraries change on purpose, and code written against one
version can stop running on the next. The problem rarely bites today. It bites a
year from now, when you come back to a project that used to work.

The third command, `python3 -m venv venv`, creates a folder called `venv` inside
this project holding its own private copy of Python and its own libraries.
Nothing outside that folder is touched, and nothing outside it can break what is
inside. Together with `requirements.txt`, which lists the exact libraries this
project needs, it is what makes the project still run next year.

The trade is that you have to point at that private copy on purpose, rather than
typing a plain `python`. Typing plain `python` would reach for the shared pile,
which does not have this project's libraries, and you would see an error saying
a module could not be found. On macOS it usually fails one step earlier, with
`command not found`, because there is no `python` on the system at all, only
`python3`. The `run` launcher below does that pointing for you.

`venv` is part of Python itself, so there is nothing extra to install. Other
tools do the same job more comfortably, `uv` and `poetry` among them, but each is
a separate program you would have to install first, and this project would rather
run on a plain Python and nothing else.

It also makes removing the project simple. Delete the folder and it is gone.
Nothing was ever installed anywhere else on your computer.

### The `run` launcher

`run` hands whatever you type after it to the Python inside `venv`, so you do
not have to write that path out every time. You can now run a search:

```bash
./run scripts/find_leads.py "bakery Novi Sad"
```

On Windows the launcher is `run.bat`. Command Prompt finds it in the current
folder on its own. PowerShell, like macOS and Linux, deliberately does not, so
there it needs `.\` in front:

```
run.bat scripts/find_leads.py "bakery Novi Sad"
.\run.bat scripts/find_leads.py "bakery Novi Sad"
```

The first line is for Command Prompt, the second for PowerShell, and every
`./run` command further down changes the same way. If you would rather see what
is happening, this is the same command on macOS and Linux:

```
venv/bin/python scripts/find_leads.py "bakery Novi Sad"
```

Both work. If `./run` says `permission denied`, you downloaded a ZIP rather
than cloning, and a ZIP drops the flag that marks a file runnable: run
`chmod +x run` once, or type `sh run` instead.

The search above needs no account and no key, using OpenStreetMap. Read on if
you want the better data.

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

Every link in that list goes into every message. The `what` line decides the
order they appear in, so a grill owner reads the grill site before the bakery,
and it doubles as the label next to each link.

Those two are yours rather than the project's, so there is a second place for
them: create `config.local.yaml` next to `config.yaml` and put them there
instead. It is laid over the public settings when the tool starts and is
ignored by Git, so a `git pull` never collides with your name and a push never
carries it.

If you will never update this project or share the folder, `config.yaml` is
fine and this file is not needed. [SETUP.md](SETUP.md#3-your-own-details)
covers it in full.

## Using it

### Searching from the terminal

```bash
./run scripts/find_leads.py "bakery Novi Sad"
./run scripts/find_leads.py "dentist Berlin" --limit 60
```

Add `--no-audit` to skip checking existing websites, which makes a search much
faster when you only want to see whether a place is worth searching at all.

The first words name the kind of business and the last ones the place. Without
a Google key, the kind is looked up in `osm_categories` in `config.yaml`, and it
does not matter whether you type it in Latin or Cyrillic, or with or without
č, ć, š, ž and đ: `pekara`, `пекара` and `kafić` each find every bakery or cafe
in that place. A word that is not on the list searches business names instead.

### Checking one website on its own

```bash
./run scripts/audit_site.py example.com
```

You get a score out of 100 and a list of problems written as sentences you can
quote to the owner.

### The table in your browser

```bash
./run app.py
```

Then open `http://localhost:5000`. This runs entirely on your own computer.
Nothing is published and no one else can reach it.

On macOS, port 5000 is also where AirPlay Receiver listens. If the page refuses
to load, or starting it fails with `Address already in use`, turn AirPlay
Receiver off in System Settings, under General, AirDrop & Handoff.

The page shows your results as a table you can sort by clicking any column. You
can filter to businesses without a website, set a minimum rating or review
count, and set a status on each row, which is saved the moment you choose it.
Each row links to the business on the map, to its website if it has one, and to
a company register search for finding the owner.

### Preparing a website

The three commands below are Claude Code commands. You type them in a Claude
Code session opened inside this folder.

They live in `commands/`, which Claude Code does not read on its own, so link
them into `.claude/commands/` once after cloning. From the project folder on
macOS and Linux:

```bash
mkdir -p .claude/commands
for f in commands/*.md; do ln -s "../../$f" .claude/commands/; done
```

That folder is ignored by Git. Because these are links and not copies, an
update that changes a command changes it here too. Open a new session
afterwards so the commands are picked up.

On Windows a link needs Developer Mode or an administrator prompt. Without
either, copy the three files instead, and copy them again after each update:

```
mkdir .claude\commands
copy commands\*.md .claude\commands\
```

```
/build-brief <place_id or business name>
```

Looks the business up on the map and on its social pages, asks you a handful of
questions about it, including the colours it already uses and whether you have
gathered any of its own photographs, collects what is missing from Pexels, and
creates a folder containing `brief.md`, an `assets` folder, and an empty `site`
folder.

That folder lands on your Desktop. To keep client work somewhere else, set
`brief.output_dir`, in `config.local.yaml` if the path is personal to you, as
[SETUP.md](SETUP.md#3-your-own-details) explains:

```yaml
brief:
  output_dir: "~/Developer/sites"
```

The `~` is expanded, and the folder is created if it does not exist.

```
/build-site "Business Name"
```

Reads that brief, builds the website into `site`, then serves it and checks it
at phone width and desktop width before telling you it is done.

```
/draft-outreach <place_id or name>
```

Shows you who is overdue a follow up, then writes the three versions of the
message for the business you named.

The button labelled "Create brief" next to each row in the browser copies the
first command for you, already filled in with the right business.

### Keeping track of who you contacted

Nothing is recorded when a message is drafted, because drafting is not sending.
Once you have actually sent one, record it:

```bash
./run scripts/outreach.py --sent "Business Name" --channel email
```

The business can be given by its name or by its `place_id`. If two businesses
share the name, the command says so and asks for the `place_id` instead.
`--channel` is one of `email`, `viber`, `whatsapp` or `instagram`, the list kept
in `outreach.channels` in `config.yaml`.

When a reply comes in:

```bash
./run scripts/outreach.py --answered "Business Name" --response interested
```

`--response` is `interested`, `declined` or `"no answer"`. To list everyone who
has not replied within `outreach.follow_up_days` of being contacted, four days
by default:

```bash
./run scripts/outreach.py --due
```

The record lives in `data/outreach.csv`.

## Where your results are kept

Every search writes a file into the `data` folder, named after what you
searched for, for example `data/leads_bakery-novi-sad.csv`. Cyrillic is spelled
out in Latin for the name, so `пекара Нови Сад` and `pekara Novi Sad` are the
same search and share one file.

That file is the database. There is no database.

A `.csv` file is a plain table that opens in Excel, in Google Sheets, or in any
text editor. Run the same search again a month later and the tool updates the
existing file rather than replacing it: business details are refreshed, and
anything you typed by hand is left exactly as you wrote it. That covers the
status, and the address, phone and opening hours where the source has none of
its own to offer.

### What `place_id` is

Every business in your results carries a `place_id`. That is the identifier the
data source uses for that one particular business. From Google it looks like
`ChIJN1t_tDeuEmsRUsoyG83frY4`. From OpenStreetMap it looks like
`osm:node/4031258789`.

It exists because names are not reliable. Three businesses in the same city can
all be called Caribic. The same business can be spelled two different ways a
month apart, because a volunteer corrected the map. Addresses are often missing
altogether.

The identifier is what lets the tool run the same search again next month and
recognise that a row is the same business as before, so it can refresh the score
while leaving what you typed by hand exactly as it was. Without it, a business
whose name had been corrected would come back as a second row and you would
contact the same owner twice.

You never have to type it or read it. You only copy it when a command asks for
one, and the "Create brief" button next to each row does that for you.

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
belong to the owners and the customers who took them. The tool never downloads
them at all: to see what a place looks like, it gives you a link to open, the
same as everywhere else. Every image that goes on a site comes from Pexels or
from the client.

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

What remains are the places where judgement is needed: describing what a place
looks like, saying what is in a photograph the owner took, writing the website,
and writing the message. Those are the Claude Code commands.

If you use a different assistant, `CLAUDE.md` in this folder holds the project
rules, and the files under `commands` hold the three procedures. Both are plain
English. Hand them to your assistant and it can follow them.

## Licence

MIT. See [LICENSE](LICENSE).

Photographs downloaded from Pexels through this tool stay under the Pexels
licence. Each such folder ships a `sources.json` naming the photographer and
linking the page the photograph came from. Photographs a business supplies
remain theirs.
