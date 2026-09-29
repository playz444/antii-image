import aiohttp
import logging
from typing import Optional, Tuple

logger = logging.getLogger("OCRScanner")

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"

class OCRScanner:
    def __init__(self, api_key: str = "helloworld"):
        self.api_key = api_key

    async def scan_image_url(self, image_url: str, engine: str = "2") -> Tuple[bool, str, Optional[str]]:
        """
        Scans an image from a direct URL using OCR.space API.
        Returns: (success: bool, extracted_text: str, error_message: Optional[str])
        """
        payload = {
            "url": image_url,
            "apikey": self.api_key,
            "language": "eng",
            "isOverlayRequired": "false",
            "detectOrientation": "false",
            "scale": "true" if engine == "2" else "false",
            "OCREngine": engine
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(OCR_SPACE_API_URL, data=payload, timeout=aiohttp.ClientTimeout(total=25)) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        logger.error(f"OCR API HTTP error {response.status}: {err_text}")
                        return False, "", f"HTTP error {response.status}"

                    data = await response.json()
                    
                    if data.get("IsErroredOnProcessing", False):
                        err_msg = data.get("ErrorMessage", ["Processing Error"])
                        return False, "", str(err_msg)

                    parsed_results = data.get("ParsedResults", [])
                    if not parsed_results:
                        return True, "", None

                    full_text = "\n".join([res.get("ParsedText", "") for res in parsed_results])
                    return True, full_text.strip(), None

        except Exception as e:
            logger.exception(f"Exception during OCR request: {e}")
            return False, "", str(e)

    async def scan_image_bytes(self, image_bytes: bytes, filename: str = "scan.png") -> Tuple[bool, str, Optional[str]]:
        """
        Scans raw image bytes using OCR.space multipart upload.
        """
        data = aiohttp.FormData()
        data.add_field("apikey", self.api_key)
        data.add_field("language", "eng")
        data.add_field("isOverlayRequired", "false")
        data.add_field("detectOrientation", "false") # Disabled for speed
        data.add_field("scale", "false")             # Disabled for speed
        data.add_field("OCREngine", "1")             # Engine 1 is significantly faster
        data.add_field("file", image_bytes, filename=filename, content_type="image/png")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(OCR_SPACE_API_URL, data=data, timeout=aiohttp.ClientTimeout(total=25)) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        return False, "", f"HTTP error {response.status}: {err_text}"

                    result = await response.json()
                    if result.get("IsErroredOnProcessing", False):
                        err_msg = result.get("ErrorMessage", ["Processing Error"])
                        return False, "", str(err_msg)

                    parsed_results = result.get("ParsedResults", [])
                    if not parsed_results:
                        return True, "", None

                    full_text = "\n".join([res.get("ParsedText", "") for res in parsed_results])
                    return True, full_text.strip(), None
        except Exception as e:
            logger.exception(f"Exception during OCR bytes request: {e}")
            return False, "", str(e)
