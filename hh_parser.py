import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Маппинг специализаций на теги Jobicy
SPECIALIZATION_TAGS = {
    "SMM / Соцсети": ["social-media", "content-marketing", "marketing"],
    "Digital / Performance": ["digital-marketing", "performance-marketing", "marketing"],
    "Brand / Маркетинг": ["marketing", "brand-marketing", "product-marketing"],
    "PR / Коммуникации": ["public-relations", "communications", "marketing"],
    "Контент / Копирайтинг": ["copywriting", "content-marketing", "marketing"],
    "Другое": ["marketing"],
}

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


class HHParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; MarketingJobsBot/1.0)",
            "Accept": "application/json",
        })

    def fetch_jobs(self, specialization: str, city: str,
                   experience: str, limit: int = 8) -> List[Dict]:

        tags = SPECIALIZATION_TAGS.get(specialization, ["marketing"])
        all_jobs = []
        seen_ids = set()

        for tag in tags[:2]:
            try:
                params = {
                    "count": limit,
                    "tag": tag,
                    "industry": "marketing",
                }
                resp = self.session.get(JOBICY_API, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("jobs", []):
                    if item.get("id") in seen_ids:
                        continue
                    seen_ids.add(item.get("id"))
                    all_jobs.append(self._format_job(item))

            except Exception as e:
                logger.error(f"Jobicy fetch error for tag '{tag}': {e}")

        # Запасной запрос без тега если ничего не нашли
        if not all_jobs:
            try:
                params = {"count": limit, "industry": "marketing"}
                resp = self.session.get(JOBICY_API, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("jobs", []):
                    all_jobs.append(self._format_job(item))
                logger.info(f"Fallback found {len(all_jobs)} jobs")
            except Exception as e:
                logger.error(f"Jobicy fallback error: {e}")

        return all_jobs[:limit]

    def _format_job(self, item: dict) -> Dict:
        salary = item.get("annualSalaryMin") or item.get("annualSalaryMax")
        if salary:
            salary_str = f"от ${item['annualSalaryMin']:,}" if item.get("annualSalaryMin") else f"до ${item['annualSalaryMax']:,}"
        else:
            salary_str = "з/п не указана"

        return {
            "id": str(item.get("id", "")),
            "name": item.get("jobTitle", "—"),
            "employer": item.get("companyName", "—"),
            "salary": salary_str,
            "url": item.get("url", ""),
            "city": item.get("jobGeo", "Remote"),
        }

    def _get_area_id(self, city_lower: str) -> str:
        return None
