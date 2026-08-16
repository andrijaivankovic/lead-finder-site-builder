import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lead_search
import lead_store

ROOT = lead_search.ROOT
FORBIDDEN_IN_NAME = re.compile(r'[\\/:*?"<>|]')


class BriefError(Exception):
    pass


def desktop_dir():
    candidates = [Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return Path.home()


def folder_name(business):
    cleaned = FORBIDDEN_IN_NAME.sub("", business).strip().rstrip(".")
    return cleaned or "Business"


def find_lead(place_id):
    for name in lead_store.list_files(ROOT):
        path = lead_store.data_dir(ROOT) / name
        for row in lead_store.load_rows(path):
            if row["place_id"] == place_id:
                return row, path.name
    raise BriefError("No lead with place_id {} in any file under data/.".format(place_id))


def _bullet_list(items, empty="not provided"):
    if not items:
        return "- {}\n".format(empty)
    return "".join("- {}\n".format(item) for item in items)


def _photo_lines(stock_dir):
    if not stock_dir:
        return "- no images collected yet\n"

    sources = Path(stock_dir) / "sources.json"
    if not sources.exists():
        return "- no images collected yet\n"

    payload = json.loads(sources.read_text(encoding="utf-8"))
    lines = []
    for photo in payload.get("photos", []):
        lines.append(
            "- `{}` — {} ({}x{}), by {}, {}\n".format(
                photo["file"],
                photo["description"] or photo["query"],
                photo["width"],
                photo["height"],
                photo["photographer"],
                photo["pexels_url"],
            )
        )
    return "".join(lines) or "- no images collected yet\n"


PROJECT_GUIDE = """# {name}

A demo website being built for {name}, a business that will be approached cold
with the finished result.

## What is here

- `brief.md` — everything about the business and the full instruction for the
  site. Read it before writing a line. The section named **Build prompt** is the
  instruction and it stands on its own.
- `assets/` — licensed photographs grouped by purpose. `assets/sources.json`
  says what each one actually shows and who took it.
- `site/` — where the website goes. It is empty until someone builds it.

## What to do here

Write `index.html`, `style.css` and `script.js` into `site/`. Nothing else in
this folder gets edited.

## Rules that are not negotiable

- Static site only: plain HTML, CSS and JavaScript. No framework, no build step,
  no server. Double clicking `site/index.html` must show the finished site.
- Mobile first. Check 360px wide before anything else.
- Image paths are relative: `../assets/<purpose>/<file>`. Use only filenames
  that exist. Read `assets/sources.json` so a photograph lands in a section it
  actually matches.
- Every visible word is in {language}.
- The name, address and phone in `brief.md` are real. Never change them.
- Opening hours, prices, staff names and reviews are unknown. Write an obvious
  placeholder in {language} and list every placeholder in an HTML comment at the
  bottom of `index.html`. Never invent a review or a person.
- No lorem ipsum anywhere.
"""


def _pitch(lead, problems):
    if not (lead.get("website") or "").strip():
        return (
            "This business has no website at all, so every person who searches for it "
            "online finds nothing."
        )
    if problems:
        return "The business already has {}, and it fails on this: {}".format(
            lead["website"], " ".join(problems)
        )
    return "The business has {}, and it is not obviously broken, so this site has to win on looks and clarity.".format(
        lead["website"]
    )


def _animation_rule(answers):
    if not answers.get("animations", True):
        return (
            "No animation library. Limit motion to short CSS transitions on hover and focus, "
            "and honour prefers-reduced-motion."
        )
    return (
        "Use GSAP with ScrollTrigger, loaded locally rather than from a CDN. Keep it to "
        "entrance reveals on scroll and one deliberate hero moment. Every animation must be "
        "wrapped in gsap.matchMedia so prefers-reduced-motion disables it. Motion must never "
        "delay reading the content."
    )


def render_brief(lead, answers, stock_dir):
    yes_no = lambda flag: "yes" if flag else "no"
    problems = [item for item in (lead.get("website_problems") or "").split("; ") if item]
    colours = answers.get("brand_colors") or []

    return """# Brief — {name}

## The business

| | |
|---|---|
| Name | {name} |
| Address | {address} |
| Phone | {phone} |
| Rating | {rating} |
| Reviews | {review_count} |
| Existing website | {website} |
| Website score | {website_score} |
| Lead score | {score} |
| Google Maps | {maps} |
| place_id | {place_id} |

## Why this business

{why}

## Style direction

{style}

Brand colours: {colours}

## Site language

{language}

## Sections to build

{sections}
## SEO keywords

{keywords}
## Images

All images live in `assets/`. Every one is a Pexels photograph, free for
commercial use. None of them show the real place, so the outreach message must
say the images are temporary and get replaced with the owner's own once they
are interested.

{photos}
## Options chosen

| Option | Answer |
|---|---|
| FAQ section | {faq} |
| Careers section | {careers} |
| Show rating and review count | {reviews} |
| GSAP and ScrollTrigger animations | {animations} |
| Generate AI images and video | {ai_media} |

## Build prompt

Everything below is the instruction for whoever builds the site. It is written
to stand on its own, so it repeats facts from above on purpose.

---

Build a complete one page website for **{name}**, a {trade} in {city}. Write it
into the `site/` folder next to this file. The entry point is
`site/index.html`.

**The pitch this site has to win.** {pitch} The owner has never seen this site
and has not paid for it. It is being sent to them cold, so it has to look like
something they would have paid for. Anything that reads as a template loses the
job.

**Technical constraints, all of them hard.**

- Plain HTML, CSS and JavaScript only. No React, no Vue, no Tailwind, no build
  step, no package manager, no server. Opening `site/index.html` by double
  clicking must show the finished site.
- Three files: `index.html`, `style.css`, `script.js`. No more unless there is a
  real reason.
- Mobile first. Design the phone layout first and let the desktop layout be the
  variation. Test mentally at 360px wide before anything else.
- Every image lives in `../assets/` relative to `site/index.html`. Use the exact
  filenames listed above. Do not invent filenames and do not hotlink anything.
- Add `width`, `height` and `loading="lazy"` to every image below the fold, so
  the page does not jump while it loads.
- `<title>`, `<meta name="description">` and `<meta name="viewport">` are
  mandatory. Those three are exactly what the audit judges a site on, so a site
  built here must not fail its own test.
- Include Open Graph tags, a favicon, and JSON-LD `LocalBusiness` structured
  data filled in with the real name, address and phone from the table above.
- Semantic HTML: one `<h1>`, sections in `<section>`, navigation in `<nav>`,
  contact details in a `<footer>`. Every image needs a real `alt` in
  {language}.
- Colour contrast at least 4.5:1 for body text. Tap targets at least 44px.
- No cookie banner, no analytics, no third party fonts loaded from a CDN. If a
  display font is wanted, pick a system font stack instead.

**Language.** Every word the visitor reads is in {language}. Do not mix
languages. Do not leave lorem ipsum anywhere — write real copy for this
business, in the voice of a {trade} that wants local customers.

**What to invent and what not to.** Address, phone and the business name are
real, take them from the table above and never change them. Opening hours,
prices, staff names and reviews are not known. Where a section needs them,
write an obvious placeholder in {language} that the owner can fill in, and mark
those spots in a `<!-- -->` comment list at the bottom of `index.html` so they
are easy to find. Never invent a fake review or a fake person.

**Sections, in this order.**

{sections}
**Style direction.** {style}

Build the palette from that description{colour_hint}. Pick one accent colour
and use it for every call to action, nothing else. Two typefaces at most.
Generous whitespace, a consistent spacing scale, and a single border radius
used everywhere.

**Animation.** {animation_rule}

**Performance.** The whole page, images included, should feel instant on a
phone. Keep total JavaScript small, defer anything that is not needed for the
first paint, and never block rendering on a script.

**When it is done**, list in your reply: the files created, which placeholders
the owner needs to fill in, and one sentence on what makes this site better than
the situation described in "Why this business".
""".format(
        name=lead["name"],
        address=lead["address"] or "not listed",
        phone=lead["phone"] or "not listed",
        rating=lead["rating"] or "not available",
        review_count=lead["review_count"] or "not available",
        website=lead["website"] or "none",
        website_score=lead["website_score"] or "not checked",
        score=lead["score"],
        maps=lead["google_maps_link"],
        place_id=lead["place_id"],
        why=_bullet_list(problems, "The business has no website at all."),
        style=answers.get("style") or "not described",
        colours=" ".join(colours) or "not known yet",
        trade=answers.get("trade", "local business"),
        city=answers.get("city", "the city"),
        pitch=_pitch(lead, problems),
        animation_rule=_animation_rule(answers),
        colour_hint=(
            ", anchored on the brand colours {}".format(" ".join(colours))
            if colours
            else " and from the photographs in assets/, since no brand colours are known"
        ),
        language=answers.get("language", "srpski"),
        sections=_bullet_list(answers.get("sections")),
        keywords=_bullet_list(answers.get("seo_keywords")),
        photos=_photo_lines(stock_dir),
        faq=yes_no(answers.get("faq", True)),
        careers=yes_no(answers.get("careers", True)),
        reviews=yes_no(answers.get("show_reviews", True)),
        animations=yes_no(answers.get("animations", True)),
        ai_media=yes_no(answers.get("ai_media", True)),
    )


def create(place_id, answers, stock_dir=None, target_root=None):
    lead, source_file = find_lead(place_id)
    base = Path(target_root) if target_root else desktop_dir()
    project = base / folder_name(lead["name"])

    (project / "assets").mkdir(parents=True, exist_ok=True)
    (project / "site").mkdir(parents=True, exist_ok=True)

    copied = 0
    if stock_dir and Path(stock_dir).is_dir():
        import shutil

        for item in Path(stock_dir).iterdir():
            destination = project / "assets" / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
                copied += len(list(destination.rglob("*.jpg")))
            else:
                shutil.copy2(item, destination)

    brief = render_brief(lead, answers, project / "assets")
    (project / "brief.md").write_text(brief, encoding="utf-8")
    (project / "CLAUDE.md").write_text(
        PROJECT_GUIDE.format(name=lead["name"], language=answers.get("language", "srpski")),
        encoding="utf-8",
    )

    return {"folder": project, "lead": lead, "source_file": source_file, "images": copied}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Builds the project folder and brief for one lead.")
    parser.add_argument("place_id", help="The place_id column from the leads CSV")
    parser.add_argument("--info", action="store_true", help="Print the lead as JSON and stop")
    parser.add_argument("--answers", help="JSON file holding the answers to the brief questions")
    parser.add_argument("--stock", help="Folder of collected stock photos to copy into assets/")
    parser.add_argument("--into", help="Where to create the project folder, defaults to the Desktop")
    arguments = parser.parse_args()

    try:
        if arguments.info:
            lead, source_file = find_lead(arguments.place_id)
            print(json.dumps({"lead": lead, "source_file": source_file}, ensure_ascii=False, indent=2))
            return

        if not arguments.answers:
            raise BriefError("Give --answers with the JSON file of answers, or --info to inspect the lead.")

        answers = json.loads(Path(arguments.answers).read_text(encoding="utf-8"))
        result = create(arguments.place_id, answers, arguments.stock, arguments.into)
    except BriefError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    print("\n{}".format(result["lead"]["name"]))
    print("Folder:  {}".format(result["folder"]))
    print("Brief:   {}".format(result["folder"] / "brief.md"))
    print("Images:  {} copied into assets/".format(result["images"]))
    print("Site:    {} (empty, ready to build)\n".format(result["folder"] / "site"))


if __name__ == "__main__":
    main()
