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

    header_fill = PatternFill(
        start_color="1E3A5F", end_color="1E3A5F", fill_type="solid"
    )
    header_font = Font(color="FFFFFF", bold=True)

    headers = [
        "Rank", "Player", "Team", "Pos", "FanPts", "VORP",
        "OffNightGames", "Sources",
        "G", "A", "PPP", "SOG", "Hits", "Blocks", "GP",
        "W", "GAA", "SV%",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row in rankings:
        stats = row.get("projected_stats", {})
        ws.append([
            row["composite_rank"],
            row.get("name", ""),
            row.get("team", ""),
            row.get("default_position", ""),
            _fmt(row.get("projected_fantasy_points")),
            _fmt(row.get("vorp")),
            row.get("off_night_games", ""),
            row.get("source_count", 0),
            _fmt(stats.get("g")),
            _fmt(stats.get("a")),
            _fmt(stats.get("ppp")),
            _fmt(stats.get("sog")),
            _fmt(stats.get("hits")),
            _fmt(stats.get("blocks")),
            _fmt(stats.get("gp")),
            _fmt(stats.get("w")),
            _fmt(stats.get("ga")),
            _fmt(stats.get("sv_pct")),
        ])

    for col_idx, _ in enumerate(headers, 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 12

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _fmt(val: float | int | None) -> str | float | int:
    """Format a nullable numeric for the spreadsheet."""
    if val is None:
        return ""
    if isinstance(val, float):
        return round(val, 2)
    return val


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
  .num {{ text-align: right; font-family: monospace; }}
  .rank {{ text-align: center; font-weight: bold; }}
</style>
</head>
<body>
<h1>PuckLogic Fantasy Rankings — {season}</h1>
<table>
  <thead>
    <tr>
      <th>Rank</th><th>Player</th><th>Team</th><th>Pos</th>
      <th>FanPts</th><th>VORP</th><th>Off-Night</th>
      <th>G</th><th>A</th><th>PPP</th><th>SOG</th>
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

    rows_html = ""
    for row in rankings:
        stats = row.get("projected_stats", {})
        fp = row.get("projected_fantasy_points")
        vorp = row.get("vorp")
        rows_html += (
            f"<tr>"
            f"<td class='rank'>{row['composite_rank']}</td>"
            f"<td>{row.get('name', '')}</td>"
            f"<td>{row.get('team', '')}</td>"
            f"<td>{row.get('default_position', '')}</td>"
            f"<td class='num'>{round(fp, 1) if fp is not None else '—'}</td>"
            f"<td class='num'>{round(vorp, 1) if vorp is not None else '—'}</td>"
            f"<td class='num'>{row.get('off_night_games', '—')}</td>"
            f"<td class='num'>{_fmt(stats.get('g'))}</td>"
            f"<td class='num'>{_fmt(stats.get('a'))}</td>"
            f"<td class='num'>{_fmt(stats.get('ppp'))}</td>"
            f"<td class='num'>{_fmt(stats.get('sog'))}</td>"
            f"</tr>\n"
        )

    html_content = _HTML_TEMPLATE.format(season=season, rows=rows_html)
    return HTML(string=html_content).write_pdf()
