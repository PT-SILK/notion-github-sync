from __future__ import annotations

import logging
import time

from github import GithubException

from clients.github_client import GitHubClient
from clients.notion_client import NotionClient, NotionTicket
from config import Config
from utils.formatter import build_issue_body, build_labels
from utils.logger import setup_logger


def _clean_repo_name(raw: str) -> str:
    """Clean repository name from Notion select value.

    Notion appends visibility suffixes like " Private", " Public" etc.
    Strip those and return the clean repo name.
    """
    cleaned = raw.strip()
    for suffix in (" Private", " Public", " Internal"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned


class SyncService:
    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config()
        self._config.validate()
        self._logger = setup_logger(self._config.log_level)
        self._notion = NotionClient(self._config, self._logger)
        self._github = GitHubClient(self._config, self._logger)

    def run_once(self) -> dict[str, int]:
        """Execute one sync cycle.

        Returns a dict with counters: {'created': int, 'failed': int, 'skipped': int}.
        """
        counters = {"created": 0, "failed": 0, "skipped": 0}

        try:
            pages = self._notion.query_database()
        except Exception:
            self._logger.exception("Sync cycle aborted - failed to query Notion")
            return counters

        for page in pages:
            ticket = self._notion.parse_page(page, logger=self._logger)

            repo_name = _clean_repo_name(ticket.modul)

            if not repo_name:
                self._logger.warning(
                    "Skipping page %s - 'Modul' field is empty", ticket.page_id
                )
                counters["skipped"] += 1
                continue

            if not ticket.judul.strip():
                self._logger.warning(
                    "Skipping page %s - 'Judul' field is empty", ticket.page_id
                )
                counters["skipped"] += 1
                continue

            try:
                body = build_issue_body(ticket)
                labels = build_labels(ticket)

                issue = self._github.create_issue(
                    repo_name=repo_name,
                    title=ticket.judul.strip(),
                    body=body,
                    labels=labels,
                )

                self._notion.update_page_after_sync(
                    ticket=ticket,
                    github_issue_number=issue.number,
                    github_issue_url=issue.html_url,
                )

                counters["created"] += 1
                self._logger.info(
                    "Issue #%d created for page %s -> %s",
                    issue.number,
                    ticket.page_id,
                    issue.html_url,
                )

            except GithubException:
                self._logger.exception(
                    "Failed creating issue for page %s (repo: %s)",
                    ticket.page_id,
                    ticket.modul,
                )
                counters["failed"] += 1
            except Exception:
                self._logger.exception(
                    "Unexpected error processing page %s", ticket.page_id
                )
                counters["failed"] += 1

        return counters

    def run_forever(self) -> None:
        """Run the sync loop continuously with the configured poll interval."""
        self._logger.info(
            "Sync service started - polling every %d seconds", self._config.poll_interval
        )

        while True:
            self._logger.info("Sync cycle started")
            counters = self.run_once()

            self._logger.info(
                "Sync cycle finished - created: %d, failed: %d, skipped: %d",
                counters["created"],
                counters["failed"],
                counters["skipped"],
            )

            self._logger.info(
                "Sleeping for %d seconds...", self._config.poll_interval
            )
            time.sleep(self._config.poll_interval)