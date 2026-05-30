import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"

SPECIALIZATION_TAGS = {
    "SMM / Соцсети":            ["social-media", "content-marketing"],
    "Digital / Performance":    ["digital-marketing", "performance-marketing"],
    "Brand / Маркетинг":        ["marketing", "brand-marketing"],
    "PR / Коммуникации":        ["public-relations", "communications"],
    "Контент / Копирайтинг":    ["copywriting", "content-marketing"],
    "Product Manager":          ["product-management"],
    "Data / Аналитика":         ["data-analysis", "data-science"],
    "Design / UX":              ["ux", "design"],
    "Frontend":                 ["frontend", "javascript"],
    "Backend":                  ["backend", "python"],
    "HR / Рекрутинг":           ["human-resources", "recruiting"],
    "Финансы":                  ["finance", "accounting"],
    "Customer Success":         ["customer-success", "customer-support"],
    "Другое":                   ["marketing"],
}

SPECIALIZATION_GROUPS = {
    "📣 Маркетинг": [
        "SMM / Соцсети", "Digital / Performance",
        "Brand / Маркетинг", "PR / Коммуникации", "Контент / Копирайтинг"
    ],
    "💻 IT": [
        "Product Manager", "Data / Аналитика",
        "Design / UX", "Frontend", "Backend"
    ],
    "🗂 Другое": [
        "HR / Рекрутинг", "Финансы", "Customer Success", "Другое"
    ],
}


class HHParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; JobsBot/1.0)",
            "Accept": "application/json",
        })

    def fetch_jobs(self, specialization: str, city: str = "",
                   experience: str = "", limit: int = 8) -> List[Dict]:

        tags = SPECIALIZATION_TAGS.get(specialization, ["marketing"])
        all_jobs = []
        seen_ids = set()

        for tag in tags[:2]:
            try:
                resp = self.session.get(JOBICY_API, params={
                    "count": limit, "tag": tag
                }, timeout=10)
                resp.raise_for_status()
                for item in resp.json().get("jobs", []):
                    if item.get("id") not in seen_ids:
                        seen_ids.add(item.get("id"))
                        all_jobs.append(self._format_job(item))
            except Exception as e:
                logger.error(f"Jobicy error for '{tag}': {e}")

        if not all_jobs:
            try:
                resp = self.session.get(JOBICY_API, params={"count": limit}, timeout=10)
                resp.raise_for_status()
                all_jobs = [self._format_job(i) for i in resp.json().get("jobs", [])]
            except Exception as e:
                logger.error(f"Jobicy fallback error: {e}")

        return all_jobs[:limit]

    def _format_job(self, item: dict) -> Dict:
        min_s = item.get("annualSalaryMin")
        max_s = item.get("annualSalaryMax")
        if min_s and max_s:
            salary = f"${min_s:,}–${max_s:,}/год"
        elif min_s:
            salary = f"от ${min_s:,}/год"
        elif max_s:
            salary = f"до ${max_s:,}/год"
        else:
            salary = "з/п не указана"

        return {
            "id": str(item.get("id", "")),
            "name": item.get("jobTitle", "—"),
            "employer": item.get("companyName", "—"),
            "salary": salary,
            "url": item.get("url", ""),
            "city": "🌍 Remote",
        }

    def _get_area_id(self, city_lower: str) -> str:
        return None
