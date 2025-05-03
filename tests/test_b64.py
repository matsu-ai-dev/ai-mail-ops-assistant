from app.main import img_to_b64
from PIL import Image
import base64, io

def test_img_to_b64():
    img = Image.new("RGB", (100, 100), "red")
    b64 = img_to_b64(img)
    data = base64.b64decode(b64)
    img2 = Image.open(io.BytesIO(data))
    assert img2.size == (100, 100)
