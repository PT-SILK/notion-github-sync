from __future__ import annotations

import sys
import threading

from dotenv import load_dotenv

from config import Config
from services.sync_service import SyncService
from utils.logger import setup_logger
from webhooks.server import create_webhook_app


def main() -> None:
    load_dotenv()

    try:
        config = Config()
        config.validate()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    logger = setup_logger(config.log_level)

    # Start the webhook server in a background thread
    webhook_app = create_webhook_app(config, logger)

    def run_webhook() -> None:
        """Run the Flask webhook server."""
        webhook_app.run(
            host="[IP_ADDRESS]",
            port=config.webhook_port,
            debug=False,
            use_reloader=False,
        )

    webhook_thread = threading.Thread(target=run_webhook, name="webhook-server", daemon=True)
    webhook_thread.start()
    logger.info(
        "Webhook server listening on %s:%d",
        config.webhook_host,
        config.webhook_port,
    )

    # Run the polling sync service in the main thread
    service = SyncService(config)
    try:
        service.run_forever()
    except KeyboardInterrupt:
        logger.info("Sync service stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()