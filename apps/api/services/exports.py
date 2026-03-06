"""
Export service — generates PDF and Excel files from composite rankings.

PDF:  WeasyPrint (CSS-based HTML → PDF)
Excel: openpyxl
"""

from __future__ import annotations

import io
from typing import Any


def generate_excel(
    rankings: list[dict[str, Any]],
    season: str,
) -> bytes:
    """Return an Excel workbook as bytes."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = f"Rankings {season}"

    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    # Collect all source columns
    source_names: list[str] = []
    if rankings:
        source_names = sorted(rankings[0].get("source_ranks", {}).keys())

    headers = ["Rank", "Player", "Team", "Position", "Score"] + [
        s.replace("_", " ").title() for s in source_names
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row in rankings:
        source_rank_vals = [
            row.get("source_ranks", {}).get(s, "") for s in source_names
        ]
        ws.append(
            [
                row["composite_rank"],
                row["name"],
                row.get("team", ""),
                row.get("position", ""),
                row["composite_score"],
            ]
            + source_rank_vals
        )

    # Auto-width columns
    for col_idx, _ in enumerate(headers, 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 15

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11px; margin: 20px; }}
  h1 {{ color: #1e3a5f; font-size: 18px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e3a5f; color: white; padding: 6px 8px; text-align: left; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) {{ background: #f4f7fb; }}
  .score {{ text-align: right; font-family: monospace; }}
  .rank  {{ text-align: center; font-weight: bold; }}
</style>
</head>
<body>
<h1>PuckLogic Fantasy Rankings — {season}</h1>
<table>
  <thead>
    <tr>
      <th>Rank</th><th>Player</th><th>Team</th><th>Pos</th><th>Score</th>
      {source_headers}
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
</body>
</html>
"""


def generate_pdf(
    rankings: list[dict[str, Any]],
    season: str,
) -> bytes:
    """Return a PDF as bytes. Requires WeasyPrint to be installed."""
    from weasyprint import HTML

    source_names: list[str] = []
    if rankings:
        source_names = sorted(rankings[0].get("source_ranks", {}).keys())

    source_headers = "".join(
        f"<th>{s.replace('_', ' ').title()}</th>" for s in source_names
    )

    rows_html = ""
    for row in rankings:
        src_cells = "".join(
            f"<td class='rank'>{row.get('source_ranks', {}).get(s, '—')}</td>"
            for s in source_names
        )
        rows_html += (
            f"<tr>"
            f"<td class='rank'>{row['composite_rank']}</td>"
            f"<td>{row['name']}</td>"
            f"<td>{row.get('team', '')}</td>"
            f"<td>{row.get('position', '')}</td>"
            f"<td class='score'>{row['composite_score']:.4f}</td>"
            f"{src_cells}"
            f"</tr>\n"
        )

    html_content = _HTML_TEMPLATE.format(
        season=season,
        source_headers=source_headers,
        rows=rows_html,
    )

    return HTML(string=html_content).write_pdf()
