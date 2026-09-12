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


def output_dir(settings):
    configured = (settings["brief"].get("output_dir") or "").strip()
    if configured:
        return Path(configured).expanduser()
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


def check_sorted(folder, settings):
    manifest = Path(folder) / "assets.json"
    if not manifest.exists():
        return

    images = json.loads(manifest.read_text(encoding="utf-8")).get("images", [])
    categories = [(image.get("category") or "").strip().lower() for image in images]

    blank = categories.count("")
    if blank:
        raise BriefError(
            "{} of {} images in {} have no category yet, so nobody has said what is in "
            "them. Run sort_assets.py on that folder, fill the categories in, then run "
            "it again with --apply.".format(blank, len(images), folder)
        )

    purposes = settings["asset_sorting"].get("purposes", {})
    unmapped = sorted({name for name in categories if name not in purposes})
    if unmapped:
        raise BriefError(
            "asset_sorting.purposes in config.yaml has no entry for {}, so there is "
            "nowhere on the page to put those photographs.".format(", ".join(unmapped))
        )


def _client_photos(assets_dir, settings):
    manifest = Path(assets_dir) / "assets.json"
    if not manifest.exists():
        return []

    purposes = settings["asset_sorting"].get("purposes", {})
    images = json.loads(manifest.read_text(encoding="utf-8")).get("images", [])

    check_sorted(manifest.parent, settings)

    photos = []
    for image in images:
        category = image["category"].strip().lower()
        photos.append(
            {
                "file": image["file"],
                "category": category,
                "purpose": purposes[category],
                "description": image.get("description") or category,
                "width": image.get("width", 0),
                "height": image.get("height", 0),
            }
        )
    return photos


def _stock_photos(assets_dir, covered):
    sources = Path(assets_dir) / "sources.json"
    if not sources.exists():
        return []

    payload = json.loads(sources.read_text(encoding="utf-8"))
    return [photo for photo in payload.get("photos", []) if photo.get("purpose") not in covered]


def _image_rule(theirs, stock):
    if not theirs:
        return (
            "Every one is a Pexels photograph, free for commercial use. None of them show\n"
            "the real place, so the outreach message must say the images are temporary and\n"
            "get replaced with the owner's own once they are interested."
        )

    lines = [
        "The ones marked \"the client's own\" are the business's own photographs. They are",
        "real, they show the real place, and they are not placeholders. Never describe them",
        "as temporary and never swap one for a stock photograph.",
    ]
    if stock:
        lines.append("")
        lines.append(
            "The ones marked \"stock\" are Pexels photographs filling what the client did not"
        )
        lines.append(
            "supply. Those are temporary, and the outreach message has to say so without"
        )
        lines.append("implying the same about their own.")
    if any(photo["purpose"] == "logo" for photo in theirs):
        lines.append("")
        lines.append(
            "The one marked \"logo\" is their logo. It belongs in the header and as the"
        )
        lines.append("favicon, never in the gallery.")
    return "\n".join(lines)


def _photo_lines(theirs, stock):
    lines = []
    for photo in theirs:
        lines.append(
            "- `{}` — {}, the client's own. {} ({}x{})\n".format(
                photo["file"],
                photo["purpose"],
                photo["description"],
                photo["width"],
                photo["height"],
            )
        )
    for photo in stock:
        lines.append(
            "- `{}` — {}, stock. {} ({}x{}). Pexels, by {}, {}\n".format(
                photo["file"],
                photo.get("purpose", "gallery"),
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
- `assets/` — the photographs. Some are stock, some may be the business's own.
  `brief.md` lists every one of them under **Images**, with where it belongs on
  the page and which of the two it is. That list is the authority, not the
  folder names.
- `site/` — where the website goes. It is empty until someone builds it.

## What to do here

Write `index.html`, `style.css` and `script.js` into `site/`. Nothing else in
this folder gets edited.

## Rules that are not negotiable

- The stack is decided in `brief.md` under **Build prompt**. Follow it. Whatever
  it says, the production build has to end up as a static bundle that runs on
  any host with no server behind it.
- Serve the site and look at it before saying it is finished. Never hand over a
  page nobody has opened.
- Mobile first. Check 360px wide before anything else.
- Image paths are relative: `../assets/` followed by the path **Images** gives
  for that photograph, written exactly as it appears there. Do not guess a path
  from a folder name: a photograph sitting in `exterior/` belongs at the top of
  the page, and the brief is what says so.
- Every visible word is in {language}.
- These are real and never change:
  {known_facts}.
- {unknown_facts} are unknown. Write an obvious
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


STATIC_STACK_RULES = """- Plain HTML, CSS and JavaScript only. No framework, no build step, no package
  manager, no server. Opening `site/index.html` by double clicking must show the
  finished site.
- Three files: `index.html`, `style.css`, `script.js`. No more unless there is a
  real reason."""

BUILT_STACK_RULES = """- Built with {stack}, set up inside `site/`.
- Whatever the stack, the production build must come out as a static bundle that
  can be dropped on any host with no server behind it. If the chosen stack
  cannot do that, use plain HTML instead and say why.
- Keep the dependency list to what the site genuinely needs. Every extra package
  is weight on a page whose whole point is being faster than what the business
  has now.
- Write `site/README.md` with the exact commands to install, run and build, so
  the folder works months later without anyone remembering anything.
- Never commit `node_modules`."""


def _stack_rules(answers):
    if not answers.get("stack_needs_a_build"):
        return STATIC_STACK_RULES
    return BUILT_STACK_RULES.format(stack=_stack_name(answers))


def _stack_name(answers):
    return (answers.get("stack") or "").strip() or "Plain HTML, CSS and JavaScript"


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


def _fact_split(lead):
    if (lead.get("opening_hours") or "").strip():
        return (
            "Address, phone, opening hours and the business name",
            "Prices, staff names and reviews",
        )
    return (
        "Address, phone and the business name",
        "Opening hours, prices, staff names and reviews",
    )


def render_brief(lead, answers, assets_dir, settings):
    yes_no = lambda flag: "yes" if flag else "no"
    problems = [item for item in (lead.get("website_problems") or "").split("; ") if item]
    colours = answers.get("brand_colors") or []
    theirs = _client_photos(assets_dir, settings)
    stock = _stock_photos(assets_dir, {photo["purpose"] for photo in theirs})

    return """# Brief — {name}

## The business

| | |
|---|---|
| Name | {name} |
| Address | {address} |
| Phone | {phone} |
| Opening hours | {hours} |
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

All images live in `assets/`. Each line below says where the photograph
belongs on the page and where it came from.

{image_rule}

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

**Stack: {stack}.** {stack_reason}

**Technical constraints, all of them hard.**

{stack_rules}
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

**What to invent and what not to.** {known_facts} are
real, take them from the table above and never change them. {unknown_facts} are not known. Where a section needs them,
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

**When it is done**, serve the site and look at it. Never hand it over unseen.
Open it at 360px wide first, then at desktop width, read the browser console for
errors, and confirm every image actually loads. Fix what you find, then show a
screenshot at both widths.

Then list in your reply: the files created, which placeholders the owner needs
to fill in, and one sentence on what makes this site better than the situation
described in "Why this business".
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
        hours=lead.get("opening_hours") or "not listed",
        known_facts=_fact_split(lead)[0],
        unknown_facts=_fact_split(lead)[1],
        stack=_stack_name(answers),
        stack_reason=answers.get("stack_reason", "Chosen as the default."),
        stack_rules=_stack_rules(answers),
        pitch=_pitch(lead, problems),
        animation_rule=_animation_rule(answers),
        colour_hint=(
            ", anchored on the brand colours {}".format(" ".join(colours))
            if colours
            else " and from the photographs in assets/, since no brand colours are known"
        ),
        language=answers.get("language", "English"),
        sections=_bullet_list(answers.get("sections")),
        keywords=_bullet_list(answers.get("seo_keywords")),
        photos=_photo_lines(theirs, stock),
        image_rule=_image_rule(theirs, stock),
        faq=yes_no(answers.get("faq", True)),
        careers=yes_no(answers.get("careers", True)),
        reviews=yes_no(answers.get("show_reviews", True)),
        animations=yes_no(answers.get("animations", True)),
        ai_media=yes_no(answers.get("ai_media", True)),
    )


def create(place_id, answers, stock_dirs=None, target_root=None):
    lead, source_file = find_lead(place_id)
    typed = {
        column: answers[column].strip()
        for column in lead_store.TYPED_FIELDS
        if (answers.get(column) or "").strip() and not (lead.get(column) or "").strip()
    }
    if typed:
        lead.update(typed)
        lead_store.update_fields(lead_store.data_dir(ROOT) / source_file, place_id, typed)

    settings = lead_search.load_settings()
    answers.setdefault("language", settings["brief"]["default_language"])
    base = Path(target_root).expanduser() if target_root else output_dir(settings)
    project = base / folder_name(lead["name"])

    (project / "assets").mkdir(parents=True, exist_ok=True)
    (project / "site").mkdir(parents=True, exist_ok=True)

    copied = 0
    for folder in stock_dirs or []:
        if not Path(folder).expanduser().is_dir():
            raise BriefError("{} is not a folder.".format(folder))
        check_sorted(Path(folder).expanduser(), settings)

        import shutil

        for item in Path(folder).expanduser().iterdir():
            destination = project / "assets" / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
                copied += len(list(destination.rglob("*.jpg")))
            else:
                shutil.copy2(item, destination)

    brief = render_brief(lead, answers, project / "assets", settings)
    (project / "brief.md").write_text(brief, encoding="utf-8")
    (project / "CLAUDE.md").write_text(
        PROJECT_GUIDE.format(
            name=lead["name"],
            language=answers.get("language", "English"),
            known_facts=_fact_split(lead)[0],
            unknown_facts=_fact_split(lead)[1],
        ),
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
    parser.add_argument(
        "--stock",
        action="append",
        help="Folder of photographs to copy into assets/, repeatable",
    )
    parser.add_argument("--into", help="Where to create the project folder, overriding brief.output_dir")
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
