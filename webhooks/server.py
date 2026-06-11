"""Flask HTTP server for GitHub webhooks."""

from __future__ import annotations

import hashlib
import hmac
import logging

from flask import Flask, Response, abort, request

from config import Config
from utils.logger import setup_logger
from webhooks.handler import WebhookHandler

app = Flask(__name__)


def create_webhook_app(config: Config, logger: "logging.Logger | None" = None) -> Flask:
    """Create and configure the Flask app for webhook handling."""
    logger = logger or setup_logger(config.log_level)
    handler = WebhookHandler(config, logger)

    @app.route("/webhook", methods=["POST"])
    def github_webhook() -> tuple[Response, int]:
        event_type = request.headers.get("X-GitHub-Event", "")
        signature = request.headers.get("X-Hub-Signature-256", "")

        if config.webhook_secret:
            if not _verify_signature(request.data, signature, config.webhook_secret):
                logger.warning("Webhook: invalid signature")
                abort(403)

        if event_type != "issues":
            logger.debug("Webhook: ignoring event type '%s'", event_type)
            return Response("Ignored", status=200)

        payload = request.get_json(silent=True) or {}
        logger.info("Webhook: received issues event, action=%s", payload.get("action"))

        try:
            result = handler.handle_issue_event(payload)
            logger.info("Webhook: %s", result)
        except Exception:
            logger.exception("Webhook: error handling event")
            return Response("Error", status=500)

        return Response(result, status=200)

    return app


def _verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify the HMAC SHA-256 signature from GitHub."""
    if not signature_header:
        return False
    hash_type, signature = signature_header.split("=", 1)
    if hash_type != "sha256":
        return False
    mac = hmac.new(
        secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, signature)