import uuid
from typing import List, Optional
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from dotenv import load_dotenv

from services.openai_service import analyze_damage_from_images
from services.sheets_service import write_damage_report

load_dotenv()

app = FastAPI(
    title="Car Damage Analyzer API",
    description=(
        "Upload car images, analyze damage with OpenAI, and log reports to "
        "Google Sheets."
    ),
    version="1.2.0",
)

# Allow local dev + future frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_image_bytes(image_bytes: bytes) -> None:
    """Simple image validation using Pillow."""
    try:
        Image.open(BytesIO(image_bytes)).verify()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="One of the uploaded files is not a valid image.",
        )


def _to_float(value) -> float:
    """Safely convert something to float, treating None/''/bad values as 0."""
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _recompute_costs(damage_report: dict) -> dict:
    """
    Backend-owned cost logic.

    For each part:
      estimated_total_part_cost = material + paint + structural

    And overall_estimated_repair_cost = sum of all part totals.

    Any totals coming from OpenAI are ignored/overwritten.
    """
    parts = damage_report.get("parts") or []
    overall = 0.0

    for part in parts:
        material = _to_float(part.get("estimated_material_cost"))
        paint = _to_float(part.get("estimated_paint_cost"))
        structural = _to_float(part.get("estimated_structural_cost"))

        part_total = material + paint + structural
        part["estimated_total_part_cost"] = round(part_total)  # or keep as part_total

        overall += part_total

    damage_report["overall_estimated_repair_cost"] = round(overall)
    return damage_report


@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "message": "Car damage API is running",
    }


@app.post("/analyze")
async def analyze(
    files: List[UploadFile] = File(
        ...,
        description="Upload one or more images of the SAME car (different angles recommended).",
    ),
    vehicle_info: Optional[str] = Form(
        None,
        description="Optional: year, make, and model (e.g., '2006 Mitsubishi Lancer Evolution IX').",
    ),
):
    """
    Analyze one or more car images.

    - Validates each file as an image.
    - Sends ALL images to OpenAI Vision in a single request.
    - Gets a combined JSON damage report.
    - Recomputes per-part and overall costs on the backend.
    - Writes all parts to Google Sheets (master log + per-report tab).
    - Returns the report_id, sheet_url, and the damage_report JSON.
    """

    if not files:
        raise HTTPException(status_code=400, detail="No images uploaded.")

    # Read and validate all images
    image_bytes_list: List[bytes] = []
    for uploaded in files:
        contents = await uploaded.read()
        if not contents:
            raise HTTPException(
                status_code=400,
                detail=f"File '{uploaded.filename}' is empty.",
            )
        _validate_image_bytes(contents)
        image_bytes_list.append(contents)

    # Call OpenAI Vision with all images (+ optional vehicle info)
    try:
        damage_report = analyze_damage_from_images(image_bytes_list, vehicle_info)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI analysis failed: {e}",
        )

    # Check if it's actually a car
    if not damage_report.get("is_car", False):
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded images do not appear to be a car. "
                f"Notes: {damage_report.get('notes', '')}"
            ),
        )

    # Backend-owned totals (ignores any totals from the model)
    damage_report = _recompute_costs(damage_report)

    # Generate a report_id for this request
    report_id = str(uuid.uuid4())

    # Write to Google Sheets (master + per-report tab)
    try:
        sheet_url = write_damage_report(report_id, damage_report)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Writing to Google Sheets failed: {e}",
        )

    return {
        "report_id": report_id,
        "sheet_url": sheet_url,
        "damage_report": damage_report,
    }