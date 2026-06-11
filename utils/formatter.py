from __future__ import annotations

from clients.notion_client import NotionTicket


def build_issue_body(ticket: NotionTicket) -> str:
    """Build a GitHub Issue markdown body from a NotionTicket."""

    def _section(heading: str, content: str) -> str:
        if not content.strip():
            return f"# {heading}\n\n*(tidak ada)*\n"
        return f"# {heading}\n\n{content.strip()}\n"

    parts: list[str] = [
        _section("Deskripsi Masalah", ticket.deskripsi_masalah),
        _section("Dampak Bisnis", ticket.dampak_bisnis),
        _section("What Needs to Be Done", ticket.what_needs_to_be_done),
        _section("Acceptance Criteria", ticket.acceptance_criteria),
        _section("Hesk Ref", ticket.hesk_ref),
        _section("Affected Criteria", ticket.affected_criteria),
    ]
    return "\n".join(parts).strip()


def build_labels(ticket: NotionTicket) -> list[str]:
    """Extract labels from a NotionTicket (Tipe + Prioritas)."""
    labels: list[str] = []
    if ticket.tipe.strip():
        labels.append(ticket.tipe.strip())
    if ticket.prioritas.strip():
        labels.append(ticket.prioritas.strip())
    return labels