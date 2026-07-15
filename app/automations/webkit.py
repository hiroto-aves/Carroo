import httpx
from app.config import settings
from typing import Dict, Any

class WebkitAutomation:
    """WebkitへのAPI経由での投稿を実行"""

    def __init__(self):
        self.api_url = settings.WEBKIT_API_URL
        self.api_key = settings.WEBKIT_API_KEY

    async def post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """案件データをWebkit APIに送信"""
        if not self.api_key:
            return {
                "status": "error",
                "platform": "webkit",
                "message": "Webkit API key not configured"
            }

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "pick_location": case_data.get("pick_location"),
                    "drop_location": case_data.get("drop_location"),
                    "cargo_weight": case_data.get("cargo_weight"),
                    "vehicle_type": case_data.get("vehicle_type"),
                    "freight_rate": case_data.get("freight_rate"),
                    "pickup_date": case_data.get("pickup_date"),
                    "pickup_time": case_data.get("pickup_time"),
                    "contact_name": case_data.get("contact_name"),
                    "contact_phone": case_data.get("contact_phone"),
                    "contact_email": case_data.get("contact_email"),
                }

                response = await client.post(
                    f"{self.api_url}/cases",
                    json=payload,
                    headers=headers
                )

                if response.status_code in [200, 201]:
                    return {
                        "status": "success",
                        "platform": "webkit",
                        "message": "Case posted to Webkit successfully",
                        "data": response.json()
                    }
                else:
                    return {
                        "status": "error",
                        "platform": "webkit",
                        "message": f"API error: {response.status_code}",
                        "details": response.text
                    }

        except Exception as e:
            return {
                "status": "error",
                "platform": "webkit",
                "message": str(e)
            }
