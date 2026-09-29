import os
import aiohttp
import base64
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger("OCRScanner")

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"

DEFAULT_API_KEYS = [
    "K81898748388957",
    "K88574938288957",
    "K85764491988957",
    "K89278782388957",
    "helloworld"
]

class OCRScanner:
    def __init__(self, api_key: Optional[str] = None):
        custom_key = api_key or os.getenv("OCR_API_KEY")
        if custom_key and custom_key not in DEFAULT_API_KEYS:
            self.keys = [custom_key] + DEFAULT_API_KEYS
        else:
            self.keys = list(DEFAULT_API_KEYS)

    async def scan_image_bytes(self, image_bytes: bytes, filename: str = "screenshot.png", engine: str = "2") -> Tuple[bool, str, Optional[str]]:
        """
        Scans raw image bytes using base64 payload and robust API key rotation.
        """
        if not image_bytes:
            return False, "", "Empty image data."

        b64_str = base64.b64encode(image_bytes).decode('utf-8')
        base64_data = f"data:image/png;base64,{b64_str}"

        for key in self.keys:
            payload = {
                "apikey": key,
                "base64Image": base64_data,
                "language": "eng",
                "isOverlayRequired": "false",
                "detectOrientation": "false",
                "scale": "true" if engine == "2" else "false",
                "OCREngine": engine
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(OCR_SPACE_API_URL, data=payload, timeout=aiohttp.ClientTimeout(total=20)) as response:
                        if response.status in (429, 503):
                            logger.warning(f"OCR key {key[:6]}... throttled ({response.status}). Trying next key...")
                            continue

                        if response.status != 200:
                            err_text = await response.text()
                            logger.warning(f"OCR key {key[:6]}... HTTP error {response.status}: {err_text}")
                            continue

                        data = await response.json()
                        if data.get("IsErroredOnProcessing", False):
                            err_msg = str(data.get("ErrorMessage", ["Unknown error"]))
                            logger.warning(f"OCR Error with key {key[:6]}...: {err_msg}")
                            continue

                        parsed_results = data.get("ParsedResults", [])
                        if not parsed_results:
                            continue

                        full_text = "\n".join([res.get("ParsedText", "") for res in parsed_results if res.get("ParsedText")])
                        return True, full_text.strip(), None

            except Exception as e:
                logger.warning(f"Exception during OCR request with key {key[:6]}...: {e}")
                continue

        return False, "", "All OCR endpoints failed or were throttled."

    async def scan_image_url(self, image_url: str, engine: str = "2") -> Tuple[bool, str, Optional[str]]:
        """
        Fallback URL scanner.
        """
        for key in self.keys:
            payload = {
                "url": image_url,
                "apikey": key,
                "language": "eng",
                "isOverlayRequired": "false",
                "detectOrientation": "false",
                "scale": "true" if engine == "2" else "false",
                "OCREngine": engine
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(OCR_SPACE_API_URL, data=payload, timeout=aiohttp.ClientTimeout(total=20)) as response:
                        if response.status in (429, 503):
                            continue
                        if response.status != 200:
                            continue

                        data = await response.json()
                        if data.get("IsErroredOnProcessing", False):
                            continue

                        parsed_results = data.get("ParsedResults", [])
                        if not parsed_results:
                            continue

                        full_text = "\n".join([res.get("ParsedText", "") for res in parsed_results if res.get("ParsedText")])
                        return True, full_text.strip(), None
            except Exception:
                continue

        return False, "", "All OCR endpoints failed."
