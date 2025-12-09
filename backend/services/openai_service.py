import os
import base64
import json
from json import JSONDecodeError
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in environment.")

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
- estimated_material_cost: parts + materials cost in USD (rough ballpark, not exact)
- estimated_paint_cost: paint/blend cost in USD if relevant, otherwise 0
- estimated_structural_cost: structural/frame/support-related cost in USD if relevant, otherwise 0

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
      "estimated_material_cost": 600.0,
      "estimated_paint_cost": 300.0,
      "estimated_structural_cost": 0.0
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
    text = text.strip()

    # Remove ```...``` fences if the model added them
    if text.startswith("```"):
        # common patterns: ```json\\n{...}\\n``` or ```\\n{...}\\n```
        # Strip leading/trailing backticks and language hints
        text = text.strip("`")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        # If we can't find a nice block, just return original
        return text
    return text[start : end + 1]


def _compute_closing_suffix(text: str) -> str:
    """
    Look at the text and find unmatched { or [ outside of strings.
    Return the sequence of } and ] needed to close them in the correct order.
    """
    stack = []
    in_string = False
    escape = False

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    closing = []
    for opener in reversed(stack):
        closing.append("}" if opener == "{" else "]")
    return "".join(closing)


def _truncate_and_balance_json(text: str, error_pos: int) -> str:
    """
    If JSON decoding fails at some position (often because the model output
    is truncated or has a half-written property), try:

    - Truncate around the error line
    - Remove a trailing comma if present
    - Close any remaining { or [ with the correct } or ] in order
    """
    partial = text[:error_pos]

    # Drop the incomplete line where the error occurred
    last_nl = partial.rfind("\n")
    if last_nl != -1:
        partial = partial[:last_nl]

    partial = partial.rstrip()

    # If we end with a comma like `"foo": 123,` and then truncated, drop the comma
    if partial.endswith(","):
        partial = partial[:-1]

    # Now append closing braces/brackets in the right order
    suffix = _compute_closing_suffix(partial)
    return partial + suffix


def _parse_model_json(raw_text: str) -> dict:
    """
    Try increasingly aggressive ways to get a usable JSON object out of the model output.
    1) Direct json.loads
    2) Extract JSON block and json.loads
    3) Truncate around the error position and balance braces/brackets
    """
    # 1) Direct attempt
    try:
        return json.loads(raw_text)
    except JSONDecodeError:
        pass

    # 2) Try after extracting the JSON-looking block
    cleaned = _extract_json_block(raw_text)
    try:
        return json.loads(cleaned)
    except JSONDecodeError as e2:
        # 3) Try to truncate and balance
        try:
            repaired = _truncate_and_balance_json(cleaned, e2.pos)
            obj = json.loads(repaired)
            print("[OpenAI] Repaired JSON by truncation; some parts may be missing.")
            return obj
        except JSONDecodeError as e3:
            # At this point, bail out; let the caller surface a 500
            print(f"[OpenAI] JSON repair also failed: {e3}")
            print("Raw model text (truncated):", raw_text[:500])
            raise


def analyze_damage_from_images(
    images: List[bytes], vehicle_info: Optional[str] = None
) -> dict:
    """
    Call OpenAI Vision with ALL provided images and return a parsed JSON damage report.

    images: list of raw image bytes.
    vehicle_info: optional string like "2006 Mitsubishi Lancer Evolution IX"
                  to help the model estimate realistic part prices.
    """
    if not images:
        raise ValueError("No images provided for analysis.")

    # Build the multi-modal input: text prompt (and optional vehicle info),
    # then each image.
    content = [
        {
            "type": "input_text",
            "text": MULTI_IMAGE_PROMPT.strip(),
        }
    ]

    if vehicle_info:
        content.append(
            {
                "type": "input_text",
                "text": (
                    "Vehicle information from the user (use this when estimating costs): "
                    f"{vehicle_info.strip()}"
                ),
            }
        )

    for img_bytes in images:
        data_url = _encode_image_bytes(img_bytes)
        content.append(
            {
                "type": "input_image",
                # For the Responses API, image_url must be a STRING (URL or data URL),
                # not an object like {"url": ...}.
                "image_url": data_url,
            }
        )

    try:
        # IMPORTANT: do NOT pass response_format here; this client version
        # doesn't accept it.
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_output_tokens=800,
        )
    except Exception as e:
        print(f"[OpenAI] Error calling API: {e}")
        raise

    # Responses API: primary text lives here
    raw_text = response.output[0].content[0].text.strip()

    # Parse/repair JSON as needed
    return _parse_model_json(raw_text)