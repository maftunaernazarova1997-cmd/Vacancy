import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

SPECIALIZATION_QUERIES = {
    "SMM / Соцсети": ["SMM менеджер", "менеджер социальных сетей", "контент менеджер"],
    "Digital / Performance": ["performance маркетолог", "digital маркетолог", "таргетолог", "контекстная реклама"],
    "Brand / Маркетинг": ["бренд менеджер", "маркетолог", "product маркетолог"],
    "PR / Коммуникации": ["PR менеджер", "специалист по коммуникациям", "пресс-секретарь"],
    "Контент / Копирайтинг": ["копирайтер", "редактор", "контент-стратег"],
    "Другое": ["маркетолог", "marketing manager"],
}

EXPERIENCE_MAP = {
    "Нет опыта (0–1 год)": "noExperience",
    "Junior (1–2 года)": "between1And3",
    "Middle (2–4 года)": "between3And6",
    "Senior (4+ лет)": "moreThan6",
}

HH_RU = "https://api.hh.ru/vacancies"
HH_UZ = "https://api.hh.uz/vacancies"


class HHParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "HH-User-Agent": "MarketingJobsBot/1.0 (maftunaernazarova1997@gmail.com)",
        })

    def fetch_jobs(self, specialization: str, city: str,
                   experience: str, limit: int = 8) -> List[Dict]:
        queries = SPECIALIZATION_QUERIES.get(specialization, ["маркетолог"])
        exp_code = EXPERIENCE_MAP.get(experience, "between1And3")
        city_lower = city.lower().strip()

        # Для Ташкента используем hh.uz, для остальных hh.ru
        if "ташкент" in city_lower or "tashkent" in city_lower:
            base_url = HH_UZ
        else:
            base_url = HH_RU

        area_id = self._get_area_id(city_lower)
        all_jobs = []
        seen_ids = set()

        for query in queries[:2]:
            try:
                params = {
                    "text": query,
                    "experience": exp_code,
                    "per_page": limit,
                    "order_by": "publication_time",
                }
                if area_id:
                    params["area"] = area_id
                elif "удалённо" in city_lower or "удаленно" in city_lower:
                    params["schedule"] = "remote"

                resp = self.session.get(base_url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    if item["id"] in seen_ids:
                        continue
                    seen_ids.add(item["id"])
                    all_jobs.append(self._format_job(item))

            except Exception as e:
                logger.error(f"HH fetch error for '{query}' on {base_url}: {e}")

        # Fallback — ищем удалённые вакансии на hh.ru если ничего не нашли
        if not all_jobs:
            logger.info("No jobs found, trying remote fallback on hh.ru...")
            try:
                params = {
                    "text": queries[0],
                    "experience": exp_code,
                    "per_page": limit,
                    "order_by": "publication_time",
                    "schedule": "remote",
                }
                resp = self.session.get(HH_RU, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("items", []):
                    all_jobs.append(self._format_job(item))
                logger.info(f"Fallback found {len(all_jobs)} jobs")
            except Exception as e:
                logger.error(f"Fallback fetch error: {e}")

        return all_jobs[:limit]

    def _format_job(self, item: dict) -> Dict:
        salary = self._format_salary(item.get("salary"))
        return {
            "id": item["id"],
            "name": item["name"],
            "employer": item.get("employer", {}).get("name", "—"),
            "salary": salary,
            "url": item.get("alternate_url", ""),
            "city": item.get("area", {}).get("name", ""),
        }

    def _format_salary(self, salary: dict) -> str:
        if not salary:
            return "з/п не указана"
        from_val = salary.get("from")
        to_val = salary.get("to")
        currency = salary.get("currency", "RUR")
        currency_sym = {"RUR": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "UZS": "сум"}.get(currency, currency)

        if from_val and to_val:
            return f"{from_val:,}–{to_val:,} {currency_sym}"
        elif from_val:
            return f"от {from_val:,} {currency_sym}"
        elif to_val:
            return f"до {to_val:,} {currency_sym}"
        return "з/п не указана"

    def _get_area_id(self, city_lower: str) -> str:
        city_map = {
            "москва": "1",
            "санкт-петербург": "2",
            "спб": "2",
            "екатеринбург": "3",
            "новосибирск": "4",
            "казань": "88",
            "нижний новгород": "66",
        }
        for key, val in city_map.items():
            if key in city_lower:
                return val
        return None
