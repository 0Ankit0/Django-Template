from __future__ import annotations

from datetime import datetime
from io import BytesIO


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_invoice_pdf(*, invoice_number: str, tenant_name: str, provider: str, product_name: str, amount: str, currency: str, payment_reference: str, issued_at: datetime, period_end: datetime | None = None) -> bytes:
    lines = [
        "django-template",
        f"Invoice: {invoice_number}",
        f"Issued: {issued_at:%Y-%m-%d %H:%M UTC}",
        f"Customer: {tenant_name}",
        f"Provider: {provider.upper()}",
        "",
        f"Item: {product_name}",
        f"Amount paid: {amount} {currency.upper()}",
        f"Payment reference: {payment_reference}",
    ]
    if period_end:
        lines.append(f"Access until: {period_end:%Y-%m-%d %H:%M UTC}")

    content_lines = ["BT", "/F1 11 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index:
            content_lines.append("0 -18 Td")
        content_lines.append(f"({_pdf_escape(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj\n",
    ]

    buffer = BytesIO(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(buffer.tell())
        buffer.write(obj)
    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(),
    )
    return buffer.getvalue()
