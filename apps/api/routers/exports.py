from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from core.dependencies import get_rankings_repository
from models.schemas import ExportRequest
from repositories.rankings import RankingsRepository
from services.exports import generate_excel, generate_pdf
from services.rankings import compute_weighted_rankings, flatten_db_rankings

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/generate")
async def generate_export(
    req: ExportRequest,
    repo: RankingsRepository = Depends(get_rankings_repository),
) -> Response:
    """Compute rankings and stream the result as a PDF or Excel file."""
    rows = repo.get_by_season(req.season)
    source_rankings = flatten_db_rankings(rows)
    ranked = compute_weighted_rankings(source_rankings, req.weights)

    filename = f"pucklogic-rankings-{req.season}"

    if req.export_type == "excel":
        content = generate_excel(ranked, req.season)
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    content = generate_pdf(ranked, req.season)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )
