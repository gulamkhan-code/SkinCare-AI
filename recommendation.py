import csv
import os
import re


def get_recommendations(skin_type, concerns):
    """Return a small set of general routine suggestions."""
    skin_type = (skin_type or "").lower()
    concerns = [str(item).lower() for item in (concerns or [])]

    if "oily" in skin_type:
        cleanser = "Gentle Foaming Cleanser"
        moisturizer = "Lightweight Gel Moisturizer"
        sunscreen = "Oil-Free Sunscreen SPF 50"
    elif "dry" in skin_type:
        cleanser = "Hydrating Gentle Cleanser"
        moisturizer = "Ceramide Moisturizer"
        sunscreen = "Hydrating Sunscreen SPF 50"
    else:
        cleanser = "Gentle Daily Cleanser"
        moisturizer = "Balanced Daily Moisturizer"
        sunscreen = "Daily Sunscreen SPF 50"

    recommendations = [
        {
            "name": cleanser,
            "category": "Cleanser",
            "reason": "A gentle first step for a simple skincare routine.",
        },
        {
            "name": moisturizer,
            "category": "Moisturizer",
            "reason": "Helps maintain skin hydration.",
        },
        {
            "name": sunscreen,
            "category": "Sunscreen",
            "reason": "Helps protect skin from UV exposure.",
        },
    ]

    if any("redness" in item for item in concerns):
        recommendations.append({
            "name": "CalmShield Redness Relief Moisturizer",
            "category": "Moisturizer",
            "reason": "Catalog-listed option for redness and sensitive skin.",
        })

    if any(
        "dark circle" in item or "under-eye" in item
        for item in concerns
    ):
        recommendations.append({
            "name": "BrightEyes Under-Eye Cream",
            "category": "Eye Care",
            "reason": "Catalog-listed option for under-eye care.",
        })

    if any(
        "pigmentation" in item or "dark spot" in item
        for item in concerns
    ):
        recommendations.append({
            "name": "GlowTone Dark Spot Serum",
            "category": "Serum",
            "reason": "Catalog-listed option for dark spots and uneven tone.",
        })

    if any("acne" in item for item in concerns):
        recommendations.append({
            "name": "ClearSkin Acne Control Cleanser",
            "category": "Cleanser",
            "reason": "Catalog-listed cleanser for acne-prone skin.",
        })

    # Keep unique product names and cap the list.
    unique = []
    seen = set()

    for product in recommendations:
        key = product["name"].casefold()
        if key not in seen:
            seen.add(key)
            unique.append(product)

    return unique[:4]


def get_routine(skin_type):
    """Build a simple morning and night routine."""
    skin_type = (skin_type or "").lower()

    if "oily" in skin_type:
        cleanser = "Gentle Foaming Cleanser"
        moisturizer = "Lightweight Gel Moisturizer"
        sunscreen = "Oil-Free Sunscreen SPF 50"
        night_serum = "Niacinamide Serum"
    elif "dry" in skin_type:
        cleanser = "Hydrating Gentle Cleanser"
        moisturizer = "Ceramide Moisturizer"
        sunscreen = "Hydrating Sunscreen SPF 50"
        night_serum = "Hydrating Serum"
    else:
        cleanser = "Gentle Daily Cleanser"
        moisturizer = "Balanced Daily Moisturizer"
        sunscreen = "Daily Sunscreen SPF 50"
        night_serum = None

    morning = [cleanser, moisturizer, sunscreen]
    night = [cleanser]

    if night_serum:
        night.append(night_serum)

    night.append(moisturizer)

    return {
        "morning": morning,
        "night": night,
    }


def get_catalog_recommendations(skin_type, concerns, limit=4):
    import csv
    import os

    csv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "products.csv"
    )

    facial_categories = {
        "cleanser", "toner", "serum", "moisturizer",
        "sunscreen", "sheet mask", "clay mask",
        "overnight mask", "eye care", "lip balm"
    }

    skin_type = (skin_type or "uncertain").strip().lower()
    concerns = [
        str(item).strip()
        for item in (concerns or [])
        if str(item).strip()
    ]

    # What the image analysis may report.
    input_terms = {
        "dark_circles": [
            "dark circle", "under-eye", "under eye",
            "puffiness", "eye bag"
        ],
        "acne": [
            "acne", "pimple", "blemish", "blackhead",
            "whitehead", "breakout"
        ],
        "redness": [
            "redness", "red area", "irritation", "sensitivity"
        ],
        "pigmentation": [
            "pigmentation", "dark spot", "uneven tone",
            "dullness", "acne mark"
        ],
        "dryness": [
            "dry", "flaky", "dehydrat", "rough skin"
        ],
        "oiliness": [
            "oiliness", "visible shine", "excess oil",
            "enlarged pore", "oily skin"
        ],
        "texture": [
            "rough texture", "uneven texture", "fine line",
            "wrinkle", "visible scar"
        ],
        "lips": [
            "chapped lips", "lip care"
        ]
    }

    # Words used to match detected concerns to actual catalog fields.
    product_terms = {
        "dark_circles": [
            "dark circle", "under-eye", "under eye",
            "eye care", "caffeine", "tired look", "puffiness"
        ],
        "acne": [
            "acne", "pimple", "blemish", "blackhead",
            "whitehead", "breakout", "salicylic", "bha",
            "tea tree", "acne-prone", "clarifying"
        ],
        "redness": [
            "redness", "cica", "centella", "soothing",
            "aloe", "barrier", "sensitive", "probiotics"
        ],
        "pigmentation": [
            "pigmentation", "dark spot", "uneven tone",
            "brightening", "kojic", "vitamin c",
            "aha", "dullness", "lactic acid"
        ],
        "dryness": [
            "dryness", "dehydration", "hydration",
            "hyaluronic", "ceramide", "moistur",
            "water", "barrier", "flaky"
        ],
        "oiliness": [
            "oiliness", "oil control", "oily",
            "clarifying", "salicylic", "niacinamide",
            "clay", "bha", "pore"
        ],
        "texture": [
            "rough texture", "uneven texture", "fine lines",
            "wrinkle", "scar", "collagen", "aha",
            "lactic acid"
        ],
        "lips": [
            "lip balm", "lip care", "chapped lips"
        ]
    }

    def contains_any(text, words):
        return any(word in text for word in words)

    # Preserve which concerns were actually reported by the AI.
    active_topics = {}

    for concern in concerns:
        text = concern.lower()

        for topic, words in input_terms.items():
            if contains_any(text, words):
                active_topics.setdefault(topic, [])

                if concern not in active_topics[topic]:
                    active_topics[topic].append(concern)

    known_skin_type = (
        any(
            item in skin_type
            for item in ("oily", "dry", "normal", "combination")
        )
        and "uncertain" not in skin_type
        and "unable to determine" not in skin_type
    )

    ranked = []

    with open(
        csv_path,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file, delimiter="\t")

        for row in reader:
            name = (row.get("product_name") or "").strip()
            category = (row.get("category") or "").strip()
            product_skin = (row.get("skin_type") or "").lower()
            product_concern = (row.get("concern") or "").lower()
            ingredients = (row.get("ingredients") or "").lower()
            description = (row.get("description") or "").lower()

            if not name or category.lower() not in facial_categories:
                continue

            score = 0
            matched_topics = []

            # Rank products against each concern reported by the AI.
            for topic, labels in active_topics.items():
                terms = product_terms[topic]
                matched = False

                # The catalog's concern field is the strongest evidence.
                if contains_any(product_concern, terms):
                    score += 10
                    matched = True

                # Product name is also an important matching signal.
                if contains_any(name.lower(), terms):
                    score += 7
                    matched = True

                # Check ingredients for relevant skincare ingredients.
                if contains_any(ingredients, terms):
                    score += 4
                    matched = True

                # Use description as a weaker supporting signal.
                if contains_any(description, terms):
                    score += 2
                    matched = True

                if matched:
                    matched_topics.extend(labels)

            # Match suitability without forcing uncertain skin types.
            if known_skin_type:
                if "all" in product_skin:
                    score += 2

                if "oily" in skin_type:
                    if "oily" in product_skin:
                        score += 5
                    elif "combination" in product_skin:
                        score += 3

                elif "dry" in skin_type:
                    if "dry" in product_skin:
                        score += 5
                    elif "normal" in product_skin:
                        score += 3

                elif "combination" in skin_type:
                    if "combination" in product_skin:
                        score += 5
                    elif "oily" in product_skin:
                        score += 3
                    elif "normal" in product_skin:
                        score += 2

                elif "normal" in skin_type:
                    if "normal" in product_skin:
                        score += 4

            # Basic products remain useful for a general routine.
            if category.lower() == "sunscreen":
                score += 2
            elif category.lower() in {"cleanser", "moisturizer"}:
                score += 1

            ranked.append({
                "score": score,
                "id": row.get("id", ""),
                "name": name,
                "category": category,
                "price": (row.get("price") or "").strip(),
                "ingredients": (row.get("ingredients") or "").strip(),
                "image": (row.get("image") or "").strip(),
                "matched_topics": list(dict.fromkeys(matched_topics))
            })

    # Best concern and skin-type matches come first.
    ranked.sort(
        key=lambda item: (
            -item["score"],
            -len(item["matched_topics"]),
            item["name"].casefold()
        )
    )

    try:
        max_items = max(1, min(int(limit), 6))
    except (TypeError, ValueError):
        max_items = 6

    selected = []
    seen_names = set()
    seen_categories = set()

    # First pass: give priority to variety across categories.
    for product in ranked:
        name_key = product["name"].casefold()
        category_key = product["category"].casefold()

        if name_key in seen_names:
            continue

        if category_key in seen_categories:
            continue

        # When a concern was detected, prioritize matched products.
        if active_topics and not product["matched_topics"]:
            continue

        selected.append(product)
        seen_names.add(name_key)
        seen_categories.add(category_key)

        if len(selected) >= max_items:
            break

    # Second pass: fill remaining slots if needed.
    # This can include a second item from a useful category.
    if len(selected) < max_items:
        for product in ranked:
            name_key = product["name"].casefold()

            if name_key in seen_names:
                continue

            if active_topics and not product["matched_topics"]:
                continue

            selected.append(product)
            seen_names.add(name_key)

            if len(selected) >= max_items:
                break

    recommendations = []

    for product in selected:
        labels = product["matched_topics"]

        if labels:
            reason = (
                "Matched to the reported concern(s): "
                + ", ".join(labels)
                + ". Based on product-catalog details, not a diagnosis."
            )
        else:
            reason = (
                "General skincare routine option based on the "
                "available catalog details."
            )

        recommendations.append({
            "id": product["id"],
            "name": product["name"],
            "category": product["category"],
            "reason": reason,
            "price": product["price"],
            "ingredients": product["ingredients"],
            "image": product["image"]
        })

    print("AI SKIN TYPE:", skin_type)
    print("AI CONCERNS:", concerns)
    print("MATCHED TOPICS:", sorted(active_topics.keys()))
    print("RECOMMENDED:", [p["name"] for p in recommendations])

    return recommendations