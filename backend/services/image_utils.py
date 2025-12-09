from PIL import Image
from io import BytesIO


def validate_image(image_bytes: bytes):
    """
    Validate that the uploaded bytes represent an actual image.

    Raises:
        ValueError: if the file is not a valid image.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()  # verifies image integrity
    except Exception:
        raise ValueError("Invalid image file.")