def calculate_score(lead, settings):
    points = settings["scoring"]
    thresholds = settings["thresholds"]
    total = 0

    website = (lead.get("website") or "").strip()
    if not website:
        total += points["no_website"]
    elif lead.get("website_is_poor"):
        total += points["poor_website"]

    rating = lead.get("rating")
    if rating is not None and rating >= thresholds["good_rating"]:
        total += points["good_rating"]

    reviews = lead.get("review_count")
    if reviews is not None:
        if reviews >= thresholds["many_reviews"]:
            total += points["many_reviews"]
        elif reviews >= thresholds["some_reviews"]:
            total += points["some_reviews"]
        elif reviews < thresholds["few_reviews"]:
            total += points["few_reviews"]

    if (lead.get("phone") or "").strip():
        total += points["has_phone"]

    return total


def _ranking_key(lead):
    website_score = lead.get("website_score")
    return -lead["score"], -1 if website_score is None else website_score


def add_scores(leads, settings):
    for lead in leads:
        lead["score"] = calculate_score(lead, settings)
    return sorted(leads, key=_ranking_key)
