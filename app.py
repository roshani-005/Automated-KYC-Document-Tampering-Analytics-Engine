from __future__ import annotations

import os
import time

from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from database import database_ready, log_verification
from detector import DocumentTamperDetector
from risk import classify_risk


ALLOWED_DOCUMENT_TYPES = {"PAN", "AADHAAR", "GSTIN"}
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

detector = DocumentTamperDetector()


def _client_ip() -> str | None:
    # Only trust X-Forwarded-For when the service is behind a configured trusted
    # proxy. For a local/demo deployment, prefer Flask's direct remote address.
    return request.remote_addr


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(_: RequestEntityTooLarge):
    return jsonify({"error": "document exceeds maximum upload size"}), 413


@app.get("/health")
def health():
    return jsonify(
        {
            "service": "kyc-fraud-risk-engine",
            "status": "ok",
            "database": "ready" if database_ready() else "unavailable",
        }
    )


@app.post("/api/v1/verifications")
def create_verification():
    started = time.perf_counter()

    user_id = (request.form.get("user_id") or "").strip()
    merchant_id = (request.form.get("merchant_id") or "").strip()
    document_type = (request.form.get("document_type") or "").strip().upper()
    document = request.files.get("document")

    missing = [
        name
        for name, value in (
            ("user_id", user_id),
            ("merchant_id", merchant_id),
            ("document_type", document_type),
            ("document", document),
        )
        if not value
    ]
    if missing:
        return jsonify({"error": f"missing required fields: {', '.join(missing)}"}), 400

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        return jsonify({"error": "document_type must be PAN, AADHAAR, or GSTIN"}), 400

    if not document.filename or _extension(document.filename) not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "document must be a PNG or JPEG image"}), 400

    payload = document.read()
    if not payload:
        return jsonify({"error": "uploaded document is empty"}), 400

    try:
        detection = detector.score(payload)
    except (ValueError, OSError) as exc:
        return jsonify({"error": f"invalid document image: {exc}"}), 400

    decision = classify_risk(
        tamper_score=detection.tamper_score,
        authentic_confidence=detection.authentic_confidence,
    )
    processing_time_ms = max(0, round((time.perf_counter() - started) * 1000))

    try:
        verification_id = log_verification(
            user_id=user_id,
            merchant_id=merchant_id,
            document_type=document_type,
            tamper_score=detection.tamper_score,
            authentic_confidence=detection.authentic_confidence,
            flagged_status=decision.flagged_status,
            risk_tier=decision.risk_tier,
            intervention=decision.intervention,
            processing_time_ms=processing_time_ms,
            ip_address=_client_ip(),
            escalation_reason=decision.reason,
        )
    except Exception as exc:
        app.logger.exception("failed to persist verification")
        return jsonify({"error": "verification could not be persisted"}), 503

    return (
        jsonify(
            {
                "verification_id": verification_id,
                "document_type": document_type,
                "tamper_score": detection.tamper_score,
                "authentic_confidence": detection.authentic_confidence,
                "flagged_status": decision.flagged_status,
                "risk_tier": decision.risk_tier,
                "intervention": decision.intervention,
                "processing_time_ms": processing_time_ms,
                "forensic_signals": {
                    "ela": detection.ela_signal,
                    "texture": detection.texture_signal,
                },
            }
        ),
        201,
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
