# apps/api/tests/scrapers/test_nst.py
"""
TDD tests for scrapers/nst.py.

All HTTP and DB I/O is mocked.
Written BEFORE the implementation (red-green-refactor).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.nst import NstScraper, _iter_seasons

FIXTURE = Path(__file__).parent / "fixtures" / "nst_skaters.html"
FIXTURE_OI = Path(__file__).parent / "fixtures" / "nst_skaters_oi.html"
FIXTURE_5V5 = Path(__file__).parent / "fixtures" / "nst_skaters_5v5.html"
FIXTURE_EV = Path(__file__).parent / "fixtures" / "nst_skaters_ev.html"
FIXTURE_PP = Path(__file__).parent / "fixtures" / "nst_skaters_pp.html"
FIXTURE_SH = Path(__file__).parent / "fixtures" / "nst_skaters_sh.html"


# ---------------------------------------------------------------------------
# _parse_html
# ---------------------------------------------------------------------------


class TestParseHtml:
    def test_returns_list(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_each_row_has_player_name(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        for row in rows:
            assert "player_name" in row
            assert row["player_name"]

    def test_parses_numeric_stats(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        # At least one row should have stat keys beyond player_name
        rows_with_stats = [r for r in rows if len(r) > 1]
        assert len(rows_with_stats) > 0

    def test_parses_cf_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE_OI.read_text(), float_col_map={"CF%": "cf_pct"})
        row = rows[0]
        assert "cf_pct" in row
        assert isinstance(row["cf_pct"], float)
        assert row["cf_pct"] == pytest.approx(58.3)

    def test_parses_xgf_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE_OI.read_text(), float_col_map={"xGF%": "xgf_pct"})
        row = rows[0]
        assert "xgf_pct" in row
        assert isinstance(row["xgf_pct"], float)
        assert row["xgf_pct"] == pytest.approx(59.1)

    def test_parses_sh_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "sh_pct" in row
        assert isinstance(row["sh_pct"], float)
        assert row["sh_pct"] == pytest.approx(14.2)

    def test_parses_pdo(self) -> None:
        rows = NstScraper._parse_html(FIXTURE_OI.read_text(), float_col_map={"PDO": "pdo"})
        row = rows[0]
        assert "pdo" in row
        assert isinstance(row["pdo"], float)
        assert row["pdo"] == pytest.approx(101.5)

    def test_parses_toi(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "toi_per_game" in row
        assert isinstance(row["toi_per_game"], float)
        # TOI / GP = 1640.5 / 82 ≈ 20.0
        assert row["toi_per_game"] == pytest.approx(1640.5 / 82, rel=1e-3)

    def test_parses_gp(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "gp" in row
        assert row["gp"] == 82

    def test_returns_three_rows_for_fixture(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert len(rows) == 3

    def test_empty_table_returns_empty_list(self) -> None:
        html = (
            "<html><body>"
            "<table id='players'>"
            "<thead><tr><th>Player</th></tr></thead>"
            "<tbody></tbody>"
            "</table></body></html>"
        )
        rows = NstScraper._parse_html(html)
        assert rows == []

    def test_missing_table_returns_empty_list(self) -> None:
        rows = NstScraper._parse_html("<html><body><p>no table</p></body></html>")
        assert rows == []


# ---------------------------------------------------------------------------
# _season_id
# ---------------------------------------------------------------------------


class TestSeasonId:
    def test_converts_season_format(self) -> None:
        assert NstScraper._season_id("2024-25") == "20242025"

    def test_handles_2000s(self) -> None:
        assert NstScraper._season_id("2025-26") == "20252026"

    def test_handles_2026_27(self) -> None:
        assert NstScraper._season_id("2026-27") == "20262027"


class TestIterSeasons:
    def test_returns_inclusive_history_range(self) -> None:
        assert _iter_seasons("2005-06", "2007-08") == ["2005-06", "2006-07", "2007-08"]

    def test_raises_when_start_is_after_end(self) -> None:
        with pytest.raises(ValueError, match="start season"):
            _iter_seasons("2007-08", "2005-06")


class TestFetchAllRows:
    def test_fetches_multiple_pages(self) -> None:
        scraper = NstScraper()
        db = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        order_mock = MagicMock()
        range_mock = MagicMock()

        page1 = MagicMock()
        page1.data = [{"id": str(i), "name": f"Player {i}"} for i in range(1000)]
        page2 = MagicMock()
        page2.data = [{"id": "1000", "name": "Player 1000"}]

        db.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.order.return_value = order_mock
        order_mock.range.return_value = range_mock
        range_mock.execute.side_effect = [page1, page2]

        rows = scraper._fetch_all_rows(db, "players", "id,name", order_by="id")

        assert len(rows) == 1001
        assert db.table.call_count == 2
        assert table_mock.select.call_count == 2
        select_mock.order.assert_any_call("id", desc=False)
        order_mock.range.assert_any_call(0, 999)
        order_mock.range.assert_any_call(1000, 1999)

    def test_fetch_players_uses_pagination_helper(self) -> None:
        scraper = NstScraper()
        db = MagicMock()
        expected = [{"id": "player-uuid", "name": "Connor McDavid"}]

        with patch.object(scraper, "_fetch_all_rows", return_value=expected) as fetch_all_rows:
            rows = scraper._fetch_players(db)

        assert rows == expected
        fetch_all_rows.assert_called_once_with(db, "players", "id,name", order_by="id")

    def test_fetch_aliases_uses_pagination_helper(self) -> None:
        scraper = NstScraper()
        db = MagicMock()
        expected = [{"alias_name": "Sid the Kid", "player_id": "p1", "source": "test"}]

        with patch.object(scraper, "_fetch_all_rows", return_value=expected) as fetch_all_rows:
            rows = scraper._fetch_aliases(db)

        assert rows == expected
        fetch_all_rows.assert_called_once_with(
            db,
            "player_aliases",
            "alias_name,player_id,source",
            order_by="alias_name",
        )


class TestUpsertPlayerStats:
    def test_upsert_uses_default_to_null_false(self) -> None:
        scraper = NstScraper()
        db = MagicMock()

        scraper._upsert_player_stats(
            db,
            player_id="player-1",
            season="2009-10",
            stats={"hits_per60": 3.5, "blocks_per60": 1.2},
        )

        db.table.assert_called_once_with("player_stats")
        db.table.return_value.upsert.assert_called_once_with(
            {
                "player_id": "player-1",
                "season": "2009-10",
                "hits_per60": 3.5,
                "blocks_per60": 1.2,
            },
            on_conflict="player_id,season",
            default_to_null=False,
        )


# ---------------------------------------------------------------------------
# scrape()
# ---------------------------------------------------------------------------


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        html = FIXTURE.read_text()
        scraper = NstScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=html)),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_raises_on_robots_disallow(self) -> None:
        from scrapers.base import RobotsDisallowedError

        mock_db = MagicMock()
        scraper = NstScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape("2025-26", mock_db)

    @pytest.mark.asyncio
    async def test_upserts_player_stats_rows(self) -> None:
        mock_db = MagicMock()

        # _fetch_players returns players list; _fetch_aliases returns empty list.
        # Use side_effect on table() so each call to table("players") vs
        # table("player_aliases") can return different data.
        players_mock = MagicMock()
        players_mock.select.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
            {"id": "player-uuid2", "name": "Leon Draisaitl"},
            {"id": "player-uuid3", "name": "Nathan MacKinnon"},
        ]
        players_order_chain = players_mock.select.return_value.order.return_value
        players_order_chain.range.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
            {"id": "player-uuid2", "name": "Leon Draisaitl"},
            {"id": "player-uuid3", "name": "Nathan MacKinnon"},
        ]
        aliases_mock = MagicMock()
        aliases_mock.select.return_value.execute.return_value.data = []
        aliases_order_chain = aliases_mock.select.return_value.order.return_value
        aliases_order_chain.range.return_value.execute.return_value.data = []

        stats_mock = MagicMock()
        stats_mock.upsert.return_value.execute.return_value.data = [{"id": "stat-uuid"}]

        def table_side_effect(name: str) -> MagicMock:
            if name == "players":
                return players_mock
            if name == "player_aliases":
                return aliases_mock
            if name == "player_stats":
                return stats_mock
            return MagicMock()

        mock_db.table.side_effect = table_side_effect

        html = FIXTURE.read_text()
        scraper = NstScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=html)),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        # All three players match by exact name — all should be upserted.
        assert count == 3
        assert stats_mock.upsert.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_html(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        scraper = NstScraper()
        empty_html = "<html><body></body></html>"
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=empty_html)),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        assert count == 0


# ---------------------------------------------------------------------------
# Phase 3 Tier 1 columns — all-situations
# ---------------------------------------------------------------------------


class TestParseHtmlPhase3Columns:
    """_parse_html extracts Phase 3 Tier 1 columns from the all-situations table."""

    def test_parses_icf_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert "icf_per60" in rows[0]
        assert rows[0]["icf_per60"] == pytest.approx(17.8)

    def test_parses_ixg_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert "ixg_per60" in rows[0]
        assert rows[0]["ixg_per60"] == pytest.approx(1.42)

    def test_parses_scf_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE_OI.read_text(), float_col_map={"SCF%": "scf_pct"})
        assert "scf_pct" in rows[0]
        assert rows[0]["scf_pct"] == pytest.approx(61.2)

    def test_parses_scf_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert "scf_per60" in rows[0]
        assert rows[0]["scf_per60"] == pytest.approx(13.5)

    def test_parses_p1_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert "p1_per60" in rows[0]
        assert rows[0]["p1_per60"] == pytest.approx(3.21)

    def test_all_three_rows_have_phase3_cols(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        for row in rows:
            assert "icf_per60" in row
            assert "ixg_per60" in row
            assert "scf_per60" in row
            assert "p1_per60" in row


class TestParseHtmlPhase3ColumnsHitsBlocks:
    def test_parses_hits_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "hits_per60" in row
        assert row["hits_per60"] == pytest.approx(3.42)

    def test_parses_blocks_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "blocks_per60" in row
        assert row["blocks_per60"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# _build_url — sit parameter
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_default_sit_is_all(self) -> None:
        url = NstScraper._build_url("2024-25")
        assert "sit=all" in url

    def test_sit_5v5(self) -> None:
        url = NstScraper._build_url("2024-25", sit="5v5")
        assert "sit=5v5" in url

    def test_sit_ev(self) -> None:
        url = NstScraper._build_url("2024-25", sit="ev")
        assert "sit=ev" in url

    def test_sit_pp(self) -> None:
        url = NstScraper._build_url("2024-25", sit="pp")
        assert "sit=pp" in url

    def test_sit_sh(self) -> None:
        url = NstScraper._build_url("2024-25", sit="sh")
        assert "sit=sh" in url


# ---------------------------------------------------------------------------
# _parse_html — custom float_col_map (for situation pages)
# ---------------------------------------------------------------------------


class TestParseHtmlCustomColMap:
    def test_parses_xgf_pct_5v5_from_5v5_fixture(self) -> None:
        rows = NstScraper._parse_html(
            FIXTURE_5V5.read_text(),
            float_col_map={"xGF%": "xgf_pct_5v5"},
        )
        assert rows[0]["xgf_pct_5v5"] == pytest.approx(62.4)
        assert "xgf_pct" not in rows[0]  # not mapped in this call

    def test_parses_toi_ev_from_ev_fixture(self) -> None:
        rows = NstScraper._parse_html(
            FIXTURE_EV.read_text(),
            float_col_map={},
            toi_col_name="toi_ev",
        )
        # toi_ev = total_toi / gp = 1230.4 / 82
        assert rows[0]["toi_ev"] == pytest.approx(1230.4 / 82, rel=1e-3)
        assert "toi_per_game" not in rows[0]

    def test_parses_toi_pp_from_pp_fixture(self) -> None:
        rows = NstScraper._parse_html(
            FIXTURE_PP.read_text(),
            float_col_map={},
            toi_col_name="toi_pp",
        )
        assert rows[0]["toi_pp"] == pytest.approx(290.5 / 82, rel=1e-3)

    def test_parses_toi_sh_from_sh_fixture(self) -> None:
        rows = NstScraper._parse_html(
            FIXTURE_SH.read_text(),
            float_col_map={},
            toi_col_name="toi_sh",
        )
        assert rows[0]["toi_sh"] == pytest.approx(45.2 / 82, rel=1e-3)


# ---------------------------------------------------------------------------
# _merge_situation_rows
# ---------------------------------------------------------------------------


class TestMergeSituationRows:
    def test_merges_stats_from_two_dicts(self) -> None:
        all_rows = [{"player_name": "A", "cf_pct": 55.0}]
        situation_rows = [{"player_name": "A", "toi_ev": 18.5}]
        merged = NstScraper._merge_situation_rows(all_rows, situation_rows)
        assert len(merged) == 1
        assert merged[0]["cf_pct"] == pytest.approx(55.0)
        assert merged[0]["toi_ev"] == pytest.approx(18.5)

    def test_drops_player_absent_from_primary(self) -> None:
        """Player in situation rows but missing from all-situations is dropped."""
        all_rows = [{"player_name": "A", "cf_pct": 55.0}]
        situation_rows = [
            {"player_name": "A", "toi_ev": 18.5},
            {"player_name": "B", "toi_ev": 12.0},  # not in all_rows
        ]
        merged = NstScraper._merge_situation_rows(all_rows, situation_rows)
        assert len(merged) == 1
        assert merged[0]["player_name"] == "A"

    def test_missing_situation_data_leaves_key_absent(self) -> None:
        """Player with no situation row gets no toi_ev key."""
        all_rows = [
            {"player_name": "A", "cf_pct": 55.0},
            {"player_name": "B", "cf_pct": 50.0},
        ]
        ev_rows = [{"player_name": "A", "toi_ev": 18.5}]
        merged = NstScraper._merge_situation_rows(all_rows, ev_rows)
        assert "toi_ev" in merged[0]
        assert "toi_ev" not in merged[1]

    def test_merges_multiple_situation_dicts(self) -> None:
        all_rows = [{"player_name": "A", "cf_pct": 55.0}]
        ev_rows = [{"player_name": "A", "toi_ev": 18.5}]
        pp_rows = [{"player_name": "A", "toi_pp": 3.2}]
        merged = NstScraper._merge_situation_rows(all_rows, ev_rows, pp_rows)
        assert merged[0]["toi_ev"] == pytest.approx(18.5)
        assert merged[0]["toi_pp"] == pytest.approx(3.2)

    def test_preserves_player_name(self) -> None:
        all_rows = [{"player_name": "Connor McDavid", "cf_pct": 58.3}]
        merged = NstScraper._merge_situation_rows(all_rows)
        assert merged[0]["player_name"] == "Connor McDavid"


# ---------------------------------------------------------------------------
# scrape() — multi-situation
# ---------------------------------------------------------------------------


class TestScrapeMultiSituation:
    def _make_db(self) -> MagicMock:
        mock_db = MagicMock()
        players_mock = MagicMock()
        players_mock.select.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
            {"id": "player-uuid2", "name": "Leon Draisaitl"},
            {"id": "player-uuid3", "name": "Nathan MacKinnon"},
        ]
        players_order_chain = players_mock.select.return_value.order.return_value
        players_order_chain.range.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
            {"id": "player-uuid2", "name": "Leon Draisaitl"},
            {"id": "player-uuid3", "name": "Nathan MacKinnon"},
        ]
        aliases_mock = MagicMock()
        aliases_mock.select.return_value.execute.return_value.data = []
        aliases_order_chain = aliases_mock.select.return_value.order.return_value
        aliases_order_chain.range.return_value.execute.return_value.data = []
        stats_mock = MagicMock()
        stats_mock.upsert.return_value.execute.return_value.data = [{"id": "stat-uuid"}]

        def table_side(name: str) -> MagicMock:
            if name == "players":
                return players_mock
            if name == "player_aliases":
                return aliases_mock
            if name == "player_stats":
                return stats_mock
            return MagicMock()

        mock_db.table.side_effect = table_side
        return mock_db

    @pytest.mark.asyncio
    async def test_scrape_includes_toi_ev_in_upserted_stats(self) -> None:
        """scrape() merges EV TOI into the player_stats upsert payload."""
        mock_db = self._make_db()
        scraper = NstScraper()

        def fake_get(url: str) -> MagicMock:
            if "stdoi=oi" in url:
                return MagicMock(text=FIXTURE_OI.read_text(), status_code=200)
            if "sit=ev" in url:
                return MagicMock(text=FIXTURE_EV.read_text(), status_code=200)
            if "sit=5v5" in url:
                return MagicMock(text=FIXTURE_5V5.read_text(), status_code=200)
            if "sit=pp" in url:
                return MagicMock(text=FIXTURE_PP.read_text(), status_code=200)
            if "sit=sh" in url:
                return MagicMock(text=FIXTURE_SH.read_text(), status_code=200)
            return MagicMock(text=FIXTURE.read_text(), status_code=200)  # sit=all

        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(side_effect=fake_get),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)

        assert count == 3
        stats_mock = mock_db.table("player_stats")
        call_kwargs = stats_mock.upsert.call_args_list[0][0][0]
        assert "toi_ev" in call_kwargs
        assert "toi_pp" in call_kwargs
        assert "toi_sh" in call_kwargs
        assert "xgf_pct_5v5" in call_kwargs
        assert "icf_per60" in call_kwargs

    @pytest.mark.asyncio
    async def test_scrape_makes_six_http_requests(self) -> None:
        """scrape() fetches all, 5v5, ev, pp, sh, and on-ice (stdoi=oi) situations."""
        mock_db = self._make_db()
        scraper = NstScraper()

        def fake_get(url: str) -> MagicMock:
            if "stdoi=oi" in url:
                return MagicMock(text=FIXTURE_OI.read_text(), status_code=200)
            if "sit=ev" in url:
                return MagicMock(text=FIXTURE_EV.read_text(), status_code=200)
            if "sit=5v5" in url:
                return MagicMock(text=FIXTURE_5V5.read_text(), status_code=200)
            if "sit=pp" in url:
                return MagicMock(text=FIXTURE_PP.read_text(), status_code=200)
            if "sit=sh" in url:
                return MagicMock(text=FIXTURE_SH.read_text(), status_code=200)
            return MagicMock(text=FIXTURE.read_text(), status_code=200)

        mock_get = AsyncMock(side_effect=fake_get)
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=mock_get),
        ):
            await scraper.scrape("2025-26", mock_db)

        assert mock_get.call_count == 6


# ---------------------------------------------------------------------------
# Phase 2 — parser robustness for current NST headers
# ---------------------------------------------------------------------------


class TestParseHtmlPhase2CurrentHeaders:
    def test_parses_toi_per_game_from_toi_gp_header_without_total_toi(self) -> None:
        html = """
        <html><body><table id='players'>
          <tr><th>Player</th><th>GP</th><th>TOI/GP</th></tr>
          <tr><td>Connor McDavid</td><td>82</td><td>0.55</td></tr>
        </table></body></html>
        """

        rows = NstScraper._parse_html(html, float_col_map={}, toi_col_name="toi_sh")

        assert rows[0]["toi_sh"] == pytest.approx(0.55)

    def test_parses_hits_and_blocks_per60_from_current_header_names(self) -> None:
        html = """
        <html><body><table id='players'>
          <tr>
            <th>Player</th><th>GP</th><th>TOI</th><th>Hits/60</th><th>Shots Blocked/60</th>
          </tr>
          <tr>
            <td>Connor McDavid</td><td>82</td><td>1640.5</td><td>3.42</td><td>0.85</td>
          </tr>
        </table></body></html>
        """

        rows = NstScraper._parse_html(html)

        assert rows[0]["hits_per60"] == pytest.approx(3.42)
        assert rows[0]["blocks_per60"] == pytest.approx(0.85)


class TestScrapePhase2CurrentHeaders:
    def _make_db(self) -> MagicMock:
        mock_db = MagicMock()
        players_mock = MagicMock()
        players_mock.select.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
        ]
        players_order_chain = players_mock.select.return_value.order.return_value
        players_order_chain.range.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
        ]
        aliases_mock = MagicMock()
        aliases_mock.select.return_value.execute.return_value.data = []
        aliases_order_chain = aliases_mock.select.return_value.order.return_value
        aliases_order_chain.range.return_value.execute.return_value.data = []
        stats_mock = MagicMock()
        stats_mock.upsert.return_value.execute.return_value.data = [{"id": "stat-uuid"}]

        def table_side(name: str) -> MagicMock:
            if name == "players":
                return players_mock
            if name == "player_aliases":
                return aliases_mock
            if name == "player_stats":
                return stats_mock
            return MagicMock()

        mock_db.table.side_effect = table_side
        return mock_db

    @pytest.mark.asyncio
    async def test_scrape_uses_current_header_variants_for_toi_sh_and_per60(self) -> None:
        mock_db = self._make_db()
        scraper = NstScraper()

        all_html = """
        <html><body><table id='players'>
          <tr>
            <th>Player</th><th>GP</th><th>TOI</th><th>Hits/60</th><th>Shots Blocked/60</th>
          </tr>
          <tr>
            <td>Connor McDavid</td><td>82</td><td>1640.5</td><td>3.42</td><td>0.85</td>
          </tr>
        </table></body></html>
        """
        sh_html = """
        <html><body><table id='players'>
          <tr><th>Player</th><th>GP</th><th>TOI/GP</th></tr>
          <tr><td>Connor McDavid</td><td>82</td><td>0.55</td></tr>
        </table></body></html>
        """
        empty_sit_html = """
        <html><body><table id='players'>
          <tr><th>Player</th></tr>
        </table></body></html>
        """
        oi_html = """
        <html><body><table id='players'>
          <tr><th>Player</th><th>CF%</th></tr>
          <tr><td>Connor McDavid</td><td>58.3</td></tr>
        </table></body></html>
        """

        def fake_get(url: str) -> MagicMock:
            if "stdoi=oi" in url:
                return MagicMock(text=oi_html, status_code=200)
            if "sit=sh" in url:
                return MagicMock(text=sh_html, status_code=200)
            if "sit=5v5" in url or "sit=ev" in url or "sit=pp" in url:
                return MagicMock(text=empty_sit_html, status_code=200)
            return MagicMock(text=all_html, status_code=200)

        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(side_effect=fake_get)),
        ):
            count = await scraper.scrape("2025-26", mock_db)

        assert count == 1
        stats_mock = mock_db.table("player_stats")
        payload = stats_mock.upsert.call_args_list[0][0][0]
        assert payload["hits_per60"] == pytest.approx(3.42)
        assert payload["blocks_per60"] == pytest.approx(0.85)
        assert payload["toi_sh"] == pytest.approx(0.55)
        assert payload["toi_sh"] != pytest.approx(1640.5 / 82, rel=1e-3)
