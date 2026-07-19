from decimal import Decimal
import unittest

from workload_common.layout import (
    SKEW_QUANTUM,
    SINGLE_LAYOUT,
    SYSU_LAYOUT,
    make_rank_buckets,
    make_tail_rank_spans,
    rank_bucket_skews,
)
from workload_common.models.common import blend_profiles, combine_profiles, ranked_profile


class LayoutTests(unittest.TestCase):
    def test_tail_rank_spans_keep_twenty_percent_head_and_group_tail_by_four(self) -> None:
        spans = make_tail_rank_spans(100, head_rank_count=20, tail_group_size=4)
        self.assertEqual(len(spans), 40)
        self.assertEqual(spans[:20], tuple((rank,) for rank in range(1, 21)))
        self.assertEqual(spans[20], (21, 22, 23, 24))
        self.assertEqual(spans[-1], (97, 98, 99, 100))

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

    def test_tail_merged_bins_keep_reference_rank_capacity(self) -> None:
        spans = (
            (1,), (2,), (3,), (4,), (5,),
            (6, 7, 8, 9),
            (10, 11, 12, 13),
            (14, 15, 16, 17),
            (18, 19, 20, 21),
            (22, 23, 24, 25),
        )
        buckets = make_rank_buckets(
            layout=SINGLE_LAYOUT,
            prefix="pool",
            anchor="/ceph/pool",
            group="pool",
            total_units=100,
            rank_count=25,
            rank_spans=spans,
        )

        self.assertEqual(len(buckets), 10 * 3)
        by_rank = {}
        for bucket in buckets:
            by_rank.setdefault(bucket.rank, []).append(bucket)
        self.assertEqual([bucket.files for bucket in by_rank[1]], [16, 8, 4])
        self.assertEqual([bucket.files for bucket in by_rank[6]], [64, 32, 16])
        self.assertEqual([bucket.files for bucket in by_rank[10]], [64, 32, 16])
        self.assertEqual(sum(bucket.capacity_mib for bucket in buckets), 100 * 48)

    def test_tail_merged_skew_sums_reference_rank_probabilities(self) -> None:
        spans = (
            (1,), (2,), (3,), (4,), (5,),
            (6, 7, 8, 9),
            (10, 11, 12, 13),
            (14, 15, 16, 17),
            (18, 19, 20, 21),
            (22, 23, 24, 25),
        )
        reference = rank_bucket_skews(
            SINGLE_LAYOUT,
            100,
            25,
            Decimal("100"),
        )
        merged = rank_bucket_skews(
            SINGLE_LAYOUT,
            100,
            25,
            Decimal("100"),
            rank_spans=spans,
        )

        self.assertEqual(len(merged), 10)
        self.assertEqual(sum(Decimal(value) for ranks in merged.values() for value in ranks.values()), Decimal("100"))
        for size in SINGLE_LAYOUT.sizes_mib:
            self.assertAlmostEqual(
                float(Decimal(merged[6][size])),
                float(sum(Decimal(reference[rank][size]) for rank in range(6, 10))),
                places=9,
            )
        shifted = rank_bucket_skews(
            SINGLE_LAYOUT,
            100,
            25,
            Decimal("100"),
            hot_rank=2,
            rank_spans=spans,
        )
        for size in SINGLE_LAYOUT.sizes_mib:
            self.assertEqual(max(shifted, key=lambda rank: Decimal(shifted[rank][size])), 2)

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
