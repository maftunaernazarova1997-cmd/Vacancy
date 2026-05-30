import os
import logging
import psycopg2
import psycopg2.extras
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")


class Database:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id       BIGINT PRIMARY KEY,
                        name          TEXT NOT NULL,
                        experience    TEXT,
                        specialization TEXT,
                        city          TEXT,
                        is_premium    BOOLEAN DEFAULT FALSE,
                        created_at    TIMESTAMP DEFAULT NOW()
                    )
                """)
            conn.commit()

    def save_user(self, user_id: int, name: str, experience: str,
                  specialization: str, city: str):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, name, experience, specialization, city)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name=EXCLUDED.name,
                        experience=EXCLUDED.experience,
                        specialization=EXCLUDED.specialization,
                        city=EXCLUDED.city
                """, (user_id, name, experience, specialization, city))
            conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_all_users(self) -> List[Dict]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users")
                return [dict(r) for r in cur.fetchall()]

    def get_stats(self) -> Dict:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                total = cur.fetchone()[0]
                cur.execute("SELECT specialization, COUNT(*) FROM users GROUP BY specialization ORDER BY COUNT(*) DESC")
                by_spec = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '7 days'")
                new_week = cur.fetchone()[0]
                return {"total": total, "by_spec": by_spec, "new_week": new_week}
