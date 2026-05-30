import io
import json
import logging
import anthropic

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()  # читает ANTHROPIC_API_KEY из env


class AIAnalyzer:

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Извлекает текст из PDF через pypdf"""
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text.strip()
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""

    async def match_cv_to_jobs(self, cv_text: str, jobs: list) -> list:
        """Использует Claude для подбора топ-5 вакансий под резюме"""
        if not cv_text or not jobs:
            return jobs[:5]

        jobs_text = "\n".join([
            f"{i+1}. {j['name']} | {j['employer']} | {j['salary']} | {j['url']}"
            for i, j in enumerate(jobs)
        ])

        prompt = f"""Ты помощник по подбору работы в маркетинге.

Вот резюме кандидата:
{cv_text[:3000]}

Вот список вакансий:
{jobs_text}

Выбери топ-5 наиболее подходящих вакансий для этого кандидата.
Ответь ТОЛЬКО в формате JSON — массив из 5 объектов:
[
  {{
    "index": <номер вакансии из списка, начиная с 1>,
    "reason": "<одна строка — почему подходит>"
  }},
  ...
]
Никакого текста кроме JSON."""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
            picks = json.loads(raw)

            result = []
            for pick in picks:
                idx = pick["index"] - 1
                if 0 <= idx < len(jobs):
                    job = dict(jobs[idx])
                    job["reason"] = pick.get("reason", "")
                    result.append(job)
            return result

        except Exception as e:
            logger.error(f"AI matching error: {e}")
            return jobs[:5]
