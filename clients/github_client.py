from __future__ import annotations

import logging
from typing import Any

from github import Github, GithubException
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Config
from utils.logger import setup_logger


class GitHubClient:
    def __init__(self, config: Config, logger: "logging.Logger | None" = None) -> None:
        self._config = config
        self._logger = logger or setup_logger(config.log_level)
        self._gh = Github(config.github_token)

    def _get_repo(self, repo_name: str) -> Repository:
        """Return a GitHub Repository object for the given repo name under the org."""
        full_name = f"{self._config.github_org}/{repo_name}"
        self._logger.debug("Getting repository %s", full_name)
        try:
            return self._gh.get_repo(full_name)
        except GithubException:
            self._logger.exception("Failed to get repository %s", full_name)
            raise

    def _ensure_label(self, repo: Repository, label_name: str) -> Label:
        """Return an existing label or create it if it does not exist."""
        try:
            label = repo.get_label(label_name)
            self._logger.debug("Label '%s' already exists in %s", label_name, repo.full_name)
            return label
        except GithubException:
            self._logger.info("Creating label '%s' in %s", label_name, repo.full_name)
            try:
                return repo.create_label(name=label_name, color="ededed")
            except GithubException:
                self._logger.exception("Failed to create label '%s'", label_name)
                raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def create_issue(
        self,
        repo_name: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create a GitHub issue in the specified repository.

        Labels are created automatically if they do not already exist.
        """
        labels = labels or []
        repo = self._get_repo(repo_name)

        label_objects: list[Label] = []
        for label_name in labels:
            if not label_name.strip():
                continue
            label_objects.append(self._ensure_label(repo, label_name.strip()))

        self._logger.info(
            "Creating issue in %s: %s (labels: %s)",
            repo.full_name,
            title,
            [lbl.name for lbl in label_objects],
        )

        try:
            issue = repo.create_issue(
                title=title,
                body=body,
                labels=label_objects,
            )
        except GithubException:
            self._logger.exception("Failed to create issue in %s", repo.full_name)
            raise

        self._logger.info("Issue created #%d in %s", issue.number, repo.full_name)
        return issue