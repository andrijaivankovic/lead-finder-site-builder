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


def render_brief(lead, answers, stock_dir):
    yes_no = lambda flag: "yes" if flag else "no"
    problems = [item for item in (lead.get("website_problems") or "").split("; ") if item]

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

## Build rules

- Static site only: plain HTML, CSS and JavaScript. No server, no build step,
  no framework. It has to run by double clicking `index.html`.
- Mobile first. It must be usable on a phone before it is pretty on a laptop.
- Every image path points inside `assets/`.
- Write all visible text in {language}.
- Keep the page under a second on a normal connection: compress images, no
  large libraries beyond GSAP if animations were chosen.
- Include `<title>`, `<meta name="description">` and `<meta name="viewport">`.
  Those are the three things the existing site is being judged on.

## Output

Write the finished site into `site/`, entry point `site/index.html`.
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
        colours=" ".join(answers.get("brand_colors") or []) or "not known yet",
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
