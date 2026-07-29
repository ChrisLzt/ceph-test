from pathlib import Path
import unittest

from workload_common.validate_vdbench import (
    ConfigValidationError,
    validate_prepare_text,
    validate_run_text,
)


ROOT = Path(__file__).resolve().parents[2]


class VdbenchValidationTests(unittest.TestCase):
    def test_accepts_run_rd_with_matching_prefix_wildcard(self) -> None:
        text = "\n".join(
            [
                "fwd=phase_data_01,fsd=fsd_01,operation=read,skew=60",
                "fwd=phase_data_02,fsd=fsd_02,operation=read,skew=40",
                "rd=phase,fwd=phase*,fwdrate=max,elapsed=600,interval=1",
            ]
        )
        validate_run_text(text)

    def test_accepts_two_rds_reusing_one_fwd_set(self) -> None:
        text = "\n".join(
            [
                "fwd=checkpoint_data_01,fsd=fsd_01,operation=read,skew=60",
                "fwd=checkpoint_data_02,fsd=fsd_02,operation=read,skew=40",
                "rd=checkpoint_read,fwd=checkpoint*,fwdrate=max,elapsed=300,interval=1",
                "rd=checkpoint_reheat,fwd=checkpoint*,fwdrate=max,elapsed=300,interval=1",
            ]
        )
        validate_run_text(text)

    def test_rejects_explicit_run_fwd_list_even_when_short(self) -> None:
        text = "\n".join(
            [
                "fwd=phase_data_01,fsd=fsd_01,operation=read,skew=100",
                "rd=phase,fwd=(phase_data_01),fwdrate=max,elapsed=600,interval=1",
            ]
        )
        with self.assertRaisesRegex(ConfigValidationError, "prefix wildcard"):
            validate_run_text(text)

    def test_rejects_run_whose_total_elapsed_is_not_600_seconds(self) -> None:
        text = "\n".join(
            [
                "fwd=phase_data_01,fsd=fsd_01,operation=read,skew=100",
                "rd=phase,fwd=phase*,fwdrate=max,elapsed=599,interval=1",
            ]
        )
        with self.assertRaisesRegex(ConfigValidationError, "600"):
            validate_run_text(text)

    def test_rejects_wildcard_prefix_collision_between_rd_names(self) -> None:
        text = "\n".join(
            [
                "fwd=phase_data,fsd=fsd_01,operation=read,skew=100",
                "fwd=phase2_data,fsd=fsd_02,operation=read,skew=100",
                "rd=phase,fwd=phase*,fwdrate=max,elapsed=300,interval=1",
                "rd=phase2,fwd=phase2*,fwdrate=max,elapsed=300,interval=1",
            ]
        )
        with self.assertRaisesRegex(ConfigValidationError, "prefix|skew|more than one"):
            validate_run_text(text)

    def test_rejects_prepare_rd_with_more_than_512_explicit_fwds(self) -> None:
        names = [f"prep_data_{index:03d}" for index in range(513)]
        text = "\n".join(
            [*(f"fwd={name},fsd=fsd_{name}" for name in names),
             f"rd=prepare,fwd=({','.join(names)}),format=(clean,only),fwdrate=max"]
        )
        with self.assertRaisesRegex(ConfigValidationError, "512"):
            validate_prepare_text(text)

    def test_rejects_run_wildcard_matching_more_than_512_fwds(self) -> None:
        names = [f"phase_data_{index:03d}" for index in range(513)]
        text = "\n".join(
            [
                *(f"fwd={name},fsd=fsd_{name},operation=read,skew=0" for name in names),
                "rd=phase,fwd=phase*,fwdrate=max,elapsed=600,interval=1",
            ]
        )
        with self.assertRaisesRegex(ConfigValidationError, "512"):
            validate_run_text(text)

    def test_both_suites_expose_real_vdbench_validation_entrypoint(self) -> None:
        for suite in ("SINGLE_workload", "SYSU_workload"):
            script = ROOT / suite / "validate_all.sh"
            self.assertTrue(script.is_file(), suite)
            text = script.read_text(encoding="utf-8")
            self.assertIn("workload_common.validate_vdbench", text, suite)
            self.assertIn("vdbench", text, suite)


if __name__ == "__main__":
    unittest.main()
