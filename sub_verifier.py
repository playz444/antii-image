import re
from typing import List, Tuple

def check_subscription(ocr_text: str, target_aliases: List[str]) -> Tuple[bool, str]:
    """
    Checks the OCR text for subscriber verification with smart normalization.
    Returns (success: bool, message: str)
    """
    if not target_aliases:
        return False, "⚠️ Server Error: The server admin has not configured any target YouTube Channel Aliases in `/sub-setup`."
        
    if not ocr_text:
        return False, "Could not detect any text in your screenshot. Please upload a clear, uncropped image."
    
    text_lower = ocr_text.lower()
    text_clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text_lower)
    text_dense = re.sub(r'[^a-zA-Z0-9]', '', text_lower)
    
    # Step 1: Verify the Target Channel Name or Handle is in the image
    alias_found = False
    for alias in target_aliases:
        if not alias:
            continue
        a_lower = alias.lower()
        a_clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', a_lower).strip()
        a_dense = re.sub(r'[^a-zA-Z0-9]', '', a_lower)
        
        # Check standard string inclusion & dense (whitespace stripped) inclusion
        if a_lower in text_lower or (a_clean and a_clean in text_clean) or (a_dense and a_dense in text_dense):
            alias_found = True
            break
            
        # Check all individual words (e.g. 'abhi' and 'cheats' both present)
        words = a_clean.split()
        if len(words) > 1 and all(w in text_clean for w in words):
            alias_found = True
            break

    if not alias_found:
        return False, "Could not detect the required YouTube channel name in your screenshot."

    # Step 2: Strict match for "Subscribed" (Pass state)
    pass_patterns = [
        r"\bsubscribed\b", r"\bsubbed\b", r"\binscrito\b", r"\binscrita\b",
        r"\bsuscrito\b", r"\bsuscrita\b", r"\babonn[eé]e?s?\b", r"\babonniert\b",
        r"abone olundu", r"\biscritto\b", r"\biscritta\b"
    ]
    
    is_subscribed = any(re.search(p, text_lower) for p in pass_patterns) or ("subscribed" in text_dense)
    
    if is_subscribed:
        # Safety check against "unsubscribed" taking precedence
        if "unsubscribed" in text_lower or "unsubscribed" in text_dense:
            return False, "Detected 'Unsubscribed' state. Please subscribe and try again."
        return True, "Successfully verified subscription."

    # Step 3: Match for "Subscribe" (Unsubscribed state)
    fail_patterns = [
        r"\bsubscribe\b", r"\bs’abonner\b", r"\binscribirse\b", r"\babonnieren\b"
    ]
    is_unsubscribed = any(re.search(p, text_lower) for p in fail_patterns)
    
    if is_unsubscribed:
        return False, "Detected the 'Subscribe' button. You must actually click Subscribe to verify!"

    # Step 4: Fallback
    return False, "Could not clearly read the 'Subscribed' button. Please upload a clearer, uncropped screenshot."
