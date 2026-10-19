
import base64
import json
import os

import cv2

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL = "gemini-3.1-flash-lite"


SIGN_LABELS = {
    "under_eye_dark_circles": "Possible under-eye dark circles",
    "uneven_pigmentation": "Possible dark pigmentation",
    "visible_redness": "Possible visible redness",
    "acne_like_spots": "Possible acne-like spots",
    "dry_looking_areas": "Possible dry-looking skin",
}


def failure(message, status="error"):
    return {
        "skin_type": "Uncertain",
        "concerns": [message],
        "analysis_note": (
            "Experimental AI observations from a photograph. "
            "Not a medical diagnosis."
        ),
        "analysis_explanation": "",
        "analysis_status": status,
    }


def call_gemini(prompt, image_base64):
    """Send the prompt and face image to Gemini."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the .env file."
        )

    client = genai.Client(api_key=api_key)

    image_part = types.Part.from_bytes(
        data=base64.b64decode(image_base64),
        mime_type="image/jpeg",
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt, image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )

    raw_text = response.text

    if not raw_text:
        raise ValueError("Gemini returned an empty response.")

    result = json.loads(raw_text)

    if not isinstance(result, dict):
        raise ValueError("AI response must be a JSON object.")

    return result


def analyze_concerns(image_base64):
    """Detect only the five requested visible concerns."""

    prompt = """
Analyze only the attached face photograph for a skincare app.

Return ONLY valid JSON:
{
  "face_visible": true,
  "image_quality": "good",
  "signs": {
    "under_eye_dark_circles": false,
    "uneven_pigmentation": false,
    "visible_redness": false,
    "acne_like_spots": false,
    "dry_looking_areas": false
  },
  "explanation": "Short description of visible evidence"
}

Assess these five visible skin signs independently:

- under_eye_dark_circles: Clearly visible brown, grey, or
  purplish discoloration beneath the eyes compared with
  nearby cheek skin. Exclude normal shadows, eye hollows,
  puffiness alone, and lighting effects.

- uneven_pigmentation: Distinct irregular darker patches
  compared with surrounding skin. Exclude shadows, natural
  skin-tone variation, makeup, and lighting artifacts.

- visible_redness: Clearly red or pink-looking skin areas.
  Exclude warm lighting, makeup, and camera color shifts.

- acne_like_spots: Visible pimples, raised bumps, or
  inflamed spots. Exclude flat dark marks, freckles,
  pores, and pigmentation alone.

- dry_looking_areas: Clearly visible flaking, peeling,
  roughness, or scaly patches. Do not infer dryness from
  lack of shine alone.

Multiple signs can coexist. Analyze only the current image.
Set each sign true only when reasonably visible; otherwise
set false. Do not diagnose conditions or infer causes.

face_visible must be true only if a human face is visible.
image_quality must be exactly "good", "poor", or "uncertain".
Use poor or uncertain when the image cannot be assessed
reliably. Return valid JSON only using the required schema.
"""

    return call_gemini(prompt, image_base64)


def analyze_skin_type(image_base64):
    """Estimate one of three primary skin types from visible evidence."""

    prompt = """
Analyze only the attached face photograph.

Return ONLY valid JSON:
{
  "skin_type": "Normal",
  "explanation": "Brief visible evidence",
  "image_reliable": true
}

Choose exactly one:
Oily, Dry, Normal, or Uncertain.

Rules:
- Oily: clear shine across several facial areas, not just the nose.
- Dry: clearly visible dry-looking, rough, or flaky areas.
- Normal: clear image with no strong visible evidence of widespread
  shine or dryness.
- Uncertain: lighting, makeup, blur, or insufficient evidence makes
  the estimate unreliable.

Do not choose Oily just because the forehead or nose reflects light.
Do not choose Dry without visible evidence.
Do not automatically choose Normal when evidence is unclear.
Do not use acne, redness, or pigmentation to determine skin type.
A photograph cannot confirm actual oil production or permanent
skin type. Do not invent evidence.
Return valid JSON only.
"""

    result = call_gemini(prompt, image_base64)
    print("RAW SKIN TYPE RESPONSE:", result)

    if result.get("image_reliable") is not True:
        return "Uncertain", "Image quality does not support a reliable estimate."

    value = result.get("skin_type", "")
    if not isinstance(value, str):
        return "Uncertain", "The model did not return a valid skin type."

    value = value.strip().lower()

    mapping = {
        "oily": "Oily",
        "oily skin": "Oily",
        "dry": "Dry",
        "dry skin": "Dry",
        "normal": "Normal",
        "normal skin": "Normal",
        "uncertain": "Uncertain",
    }

    skin_type = mapping.get(value, "Uncertain")

    explanation = result.get("explanation", "")
    if not isinstance(explanation, str):
        explanation = ""

    print("FINAL SKIN TYPE:", skin_type, "|", explanation)

    return skin_type, explanation.strip()[:250]


def analyze_skin(image_path):
    """Analyze an uploaded image and return Flask-compatible data."""

    if not os.path.isfile(image_path):
        return failure("Image file was not found.")

    image = cv2.imread(image_path)

    if image is None:
        return failure("Image could not be opened.")

    height, width = image.shape[:2]

    if height < 200 or width < 200:
        return failure("Image resolution is too low. Upload a clearer photo.")

    scale = min(1.0, 1024 / max(height, width))

    if scale < 1.0:
        image = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA,
        )

    success, encoded_image = cv2.imencode(".jpg", image)

    if not success:
        return failure("Image encoding failed.")

    image_base64 = base64.b64encode(
        encoded_image.tobytes()
    ).decode("utf-8")

    # Request 1: five visible concerns.
    print("LOCAL AI: Starting concern assessment...")

    try:
        concern_result = analyze_concerns(image_base64)

    except (json.JSONDecodeError, ValueError, TypeError) as error:
        print("CONCERN RESPONSE ERROR:", error)
        return failure("Gemini returned an invalid concern response.")

    except Exception as error:
        print("CONCERN ANALYSIS ERROR:", error)
        return failure(
            "Gemini concern analysis failed. Check API key, quota, "
            "and internet connection."
        )

    print("LOCAL AI CONCERNS:", concern_result)

    if concern_result.get("face_visible") is not True:
        return failure(
            "A face was not clearly identified. Try a front-facing photo.",
            status="uncertain",
        )

    if concern_result.get("image_quality") != "good":
        return failure(
            "Use a clear, front-facing photo with even lighting.",
            status="uncertain",
        )

    raw_signs = concern_result.get("signs", {})

    if not isinstance(raw_signs, dict):
        raw_signs = {}

    concerns = [
        label
        for key, label in SIGN_LABELS.items()
        if raw_signs.get(key) is True
    ]

    if not concerns:
        concerns = [
            "No clear visual indicator reported by the local model."
        ]

    explanation = concern_result.get("explanation", "")
    if not isinstance(explanation, str):
        explanation = ""

    explanation = explanation.strip()[:300]

    # Request 2: three-category skin-type estimate.
    skin_type = "Uncertain"
    skin_type_explanation = ""

    print("LOCAL AI: Starting skin-type assessment...")

    try:
        skin_type, skin_type_explanation = analyze_skin_type(image_base64)

    except (json.JSONDecodeError, ValueError, TypeError) as error:
        print("SKIN TYPE RESPONSE ERROR:", error)

    except Exception as error:
        print("GEMINI SKIN TYPE ERROR:", error)

    if skin_type_explanation:
        if explanation:
            explanation += " Skin-type estimate: " + skin_type_explanation
        else:
            explanation = skin_type_explanation

    return {
        "skin_type": skin_type,
        "concerns": concerns,
        "analysis_note": (
            "Skin type is an experimental visual estimate from one photo. "
            "Visible signs are AI observations, not a medical diagnosis."
        ),
        "analysis_explanation": explanation[:500],
        "analysis_status": "completed",
    }
