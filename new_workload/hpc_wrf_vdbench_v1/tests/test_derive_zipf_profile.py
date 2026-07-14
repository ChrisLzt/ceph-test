#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_zipf_profile import (  # noqa: E402
    PHASES,
    aggregate_zipf_percentages,
    build_prepare_template,
    build_run_template,
)


class ZipfProfileTests(unittest.TestCase):
    def test_default_profile_is_nonzero_and_sums_to_100(self) -> None:
        self.assertEqual(
            aggregate_zipf_percentages(9600, 20, 0.99),
            [68, 7, 4, 3, 2, 2] + [1] * 14,
        )

    def test_profile_rejects_nondivisible_object_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "divisible"):
            aggregate_zipf_percentages(9601, 20, 0.99)

    def test_prepare_template_contains_all_sixty_rank_pools(self) -> None:
        text = build_prepare_template(rank_count=20)
        self.assertEqual(text.count("\nfsd=fsd_"), 60)
        self.assertEqual(text.count("\nfwd=prep_"), 60)
        self.assertIn("format=(clean,only)", text)
        self.assertIn("format=(restart,only)", text)

    def test_run_template_has_four_phases_with_zipf_weights(self) -> None:
        weights = aggregate_zipf_percentages(9600, 20, 0.99)
        text = build_run_template(rank_count=20, weights=weights)

        self.assertEqual(text.count("\nfsd=fsd_"), 60)
        self.assertEqual(text.count("\nfwd="), 80)
        self.assertEqual(text.count("\nrd="), 4)
        self.assertNotIn("operation=write", text)
        self.assertNotIn("format=", text)

        for phase, group in PHASES:
            self.assertIn(
                f"fwd={phase}_r01,fsd=fsd_{group}_r01,operation=read,"
                "fileio=sequential,fileselect=random,xfersize=@XFER_SIZE@,"
                "threads=@THREADS@,skew=68",
                text,
            )

    def test_checkpoint_reheat_uses_same_group_and_weight_order(self) -> None:
        weights = aggregate_zipf_percentages(9600, 20, 0.99)
        text = build_run_template(rank_count=20, weights=weights)

        for rank, weight in enumerate(weights, 1):
            first = (
                f"fwd=checkpoint_read_r{rank:02d},"
                f"fsd=fsd_checkpoint_r{rank:02d},"
            )
            reheat = (
                f"fwd=checkpoint_reheat_r{rank:02d},"
                f"fsd=fsd_checkpoint_r{rank:02d},"
            )
            self.assertIn(first, text)
            self.assertIn(reheat, text)
            self.assertIn(f"{first}operation=read", text)
            self.assertIn(f"{reheat}operation=read", text)
            self.assertIn(f"skew={weight}", text)


if __name__ == "__main__":
    unittest.main()
