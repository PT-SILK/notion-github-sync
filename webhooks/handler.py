"""GitHub webhook event → Notion status mapping."""

from __future__ import annotations

import logging
from typing import Any

from clients.notion_client import NotionClient
from config import Config

# Mapping: GitHub issue action → Notion Status
STATUS_MAP: dict[str, str] = {
    "assigned": "Assigned",
    "labeled_in_progress": "In progress",
    "labeled_in_review": "In Review",
    "labeled_blocked": "Blocked",
    "closed": "Closed",
    "reopened": "GitHub Issue Created",
    "labeled_done": "Done",
}

# Which label names trigger status changes
LABEL_STATUS_MAP: dict[str, str] = {
    "in progress": "In progress",
    "in review": "In Review",
    "blocked": "Blocked",
    "done": "Done",
}


class WebhookHandler:
    """Handle incoming GitHub webhook events and update Notion accordingly."""

    def __init__(self, config: Config, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._notion = NotionClient(config, logger)

    def handle_issue_event(self, payload: dict[str, Any]) -> str:
        """Process a GitHub issues event and return a status message.

        Supported actions:
          - assigned: developer assigned → "Assigned"
          - labeled: check label name → mapped status
          - unlabeled: if was status label → revert to "In progress"
          - closed: issue closed → "Closed"
          - reopened: issue reopened → "GitHub Issue Created"
        """
        action: str = payload.get("action", "")
        issue_data: dict[str, Any] = payload.get("issue", {})
        issue_url: str = issue_data.get("html_url", "")

        if not issue_url:
            return "No issue URL in payload, skipped"

        ticket = self._notion.find_page_by_issue_url(issue_url)
        if ticket is None:
            return f"No Notion page found for {issue_url}, skipped"

        new_status: str | None = self._resolve_status(action, payload)

        if new_status is None:
            return f"Action '{action}' does not trigger status change, skipped"

        self._logger.info(
            "Webhook: issue %s action=%s → Notion status='%s' (page %s)",
            issue_url, action, new_status, ticket.page_id,
        )

        self._notion.update_page_status(ticket, new_status)
        return f"Updated page {ticket.page_id} → '{new_status}'"

    def _resolve_status(self, action: str, payload: dict[str, Any]) -> str | None:
        """Determine target Notion status from the webhook event."""
        if action == "assigned":
            assignee = payload.get("assignee")
            if assignee:
                return STATUS_MAP["assigned"]
            return None

        if action == "labeled":
            label: dict[str, Any] = payload.get("label") or {}
            label_name: str = (label.get("name", "") or "").lower()
            for label_key, status_value in LABEL_STATUS_MAP.items():
                if label_key in label_name:
                    return status_value
            return None

        if action == "unlabeled":
            label: dict[str, Any] = payload.get("label") or {}
            label_name: str = (label.get("name", "") or "").lower()
            for label_key in LABEL_STATUS_MAP:
                if label_key in label_name:
                    return "In progress"
            return None

        if action == "closed":
            return STATUS_MAP["closed"]

        if action == "reopened":
            return STATUS_MAP["reopened"]

        return None