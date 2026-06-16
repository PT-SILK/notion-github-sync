from __future__ import annotations

from clients.notion_client import NotionTicket


def build_issue_body(ticket: NotionTicket) -> str:
    """Build a GitHub Issue markdown body from a NotionTicket."""

    def _section(heading: str, content: str) -> str:
        if not content.strip():
            return f"**{heading}:** *(tidak ada)*"
        return f"**{heading}:** {content.strip()}"

    def _heading_section(heading: str, content: str) -> str:
        if not content.strip():
            return f"## {heading}\n\n*(tidak ada)*"
        return f"## {heading}\n\n{content.strip()}"

    parts: list[str] = [
        "## Context",
        "",
        _section("Deskripsi Masalah", ticket.deskripsi_masalah),
        _section("Dampak Bisnis", ticket.dampak_bisnis),
        "",
        _heading_section("What Needs to Be Done", ticket.what_needs_to_be_done),
        "",
        _heading_section("Acceptance Criteria", ticket.acceptance_criteria),
        "",
        "## Affected Area",
        "",
        _section("Modul", ticket.modul),
        "",
        "## References",
        "",
        _section("Notion", ticket.notion_url),
        _section("HESK", ticket.hesk_ref),
    ]
    return "\n".join(parts).strip()


def build_labels(ticket: NotionTicket) -> list[str]:
    """Extract labels from a NotionTicket (Tipe + Prioritas + Modul)."""
    labels: list[str] = []
    if ticket.tipe.strip():
        labels.append(ticket.tipe.strip())
    if ticket.prioritas.strip():
        labels.append(ticket.prioritas.strip())
    if ticket.modul.strip():
        labels.append(ticket.modul.strip())
    return labels