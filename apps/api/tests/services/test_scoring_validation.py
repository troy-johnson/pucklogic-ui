from __future__ import annotations

import pytest

from services.scoring_validation import validate_scoring_config


class TestValidateScoringConfig:
    def test_valid_config_passes(self) -> None:
        # No conflict: ppp > 0, ppg and ppa are 0 (or absent)
        validate_scoring_config({"g": 3, "a": 2, "ppp": 1})

    def test_ppp_and_ppg_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="PPP.*PPG"):
            validate_scoring_config({"ppp": 1, "ppg": 1})

    def test_ppp_and_ppa_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="PPP.*PPA"):
            validate_scoring_config({"ppp": 1, "ppa": 1})

    def test_shp_and_shg_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="SHP.*SHG"):
            validate_scoring_config({"shp": 1, "shg": 1})

    def test_shp_and_sha_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="SHP.*SHA"):
            validate_scoring_config({"shp": 1, "sha": 1})

    def test_ppg_and_ppa_without_ppp_is_valid(self) -> None:
        validate_scoring_config({"ppg": 2, "ppa": 1})

    def test_ppp_zero_with_ppg_nonzero_is_valid(self) -> None:
        validate_scoring_config({"ppp": 0, "ppg": 2})

    def test_empty_config_is_valid(self) -> None:
        validate_scoring_config({})

    def test_shg_and_sha_without_shp_is_valid(self) -> None:
        validate_scoring_config({"shg": 2, "sha": 1})
