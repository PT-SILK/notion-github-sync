from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from notion_client import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Config
from utils.logger import setup_logger


@dataclass
class NotionTicket:
    page_id: str = ""
    notion_url: str = ""
    judul: str = ""
    tipe: str = ""
    prioritas: str = ""
    modul: str = ""
    deskripsi_masalah: str = ""
    dampak_bisnis: str = ""
    what_needs_to_be_done: str = ""
    acceptance_criteria: str = ""
    hesk_ref: str = ""
    affected_criteria: str = ""
    github_issue_number: str = ""
    github_issue_url: str = ""
    status: str = ""


def _get_plain_text(prop: Any) -> str:
    """Safely extract plain text from a Notion rich_text / title property."""
    if not prop:
        return ""
    try:
        rich_text = prop.get("rich_text") or prop.get("title") or []
        return "".join(part.get("plain_text", "") for part in rich_text if part)
    except (AttributeError, TypeError):
        return ""


def _get_select_value(prop: Any) -> str:
    """Safely extract the name of a Notion select property."""
    if not prop:
        return ""
    try:
        select = prop.get("select")
        if select and isinstance(select, dict):
            return select.get("name", "")
        return ""
    except (AttributeError, TypeError):
        return ""


def _get_status_value(prop: Any) -> str:
    """Safely extract the name of a Notion status property."""
    if not prop:
        return ""
    try:
        status = prop.get("status")
        if status and isinstance(status, dict):
            return status.get("name", "")
        return ""
    except (AttributeError, TypeError):
        return ""


def _get_formula_value(prop: Any) -> str:
    """Safely extract a Notion formula property result."""
    if not prop:
        return ""
    try:
        formula = prop.get("formula")
        if formula and isinstance(formula, dict):
            # Formula results can be string, number, boolean, etc.
            ftype = formula.get("type", "")
            if ftype == "string":
                return formula.get("string") or ""
            if ftype == "number":
                return str(formula.get("number", ""))
            return str(formula.get(ftype, ""))
        return ""
    except (AttributeError, TypeError):
        return ""


def _get_url_value(prop: Any) -> str:
    """Safely extract a Notion url property."""
    if not prop:
        return ""
    try:
        return prop.get("url") or ""
    except (AttributeError, TypeError):
        return ""


class NotionClient:
    def __init__(self, config: Config, logger: "logging.Logger | None" = None) -> None:
        self._config = config
        self._logger = logger or setup_logger(config.log_level)
        self._client = Client(auth=config.notion_token)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def query_database(self) -> list[dict[str, Any]]:
        """Return raw page objects from Notion where 'Create GitHub Issue' checkbox is checked."""
        self._logger.info("Querying Notion database %s", self._config.notion_database_id)

        try:
            response = self._client.databases.query(
                database_id=self._config.notion_database_id,
                filter={
                    "and": [
                        {
                            "property": "Create GitHub Issue",
                            "checkbox": {"equals": True},
                        },
                        {
                            "property": "GitHub Issue Number",
                            "rich_text": {"is_empty": True},
                        },
                    ]
                },
            )
        except Exception:
            self._logger.exception("Failed to query Notion database")
            raise

        pages: list[dict[str, Any]] = response.get("results", [])
        self._logger.info("Found %d page(s) with Create GitHub Issue checked", len(pages))
        return pages

    @staticmethod
    def parse_page(page: dict[str, Any], logger: "logging.Logger | None" = None) -> NotionTicket:
        props: dict[str, Any] = page.get("properties", {})
        page_id = page.get("id", "")
        notion_url = f"https://www.notion.so/{page_id.replace('-', '')}" if page_id else ""

        # Debug: log all property names and their types
        if logger:
            prop_names = sorted(props.keys())
            logger.info("Page %s has properties: %s", page_id, prop_names)
            for pname in prop_names:
                pval = props.get(pname, {})
                ptype = pval.get("type", "unknown")
                logger.info("  Property '%s' → type=%s", pname, ptype)

        return NotionTicket(
            page_id=page_id,
            notion_url=notion_url,
            judul=_get_plain_text(props.get("Judul")),
            tipe=_get_select_value(props.get("Tipe")),
            prioritas=_get_select_value(props.get("Prioritas")),
            modul=_get_select_value(props.get("Modul/Area Sistem")),
            deskripsi_masalah=_get_plain_text(props.get("Deskripsi Masalah")),
            dampak_bisnis=_get_plain_text(props.get("Dampak Bisnis")),
            what_needs_to_be_done=_get_plain_text(props.get("What Needs To Be Done")),
            acceptance_criteria=_get_plain_text(props.get("Acceptance Criteria")),
            hesk_ref=_get_formula_value(props.get("Hesk Ref")),
            affected_criteria=_get_plain_text(props.get("Affected Area")),
            github_issue_number=_get_plain_text(props.get("GitHub Issue Number")),
            github_issue_url=_get_url_value(props.get("GitHub Issue URL")),
            status=_get_status_value(props.get("Status")),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def update_page_after_sync(self, ticket: NotionTicket, github_issue_number: int, github_issue_url: str) -> None:
        """Update a Notion page with GitHub issue data and change status.
        
        Note: 'Create GitHub Issue' checkbox is NOT unchecked here.
        It stays checked so the webhook can still identify this page
        and update its status when GitHub events occur (e.g. assigned).
        """
        self._logger.info("Updating Notion page %s with issue #%d", ticket.page_id, github_issue_number)

        try:
            self._client.pages.update(
                page_id=ticket.page_id,
                properties={
                    "GitHub Issue Number": {
                        "rich_text": [{"text": {"content": str(github_issue_number)}}]
                    },
                    "GitHub Issue URL": {"url": github_issue_url},
                    "Status": {"status": {"name": self._config.notion_success_status}},
                },
            )
        except Exception:
            self._logger.exception("Failed to update Notion page %s", ticket.page_id)
            raise

        self._logger.info("Notion page %s updated successfully", ticket.page_id)

    def find_page_by_issue_url(self, issue_url: str) -> NotionTicket | None:
        """Find a Notion page by its GitHub Issue URL."""
        self._logger.info("Searching Notion for issue URL: %s", issue_url)

        try:
            response = self._client.databases.query(
                database_id=self._config.notion_database_id,
                filter={
                    "property": "GitHub Issue URL",
                    "url": {"equals": issue_url},
                },
            )
        except Exception:
            self._logger.exception("Failed to query Notion by issue URL")
            return None

        pages: list[dict[str, Any]] = response.get("results", [])
        if not pages:
            self._logger.warning("No Notion page found for URL: %s", issue_url)
            return None

        self._logger.info("Found page %s for URL %s", pages[0].get("id"), issue_url)
        return self.parse_page(pages[0])

    def update_page_status(self, ticket: NotionTicket, new_status: str) -> None:
        """Update only the Status field of a Notion page."""
        self._logger.info(
            "Updating page %s status → '%s'", ticket.page_id, new_status
        )

        try:
            self._client.pages.update(
                page_id=ticket.page_id,
                properties={
                    "Status": {"status": {"name": new_status}},
                },
            )
        except Exception:
            self._logger.exception(
                "Failed to update status for page %s", ticket.page_id
            )
            raise

        self._logger.info("Page %s status updated to '%s'", ticket.page_id, new_status)
