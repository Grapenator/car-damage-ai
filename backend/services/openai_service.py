import os
import base64
import json
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

MULTI_IMAGE_PROMPT = """
You are a professional auto body estimator.

The user uploads between 1 and 10 photos of a vehicle. Your job is to:
- Assume all images are of THE SAME vehicle unless there is a very obvious mismatch
  (different color, different body style, etc.). If you think they are different vehicles,
  explain that clearly in `notes`.
- Look across ALL images together and produce ONE combined damage report.
- Focus on EXTERIOR and VISIBLE STRUCTURAL damage (frame, radiator support, core support, etc.).
- Include paint damage and signs of possible hidden/frame damage when reasonable from the angles.

For each distinct damaged part, you must estimate:
- severity: integer 1–5 (5 = worst / heavy damage)
- estimated_labor_hours: hours to repair/replace, decimal ok (e.g., 2.5)
- estimated_material_cost: parts + materials cost in USD (rough ballpark, not exact)
- estimated_paint_cost: paint/blend cost in USD if relevant, otherwise 0
- estimated_structural_cost: structural/frame/support-related cost in USD if relevant, otherwise 0
- estimated_total_part_cost: total estimated cost in USD for this part ONLY
  (labor + materials + paint + structural).

Finally, compute:
- overall_estimated_repair_cost: total estimated cost in USD for repairing ALL visible damage
  on this vehicle, including paint and structural where applicable.

RETURN FORMAT (VERY IMPORTANT):

You MUST respond with EXACTLY ONE valid JSON object that conforms to this structure:

{
  "is_car": true,
  "notes": "short explanation",
  "overall_estimated_repair_cost": 0,
  "parts": [
    {
      "part_id": "front_bumper",
      "part_name": "Front Bumper",
      "damage_description": "Cracked and scraped on the right side.",
      "severity": 4,
      "estimated_labor_hours": 3.0,
      "estimated_material_cost": 600.0,
      "estimated_paint_cost": 300.0,
      "estimated_structural_cost": 0.0,
      "estimated_total_part_cost": 1200.0
    }
  ]
}

If the images do NOT show a car, respond with:

{
  "is_car": false,
  "notes": "Explain what you see instead.",
  "overall_estimated_repair_cost": 0,
  "parts": []
}

STRICT JSON RULES:

- Output MUST be valid JSON per RFC 8259.
- DO NOT include any text before or after the JSON.
- DO NOT wrap the JSON in backticks or a code block.
- DO NOT include comments.
- DO NOT include trailing commas after the last item in an object or array.
- EVERY property in an object must be separated by a comma.
- Use double quotes around all string keys and string values.
- Booleans must be true/false (lowercase).
- Numbers must not contain extra text.

Double-check your output for missing or extra commas before returning.
"""


def _encode_image_bytes(image_bytes: bytes) -> str:
    """Encode raw image bytes as base64 data URL for OpenAI Vision."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _extract_json_block(text: str) -> str:
    """
    Try to pull out the JSON object from a larger text blob.

    - Strips ```json ... ``` fences if present.
    - Takes everything between the first '{' and the last '}'.
    """
    # Remove ```json or ``` fences if the model wrapped the JSON
    if text.startswith("```"):
        # Drop leading ```json or ``` and trailing ```
        text = text.strip("`")
        # After this, rest of the logic still applies

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        # If we can't find a nice block, just return original
        return text
    return text[start : end + 1]


def analyze_damage_from_images(images: List[bytes]) -> dict:
    """
    Call OpenAI Vision with ALL provided images and return a parsed JSON damage report.

    images: list of raw image bytes.
    """
    if not images:
        raise ValueError("No images provided for analysis.")

    # Build the multi-modal input: first the text prompt, then each image.
    content = [
        {
            "type": "input_text",
            "text": MULTI_IMAGE_PROMPT.strip(),
        }
    ]

    for img_bytes in images:
        data_url = _encode_image_bytes(img_bytes)
        content.append(
            {
                "type": "input_image",
                # For the Responses API, image_url should be a STRING (URL or data URL),
                # not an object with {"url": ...}.
                "image_url": data_url,
            }
        )

    try:
        # NOTE: NO response_format here, because this client version doesn't support it.
        response = client.responses.create(
            model="gpt-4.1-mini",  # cost-effective and supports vision
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_output_tokens=800,
        )
    except Exception as e:
        # If the API call itself fails (bad API key, quota, etc.), bubble it up.
        print(f"[OpenAI] Error calling API: {e}")
        raise

    # --- Try to parse the model output as JSON ---

    # Responses API: output[0].content[0].text is the text string
    raw_text = response.output[0].content[0].text.strip()

    # First attempt: direct JSON
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Second attempt: strip code fences / extra text and grab the JSON block
        print("[OpenAI] Initial JSON decode failed, trying to clean the text...")
        cleaned = _extract_json_block(raw_text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # At this point, the model really didn't give valid JSON
            print(f"[OpenAI] JSON decode failed after cleaning: {e}")
            print("Raw model text (truncated):", raw_text[:500])
            # Let this propagate as a 500 so you SEE the failure instead of a fake fallback
            raise