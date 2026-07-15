from decimal import Decimal
import unittest

from workload_common.layout import (
    SKEW_QUANTUM,
    SINGLE_LAYOUT,
    SYSU_LAYOUT,
    make_rank_buckets,
    rank_bucket_skews,
)
from workload_common.models.common import blend_profiles, combine_profiles, ranked_profile


class LayoutTests(unittest.TestCase):
    def test_ranked_profiles_crossfade_at_exact_quarter_steps(self) -> None:
        buckets = make_rank_buckets(
            layout=SINGLE_LAYOUT,
            prefix="test",
            anchor="/ceph/test",
            group="test",
            total_units=96,
            rank_count=24,
        )
        ranks = {}
        for bucket in buckets:
            ranks.setdefault(bucket.rank, []).append(bucket)
        old = ranked_profile(SINGLE_LAYOUT, ranks, 96, 24, 100, hot_rank=1)
        new = ranked_profile(SINGLE_LAYOUT, ranks, 96, 24, 100, hot_rank=2)

        for new_share in (Decimal("0.25"), Decimal("0.50"), Decimal("0.75")):
            with self.subTest(new_share=new_share):
                blended = blend_profiles(old, new, new_share)
                self.assertEqual(sum(blended.values()), Decimal("100"))
                first = buckets[0]
                expected = (
                    old[first] * (Decimal("1") - new_share)
                    + new[first] * new_share
                ).quantize(SKEW_QUANTUM)
                self.assertEqual(blended[first], expected)
                self.assertTrue(all(value > 0 for value in blended.values()))

        left = ranked_profile(SINGLE_LAYOUT, ranks, 96, 24, 75, hot_rank=1)
        right = ranked_profile(SINGLE_LAYOUT, ranks, 96, 24, 25, hot_rank=2)
        combined = combine_profiles(left, right)
        self.assertEqual(sum(combined.values()), Decimal("100"))

    def test_physical_layouts_share_2400_logical_units(self) -> None:
        self.assertEqual(SINGLE_LAYOUT.sizes_mib, (4, 8, 16))
        self.assertEqual(SINGLE_LAYOUT.files_per_unit, (4, 2, 1))
        self.assertEqual(SINGLE_LAYOUT.capacity_mib(2400), 112 * 1024 + 512)
        self.assertEqual(SYSU_LAYOUT.sizes_mib, (4, 8, 16, 32, 64))
        self.assertEqual(SYSU_LAYOUT.files_per_unit, (16, 8, 4, 2, 1))
        self.assertEqual(SYSU_LAYOUT.capacity_mib(2400), 750 * 1024)

    def test_rank_buckets_have_equal_capacity_per_size(self) -> None:
        buckets = make_rank_buckets(
            layout=SINGLE_LAYOUT,
            prefix="dataset",
            anchor="/mnt/cephfs/test/dataset",
            group="dataset",
            total_units=800,
            rank_count=40,
        )
        self.assertEqual(len(buckets), 40 * 3)
        first = buckets[:3]
        self.assertEqual([bucket.files for bucket in first], [80, 40, 20])
        self.assertEqual([bucket.capacity_mib for bucket in first], [320, 320, 320])
        self.assertEqual({bucket.rank_key for bucket in first}, {"dataset:001"})

    def test_zipf_skews_are_positive_decimal_and_exact(self) -> None:
        skews = rank_bucket_skews(
            layout=SINGLE_LAYOUT,
            group_units=800,
            rank_count=40,
            group_weight=Decimal("100"),
        )
        values = [Decimal(value) for rank in skews.values() for value in rank.values()]
        self.assertTrue(all(value > 0 for value in values))
        self.assertEqual(sum(values), Decimal("100"))
        self.assertTrue(any(value != value.to_integral() for value in values))
        for size in SINGLE_LAYOUT.sizes_mib:
            self.assertAlmostEqual(
                float(sum(Decimal(skews[rank][size]) for rank in skews)),
                100 / 3,
                places=8,
            )

    def test_hot_rank_rotates_zipf_head_without_changing_total(self) -> None:
        base = rank_bucket_skews(SYSU_LAYOUT, 800, 40, Decimal("100"), hot_rank=1)
        shifted = rank_bucket_skews(SYSU_LAYOUT, 800, 40, Decimal("100"), hot_rank=2)
        for size in SYSU_LAYOUT.sizes_mib:
            self.assertEqual(max(base, key=lambda rank: Decimal(base[rank][size])), 1)
            self.assertEqual(max(shifted, key=lambda rank: Decimal(shifted[rank][size])), 2)
        self.assertEqual(
            sum(Decimal(value) for rank in shifted.values() for value in rank.values()),
            Decimal("100"),
        )

    def test_rejects_non_divisible_rank_layout(self) -> None:
        with self.assertRaisesRegex(ValueError, "divisible"):
            make_rank_buckets(
                layout=SINGLE_LAYOUT,
                prefix="bad",
                anchor="/tmp/bad",
                group="bad",
                total_units=10,
                rank_count=3,
            )


if __name__ == "__main__":
    unittest.main()
