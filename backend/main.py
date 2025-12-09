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
    description="Upload car images, analyze damage with OpenAI, and log reports to Google Sheets.",
    version="1.2.0",
)

# Allow local dev + future frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can tighten this later
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

    # Call OpenAI Vision with all images (+ optional vehicle_info)
    try:
        damage_report = analyze_damage_from_images(
            image_bytes_list, vehicle_info=vehicle_info
        )
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

    # If overall cost is missing, try to derive it from per-part totals
    overall_cost = damage_report.get("overall_estimated_repair_cost")
    if overall_cost is None:
        parts = damage_report.get("parts", [])
        total = 0.0
        for p in parts:
            if "estimated_total_part_cost" in p:
                try:
                    total += float(p["estimated_total_part_cost"])
                except Exception:
                    pass
        if total > 0:
            damage_report["overall_estimated_repair_cost"] = total

    return {
        "report_id": report_id,
        "sheet_url": sheet_url,
        "damage_report": damage_report,
    }