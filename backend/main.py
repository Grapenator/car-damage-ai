from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.image_utils import validate_image
from services.openai_service import analyze_car_damage
from services.sheets_service import write_damage_report

import uuid

app = FastAPI(
    title="Car Damage Analyzer",
    description="Uploads a car image, uses OpenAI to detect exterior damage, and logs a report to Google Sheets.",
    version="1.0.0",
)

# CORS so React frontend can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Car damage API is running"}


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    # Only allow JPEG/PNG
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Please upload a JPEG or PNG image.")

    image_bytes = await file.read()

    # Validate actual image content
    try:
        validate_image(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate a report ID
    report_id = str(uuid.uuid4())

    # 1) Call OpenAI to analyze damage
    try:
        damage_report = analyze_car_damage(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI analysis failed: {e}")

    if not damage_report.get("is_car", False):
        raise HTTPException(
            status_code=400,
            detail=damage_report.get("notes", "The uploaded image does not appear to be a car."),
        )

    # 2) Write damage report to Google Sheets
    try:
        sheet_url = write_damage_report(report_id, damage_report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Writing to Google Sheets failed: {e}")

    return JSONResponse(
        {
            "report_id": report_id,
            "sheet_url": sheet_url,
            "damage_report": damage_report,
        }
    )