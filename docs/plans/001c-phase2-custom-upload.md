# Phase 2 Custom Source Upload Backend Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three endpoints to the sources router: `POST /sources/upload` (parse CSV/Excel, match players, upsert projections), `GET /sources/custom` (list user's custom sources), and `DELETE /sources/{id}` (owner-scoped delete + cache invalidation). Enforce a 2-slot limit per user.

**Architecture:** Upload handler uses `pandas` to parse the file, `PlayerMatcher` for name resolution, and the existing `CacheService.invalidate_rankings()` for cache busting. All three endpoints extend `routers/sources.py`. No new router file needed.

**Tech Stack:** FastAPI `UploadFile`, `pandas`, `rapidfuzz` (via `PlayerMatcher`), Supabase service role client.

**Prerequisites:**
- `scrapers/matching.py` (PlayerMatcher) — from projection scrapers plan
- `scrapers/projection/__init__.py` (shared helpers) — from projection scrapers plan

---

## Files

| Action | Path |
|--------|------|
| Modify | `apps/api/routers/sources.py` — add upload, list-custom, delete endpoints |
| Modify | `apps/api/models/schemas.py` — add upload response schemas |
| Modify | `apps/api/tests/routers/test_sources.py` — add tests for new endpoints |

---

## Chunk 1: Schemas + GET /sources/custom

### Task 1: Add upload schemas to models/schemas.py

**Files:**
- Modify: `apps/api/models/schemas.py`

- [ ] **Step 1: Append upload-related schemas**

Add to the end of `apps/api/models/schemas.py`:

```python
# ---------------------------------------------------------------------------
# Custom source upload
# ---------------------------------------------------------------------------


class UnmatchedPlayer(BaseModel):
    row_number: int
    original_name: str
    closest_match: str | None = None
    match_score: float | None = None


class CustomSourceOut(BaseModel):
    id: str
    name: str
    display_name: str
    player_count: int
    season: str
    created_at: datetime


class UploadResponse(BaseModel):
    source_id: str
    rows_upserted: int
    unmatched: list[UnmatchedPlayer]
    slots_used: int
    slots_total: int = 2
```

- [ ] **Step 2: Run tests to confirm no regressions**

```bash
cd apps/api && pytest tests/ -x -q
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/models/schemas.py
git commit -m "feat(sources): add CustomSourceOut, UploadResponse, UnmatchedPlayer schemas"
```

---

### Task 2: Write failing tests for GET /sources/custom and DELETE /sources/{id}

**Files:**
- Modify: `apps/api/tests/routers/test_sources.py`

- [ ] **Step 1: Add new test classes**

Append to `apps/api/tests/routers/test_sources.py`:

```python
# ---- Add these imports at the top of the existing test file ----
# from core.dependencies import get_current_user, get_cache_service
# from services.cache import CacheService

# ---- Append these test classes to the file ----

CUSTOM_SOURCE = {
    "id": "cs1",
    "name": "my_source",
    "display_name": "My Source",
    "user_id": "u1",
    "active": True,
    "is_paid": False,
}

AUTH_USER = {"id": "u1", "email": "user@test.com"}


class TestListCustomSources:
    @pytest.fixture(autouse=True)
    def setup(self, mock_source_repo: MagicMock) -> None:
        mock_source_repo.list_custom.return_value = [CUSTOM_SOURCE]
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/sources/custom").status_code == 200

    def test_returns_list(self, client: TestClient) -> None:
        data = client.get("/sources/custom").json()
        assert isinstance(data, list)

    def test_calls_list_custom_with_user_id(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        client.get("/sources/custom")
        mock_source_repo.list_custom.assert_called_once_with(user_id="u1")

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        assert client.get("/sources/custom").status_code == 401


class TestDeleteSource:
    @pytest.fixture(autouse=True)
    def setup(self, mock_source_repo: MagicMock) -> None:
        mock_source_repo.delete_custom.return_value = True
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER
        mock_cache = MagicMock()
        app.dependency_overrides[get_cache_service] = lambda: mock_cache

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_returns_204_on_success(self, client: TestClient) -> None:
        assert client.delete("/sources/cs1").status_code == 204

    def test_returns_404_when_not_found(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        mock_source_repo.delete_custom.return_value = False
        assert client.delete("/sources/cs1").status_code == 404

    def test_calls_invalidate_cache(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        from core.dependencies import get_cache_service
        mock_cache = MagicMock()
        app.dependency_overrides[get_cache_service] = lambda: mock_cache
        client.delete("/sources/cs1")
        mock_cache.invalidate_rankings.assert_called_once()
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd apps/api && pytest tests/routers/test_sources.py -v -k "custom or delete"
```

Expected: FAIL (endpoints don't exist yet)

---

### Task 3: Add list_custom and delete_custom to SourceRepository

**Files:**
- Modify: `apps/api/repositories/sources.py`

- [ ] **Step 1: Add two methods**

```python
def list_custom(self, user_id: str) -> list[dict[str, Any]]:
    """Return custom sources owned by user_id, with player projection count."""
    result = (
        self._db.table("sources")
        .select("id, name, display_name, user_id, active, created_at")
        .eq("user_id", user_id)
        .eq("active", True)
        .execute()
    )
    sources = result.data
    # Attach player_count per source
    for source in sources:
        count_result = (
            self._db.table("player_projections")
            .select("id", count="exact")
            .eq("source_id", source["id"])
            .execute()
        )
        source["player_count"] = count_result.count or 0
        source["season"] = ""  # populated below if projections exist
        if count_result.data:
            # Get the season from the first row
            season_result = (
                self._db.table("player_projections")
                .select("season")
                .eq("source_id", source["id"])
                .limit(1)
                .execute()
            )
            if season_result.data:
                source["season"] = season_result.data[0]["season"]
    return sources

def delete_custom(self, source_id: str, user_id: str) -> bool:
    """Delete a custom source (and cascade player_projections via FK).

    Returns True if a row was deleted, False if not found or not owned by user.
    """
    result = (
        self._db.table("sources")
        .delete()
        .eq("id", source_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)

def count_custom(self, user_id: str) -> int:
    """Count active custom sources owned by user_id."""
    result = (
        self._db.table("sources")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("active", True)
        .execute()
    )
    return result.count or 0
```

- [ ] **Step 2: Write repository unit tests**

Add to `apps/api/tests/repositories/test_sources.py`:

```python
class TestListCustom:
    def test_filters_by_user_id(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = []
        repo.list_custom(user_id="u1")
        # Verify user_id filter was applied
        mock_db.table.assert_called_with("sources")

class TestDeleteCustom:
    def test_returns_true_when_deleted(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.delete.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = [{"id": "cs1"}]
        assert repo.delete_custom("cs1", "u1") is True

    def test_returns_false_when_not_found(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.delete.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = []
        assert repo.delete_custom("cs1", "u1") is False
```

- [ ] **Step 3: Run repository tests**

```bash
cd apps/api && pytest tests/repositories/test_sources.py -v
```

---

### Task 4: Add GET /sources/custom and DELETE /sources/{id} to router

**Files:**
- Modify: `apps/api/routers/sources.py`

- [ ] **Step 1: Add imports and two new endpoints**

In `apps/api/routers/sources.py`, add:

```python
# Add to imports
from typing import Any
from core.dependencies import get_cache_service, get_current_user
from models.schemas import CustomSourceOut
from services.cache import CacheService

# Add to router (append to existing file)

@router.get("/custom", response_model=list[CustomSourceOut])
async def list_custom_sources(
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
) -> list[CustomSourceOut]:
    """Return the authenticated user's custom projection sources."""
    rows = repo.list_custom(user_id=user["id"])
    return [CustomSourceOut(**row) for row in rows]


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
    cache: CacheService = Depends(get_cache_service),
) -> None:
    """Delete a custom source. Only the owning user may delete."""
    deleted = repo.delete_custom(source_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    from core.config import settings
    cache.invalidate_rankings(settings.current_season)
```

- [ ] **Step 2: Run the new router tests**

```bash
cd apps/api && pytest tests/routers/test_sources.py -v -k "custom or delete"
```

Expected: All pass.

- [ ] **Step 3: Run full suite + lint**

```bash
cd apps/api && pytest tests/ -q && ruff check .
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/routers/sources.py apps/api/repositories/sources.py \
        apps/api/models/schemas.py apps/api/tests/routers/test_sources.py \
        apps/api/tests/repositories/test_sources.py
git commit -m "feat(sources): add GET /sources/custom and DELETE /sources/{id}"
```

---

## Chunk 2: POST /sources/upload

### Task 5: Write failing tests for POST /sources/upload

**Files:**
- Modify: `apps/api/tests/routers/test_sources.py`

- [ ] **Step 1: Add upload test class**

```python
import io

class TestUploadSource:
    COLUMN_MAP = '{"Goals": "g", "Assists": "a", "GP": "gp"}'
    CSV_CONTENT = "Player,Goals,Assists,GP\nConnor McDavid,52,72,82\nUnknown Player,10,10,50"

    @pytest.fixture(autouse=True)
    def setup(self, mock_source_repo: MagicMock) -> None:
        mock_source_repo.count_custom.return_value = 0  # slots available
        mock_source_repo.upsert_custom.return_value = "src-new"
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER
        # Mock DB for player matching
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute.return_value.data = [
            {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"}
        ]
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-new"}]
        from core.dependencies import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/upload",
            files={"file": ("proj.csv", io.BytesIO(self.CSV_CONTENT.encode()), "text/csv")},
            data={"source_name": "My Source", "season": "2025-26", "column_map": self.COLUMN_MAP},
        )
        assert resp.status_code == 200

    def test_returns_upload_response_shape(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/upload",
            files={"file": ("proj.csv", io.BytesIO(self.CSV_CONTENT.encode()), "text/csv")},
            data={"source_name": "My Source", "season": "2025-26", "column_map": self.COLUMN_MAP},
        ).json()
        assert "source_id" in resp
        assert "rows_upserted" in resp
        assert "unmatched" in resp
        assert "slots_used" in resp

    def test_slot_limit_returns_400(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        mock_source_repo.count_custom.return_value = 2  # already at limit
        resp = client.post(
            "/sources/upload",
            files={"file": ("proj.csv", io.BytesIO(self.CSV_CONTENT.encode()), "text/csv")},
            data={"source_name": "My Source", "season": "2025-26", "column_map": self.COLUMN_MAP},
        )
        assert resp.status_code == 400
        assert "slot" in resp.json()["detail"].lower()

    def test_invalid_file_type_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/upload",
            files={"file": ("bad.txt", io.BytesIO(b"not a csv"), "text/plain")},
            data={"source_name": "My Source", "season": "2025-26", "column_map": self.COLUMN_MAP},
        )
        assert resp.status_code == 400

    def test_file_too_large_returns_400(self, client: TestClient) -> None:
        large_content = b"a,b\n" + b"x,y\n" * 200_000  # ~2MB
        resp = client.post(
            "/sources/upload",
            files={"file": ("big.csv", io.BytesIO(large_content), "text/csv")},
            data={"source_name": "My Source", "season": "2025-26", "column_map": self.COLUMN_MAP},
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd apps/api && pytest tests/routers/test_sources.py::TestUploadSource -v
```

Expected: FAIL (endpoint doesn't exist)

---

### Task 6: Add upsert_custom to SourceRepository

**Files:**
- Modify: `apps/api/repositories/sources.py`

- [ ] **Step 1: Add upsert_custom method**

```python
def upsert_custom(
    self, user_id: str, source_name: str, display_name: str
) -> str:
    """Create or update a custom source row for user_id. Returns source UUID."""
    result = (
        self._db.table("sources")
        .upsert(
            {
                "name": source_name,
                "display_name": display_name,
                "user_id": user_id,
                "is_paid": False,
                "active": True,
            },
            on_conflict="name,user_id",
        )
        .execute()
    )
    return result.data[0]["id"]
```

---

### Task 7: Implement POST /sources/upload

**Files:**
- Modify: `apps/api/routers/sources.py`

- [ ] **Step 1: Add upload endpoint**

```python
# Additional imports needed at top of routers/sources.py:
import json
from fastapi import File, Form, UploadFile
from models.schemas import UnmatchedPlayer, UploadResponse
from scrapers.matching import PlayerMatcher
from scrapers.projection import apply_column_map, upsert_projection_row

FREE_SLOT_LIMIT = 2  # Custom source slots for free users
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_CONTENT_TYPES = {"text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


@router.post("/upload", response_model=UploadResponse)
async def upload_custom_source(
    file: UploadFile = File(...),
    source_name: str = Form(...),
    season: str = Form(...),
    column_map: str = Form(..., description="JSON: {their_col: our_stat}"),
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
    cache: CacheService = Depends(get_cache_service),
    db: Any = Depends(get_db),
) -> UploadResponse:
    """Upload a CSV or Excel projection file as a custom source.

    - Max 5MB file size
    - Max 2 custom source slots per user
    - Unmatched players returned in response (not an error)
    - Cache invalidated on success
    """
    # Validate file type
    suffix = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 5MB limit")

    # Check slot limit
    slots_used = repo.count_custom(user["id"])
    if slots_used >= FREE_SLOT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Custom source slot limit reached ({FREE_SLOT_LIMIT} slots). Delete an existing custom source to upload a new one.",
        )

    # Parse column_map JSON
    try:
        col_map: dict[str, str] = json.loads(column_map)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid column_map JSON: {exc}") from exc

    # Parse file with pandas
    try:
        import io
        import pandas as pd
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    # Upsert source row
    source_id = repo.upsert_custom(
        user_id=user["id"],
        source_name=f"custom_{user['id'][:8]}_{source_name.lower().replace(' ', '_')}",
        display_name=source_name,
    )

    # Build player matcher
    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id, source").execute().data
    matcher = PlayerMatcher(players, aliases)

    # Process rows
    from rapidfuzz import fuzz, process as fuzz_process
    player_names = [p["name"] for p in players]
    rows_upserted = 0
    unmatched: list[UnmatchedPlayer] = []

    for row_idx, row in enumerate(df.to_dict("records")):
        # Find player name column: first column not in col_map values
        player_name_col = next(
            (col for col in df.columns if col not in col_map), df.columns[0]
        )
        player_name = str(row.get(player_name_col, "")).strip()
        if not player_name:
            continue

        player_id = matcher.resolve(player_name)
        if player_id is None:
            # Find closest match for the response
            closest = fuzz_process.extractOne(
                player_name, player_names, scorer=fuzz.token_sort_ratio
            )
            unmatched.append(UnmatchedPlayer(
                row_number=row_idx + 2,  # +2 for 1-indexed + header row
                original_name=player_name,
                closest_match=closest[0] if closest else None,
                match_score=closest[1] if closest else None,
            ))
            continue

        stats = apply_column_map({str(k): str(v) for k, v in row.items()}, col_map)
        if stats:
            upsert_projection_row(db, player_id, source_id, season, stats)
            rows_upserted += 1

    cache.invalidate_rankings(season)

    return UploadResponse(
        source_id=source_id,
        rows_upserted=rows_upserted,
        unmatched=unmatched,
        slots_used=slots_used + 1,
    )
```

- [ ] **Step 2: Run upload tests**

```bash
cd apps/api && pytest tests/routers/test_sources.py::TestUploadSource -v
```

Expected: All tests pass.

- [ ] **Step 3: Run full suite + lint**

```bash
cd apps/api && pytest tests/ -q && ruff check . && ruff format --check .
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/routers/sources.py apps/api/repositories/sources.py \
        apps/api/tests/routers/test_sources.py
git commit -m "feat(sources): add POST /sources/upload with 2-slot limit, CSV/Excel parsing, player matching"
```

---

## Chunk 3: Final Verification + Notion Updates

### Task 8: End-to-end test run and cleanup

- [ ] **Step 1: Run full test suite with coverage**

```bash
cd apps/api && pytest tests/ -q --cov=. --cov-report=term-missing
```

Expected: All tests green.

- [ ] **Step 2: Lint and format check**

```bash
cd apps/api && ruff check . && ruff format --check .
```

- [ ] **Step 3: Update Notion task statuses**

  - Mark "Build custom projection source upload (UI + backend)" (32548885-3275-8164-8bd3-f398f9134a72) → In Progress (backend done, UI still TODO)
  - Mark "Build auth router" (32548885-3275-81ec-9228-ec5116e7cf05) → Done (if Plan 1 complete)
  - Mark "Add user_kits, exports, subscriptions tables" (32048885-3275-81d1-ba69-d68c2924305d) → Done (was already in migration 001)

- [ ] **Step 4: Update apps/api/CLAUDE.md Phase 2 status**

  Add to Phase 2 status table:
  - `POST /sources/upload` ✅ Complete
  - `GET /sources/custom` ✅ Complete
  - `DELETE /sources/{id}` ✅ Complete

- [ ] **Step 5: Final commit**

```bash
git add apps/api/CLAUDE.md
git commit -m "docs(api): mark custom source upload backend as complete"
```
