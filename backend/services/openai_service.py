import base64
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

PROMPT = """
You are a professional auto body estimator.

The user will send you a photo of a vehicle. Your job:

1. Decide if the image contains a car or truck that could reasonably be repaired.
2. If it does, list the damaged EXTERIOR parts you can see.
3. For each damaged part, provide:
   - part_id: short snake_case ID, e.g. "front_bumper"
   - part_name: human readable name, e.g. "Front Bumper"
   - damage_description: 1–2 sentence description of visible damage
   - severity: integer 1–5 (5 = worst)
   - estimated_labor_hours: rough decimal hours to repair/replace, e.g. 2.5

Return ONLY valid JSON in this format:

{
  "is_car": true,
  "notes": "short explanation",
  "parts": [
    {
      "part_id": "front_bumper",
      "part_name": "Front Bumper",
      "damage_description": "Cracked and scraped on the right side.",
      "severity": 4,
      "estimated_labor_hours": 3.0
    }
  ]
}

If the image is not a car, return:

{
  "is_car": false,
  "notes": "Explain what you see instead.",
  "parts": []
}
"""


def analyze_car_damage(image_bytes: bytes) -> dict:
    """
    Send the image to OpenAI Vision and get back a structured damage report.
    """

    # Encode image as base64 data URL
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_image}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Can be adjusted to use a different model
        messages=[
            {
                "role": "system",
                "content": PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze the damage in this vehicle image and respond with JSON only.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            },
        ],
        temperature=0,
    )

    content = response.choices[0].message.content

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from OpenAI: {e}\nRaw content: {content}")

    # Ensure required keys exist
    data.setdefault("is_car", False)
    data.setdefault("notes", "")
    data.setdefault("parts", [])

    return data