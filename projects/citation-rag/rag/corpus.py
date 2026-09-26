"""A tiny sample corpus so the project runs with zero setup.

Three short "documents" chunked by section. Swap load_corpus() for your own loader
(PDF/Confluence/Notion/DB) and everything downstream is unchanged.
"""
from __future__ import annotations

from .retriever import Chunk


def load_corpus() -> list[Chunk]:
    return [
        Chunk("returns-policy", "§1 Eligibility",
              "Items are eligible for return if they are unused and in original packaging. "
              "Final-sale and personalized items cannot be returned."),
        Chunk("returns-policy", "§2 Timeframe",
              "Customers may request a return within 30 days of delivery. Requests after 30 days "
              "are declined automatically."),
        Chunk("returns-policy", "§3 Refund method",
              "Approved refunds are issued to the original payment method within 5 to 7 business "
              "days after the item is received at the warehouse."),
        Chunk("security-whitepaper", "§4 Data encryption",
              "All customer data is encrypted in transit with TLS 1.2 or higher and at rest with "
              "AES-256. Encryption keys are rotated every 90 days."),
        Chunk("security-whitepaper", "§7 Access control",
              "Production access follows least privilege. Every access grant is logged and access "
              "reviews are performed quarterly."),
        Chunk("sla", "§2 Uptime",
              "The service targets 99.9 percent monthly uptime. Scheduled maintenance is announced "
              "at least 48 hours in advance and does not count against the uptime target."),
        Chunk("sla", "§5 Support response",
              "Critical incidents receive a first response within one hour. Standard requests "
              "receive a first response within one business day."),
    ]
