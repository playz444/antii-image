import re
from typing import Dict, Any, List

class ScamDetector:
    def __init__(self, threshold: int = 50):
        self.threshold = threshold

        # Core regex and keyword signatures
        self.mrbeast_keywords = [
            r"\bmr\s*beast\b",
            r"@mrbeast",
            r"\bjimmy\s*donaldson\b",
            r"\bmrbeast6000\b"
        ]

        self.crypto_casino_keywords = [
            r"cryptocurrency\s+casino",
            r"crypto\s+casino",
            r"vyro\s+project",
            r"\blenuwin\b",
            r"\brakeback\b",
            r"vip-club",
            r"\bbonuses\b",
            r"\bdeposit\b",
            r"\bwithdraw\b",
            r"withdrawal\s+success",
            r"your\s+withdrawal\s+of",
            r"transferred\s+to\s+your\s+specified\s+wallet",
            r"receive\s+usdt",
            r"network\s+fee",
            r"block\s+explorer"
        ]

        self.promo_reward_keywords = [
            r"promo\s*code\s*[:\-]?\s*[A-Z0-9]+",
            r"activate\s+code\s+for\s+bonus",
            r"enter\s+the\s+special\s+promo\s+code",
            r"give\s*away\s*\$?\s*5[,.]?600",
            r"\$?\s*5[,.]?600\s*(to\s+everyone|bonus|usdt)?",
            r"bonus\s+immediately",
            r"how\s+to\s+claim\s+your\s+reward",
            r"exclusive\s+reward",
            r"offer\s+is\s+limited"
        ]

        self.urgency_keywords = [
            r"post\s+will\s+be\s+deleted",
            r"deleted\s+(an|1)\s+hour\s+after",
            r"only\s+the\s+fastest\s+people",
            r"don'?t\s+miss\s+your\s+chance",
            r"so\s+only\s+the\s+fastest"
        ]

    def evaluate(self, text: str) -> Dict[str, Any]:
        """
        Analyzes the extracted OCR text and computes a scam confidence score.
        """
        if not text:
            return {
                "is_scam": False,
                "score": 0,
                "matches": [],
                "details": "No readable text found."
            }

        cleaned_text = text.lower()
        score = 0
        matches: List[str] = []
        breakdown: Dict[str, List[str]] = {
            "mrbeast_identity": [],
            "crypto_casino": [],
            "promo_giveaway": [],
            "fake_urgency": []
        }

        # 1. Check MrBeast identity match
        for pattern in self.mrbeast_keywords:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                found = re.findall(pattern, cleaned_text, re.IGNORECASE)
                breakdown["mrbeast_identity"].extend(found)
                matches.append(f"MrBeast Branding: {found[0]}")

        # 2. Check Crypto / Casino / Withdrawal keywords
        for pattern in self.crypto_casino_keywords:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                found = re.findall(pattern, cleaned_text, re.IGNORECASE)
                breakdown["crypto_casino"].extend(found)
                matches.append(f"Crypto/Casino Sign: {pattern.replace(r'\b', '')}")

        # 3. Check Promo / High Reward / Giveaway lures
        for pattern in self.promo_reward_keywords:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                found = re.findall(pattern, cleaned_text, re.IGNORECASE)
                breakdown["promo_giveaway"].extend(found)
                matches.append(f"Reward/Promo Lure: {pattern.replace(r'\b', '')}")

        # 4. Check Urgency / Phishing pressure
        for pattern in self.urgency_keywords:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                found = re.findall(pattern, cleaned_text, re.IGNORECASE)
                breakdown["fake_urgency"].extend(found)
                matches.append(f"Fake Urgency: {pattern.replace(r'\b', '')}")

        # Calculate Score
        has_mrbeast = len(breakdown["mrbeast_identity"]) > 0
        crypto_count = len(breakdown["crypto_casino"])
        promo_count = len(breakdown["promo_giveaway"])
        urgency_count = len(breakdown["fake_urgency"])

        if has_mrbeast:
            score += 35
        
        # Crypto/Casino matches
        score += min(crypto_count * 15, 35)

        # Promo/Reward matches
        score += min(promo_count * 20, 40)

        # Urgency matches
        score += min(urgency_count * 15, 20)

        # Critical combo heuristics
        # Combo A: MrBeast + (Crypto/Casino OR Promo Lure OR $5600)
        if has_mrbeast and (crypto_count >= 1 or promo_count >= 1):
            score = max(score, 85)

        # Combo B: Fake Withdrawal UI + Promo / $5600 / USDT
        if ("withdrawal" in cleaned_text or "withdraw" in cleaned_text) and (promo_count >= 1 or "5600" in cleaned_text or "usdt" in cleaned_text):
            score = max(score, 80)

        # Combo C: Promo code activation screen with casino rakeback/VIP
        if "activate code" in cleaned_text or "rakeback" in cleaned_text or "lenuwin" in cleaned_text:
            score = max(score, 75)

        # Cap score between 0 and 100
        score = min(score, 100)
        is_scam = score >= self.threshold

        return {
            "is_scam": is_scam,
            "score": score,
            "matches": list(dict.fromkeys(matches)), # Deduplicate
            "breakdown": breakdown,
            "threshold": self.threshold
        }
