from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    notion_token: str = field(default_factory=lambda: os.getenv("NOTION_TOKEN", ""))
    notion_database_id: str = field(
        default_factory=lambda: os.getenv("NOTION_DATABASE_ID", "")
    )
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_org: str = field(
        default_factory=lambda: os.getenv("GITHUB_ORG", "PT-SILK")
    )
    poll_interval: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL", "60"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    notion_trigger_status: str = field(
        default_factory=lambda: os.getenv("NOTION_TRIGGER_STATUS", "Ready For Engineering")
    )
    notion_success_status: str = field(
        default_factory=lambda: os.getenv("NOTION_SUCCESS_STATUS", "GitHub Issue Created")
    )
    webhook_secret: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET", "")
    )
    webhook_host: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_HOST", "[IP_ADDRESS]")
    )
    webhook_port: int = field(
        default_factory=lambda: int(os.getenv("WEBHOOK_PORT", "5000"))
    )

    def validate(self) -> None:
        missing: list[str] = []
        if not self.notion_token:
            missing.append("NOTION_TOKEN")
        if not self.notion_database_id:
            missing.append("NOTION_DATABASE_ID")
        if not self.github_token:
            missing.append("GITHUB_TOKEN")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )