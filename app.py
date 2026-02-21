import base64
from datetime import datetime
from io import BytesIO
from fastapi, status import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from ocr import scan_receipt
from pathlib import Path
from PIL import Image
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class ReceiptLinesArgs(BaseModel):
    image: str

@app.get("/", status_code=status.HTTP_200_OK)
def ping():
    return {"message": "Healthy!"}

@app.post("/receiptLines")
def scan_receipt_image(args: ReceiptLinesArgs):
    image_url = args.image
    
    # strip the metadata from the front of the image URI
    assert image_url.startswith("data:image/png;base64,")
    image_b64 = image_url.split(",")[1]

    image_data = base64.b64decode(image_b64)
    image = Image.open(BytesIO(image_data))

    image_path = Path(f"imgs") / f"{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    image.save(image_path)

    return scan_receipt(str(image_path), debug=True)
