from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://kyc_user:kyc_password@localhost:5432/kyc_analytics",
)


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_dimensions(*, user_id: str, merchant_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO merchants (merchant_id)
                VALUES (%s)
                ON CONFLICT (merchant_id) DO NOTHING
                """,
                (merchant_id,),
            )


def log_verification(
    *,
    user_id: str,
    merchant_id: str,
    document_type: str,
    tamper_score: float,
    authentic_confidence: float,
    flagged_status: str,
    risk_tier: str,
    intervention: str,
    processing_time_ms: int,
    ip_address: str | None,
    escalation_reason: str | None = None,
) -> str:
    verification_id = str(uuid.uuid4())

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO merchants (merchant_id)
                VALUES (%s)
                ON CONFLICT (merchant_id) DO NOTHING
                """,
                (merchant_id,),
            )
            cur.execute(
                """
                INSERT INTO verifications (
                    verification_id,
                    user_id,
                    merchant_id,
                    document_type,
                    tamper_score,
                    authentic_confidence,
                    flagged_status,
                    risk_tier,
                    intervention,
                    processing_time_ms,
                    ip_address
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    verification_id,
                    user_id,
                    merchant_id,
                    document_type,
                    tamper_score,
                    authentic_confidence,
                    flagged_status,
                    risk_tier,
                    intervention,
                    processing_time_ms,
                    ip_address,
                ),
            )

            if intervention == "BLOCK_AND_ESCALATE":
                cur.execute(
                    """
                    INSERT INTO fraud_escalations (verification_id, reason)
                    VALUES (%s, %s)
                    """,
                    (verification_id, escalation_reason or "High-risk automated KYC signal"),
                )

    return verification_id


def database_ready() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
    except psycopg.Error:
        return False
