import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Маппинг специализаций на поисковые запросы hh.ru
SPECIALIZATION_QUERIES = {
    "SMM / Соцсети": ["SMM менеджер", "менеджер социальных сетей", "контент менеджер"],
    "Digital / Performance": ["performance маркетолог", "digital маркетолог", "таргетолог", "контекстная реклама"],
    "Brand / Маркетинг": ["бренд менеджер", "маркетолог", "product маркетолог"],
    "PR / Коммуникации": ["PR менеджер", "специалист по коммуникациям", "пресс-секретарь"],
    "Контент / Копирайтинг": ["копирайтер", "редактор", "контент-стратег"],
    "Другое": ["маркетолог", "marketing manager"],
}

# Маппинг опыта на коды hh.ru
EXPERIENCE_MAP = {
    "Нет опыта (0–1 год)": "noExperience",
    "Junior (1–2 года)": "between1And3",
    "Middle (2–4 года)": "between3And6",
    "Senior (4+ лет)": "moreThan6",
}

HH_API = "https://api.hh.ru/vacancies"


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

        # Определяем area_id для города
        area_id = self._get_area_id(city)

        all_jobs = []
        seen_ids = set()

        for query in queries[:2]:  # берём 2 первых запроса
            try:
                params = {
                    "text": query,
                    "experience": exp_code,
                    "per_page": limit,
                    "order_by": "publication_time",
                    "only_with_salary": False,
                }
                if area_id:
                    params["area"] = area_id
                elif "удалённо" in city.lower() or "удаленно" in city.lower():
                    params["schedule"] = "remote"

                resp = self.session.get(HH_API, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    if item["id"] in seen_ids:
                        continue
                    seen_ids.add(item["id"])
                    all_jobs.append(self._format_job(item))

            except Exception as e:
                logger.error(f"HH fetch error for '{query}': {e}")

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

    def _get_area_id(self, city: str) -> str:
        """Возвращает area_id для hh.ru по названию города"""
        city_map = {
            "москва": "1",
            "санкт-петербург": "2",
            "спб": "2",
            "екатеринбург": "3",
            "новосибирск": "4",
            "казань": "88",
            "нижний новгород": "66",
            "ташкент": None,  # hh.ru Узбекистан — отдельный домен
        }
        city_lower = city.lower().strip()
        for key, val in city_map.items():
            if key in city_lower:
                return val
        return None  # hh.ru сам найдёт по всей России
