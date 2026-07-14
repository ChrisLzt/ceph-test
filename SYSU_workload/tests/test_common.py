import unittest

from SYSU_workload.common.layout import (
    aggregate_zipf_percentages,
    bucket_counts,
    split_skew,
)


class MixedLayoutTests(unittest.TestCase):
    def test_one_unit_has_equal_capacity_per_size(self) -> None:
        self.assertEqual(bucket_counts(1), {4: 16, 8: 8, 16: 4, 32: 2, 64: 1})

    def test_750_gib_layout(self) -> None:
        counts = bucket_counts(2400)
        self.assertEqual(sum(size * files for size, files in counts.items()), 750 * 1024)
        self.assertEqual(sum(counts.values()), 74400)

    def test_scaled_zipf_profiles(self) -> None:
        self.assertEqual(
            aggregate_zipf_percentages(64000, 20, 0.99),
            [73, 6, 3, 2] + [1] * 16,
        )
        self.assertEqual(
            aggregate_zipf_percentages(166400, 20, 0.99),
            [74, 5, 3, 2] + [1] * 16,
        )

    def test_fractional_bucket_skew(self) -> None:
        self.assertEqual(split_skew(13), ["2.6"] * 5)
        self.assertEqual(split_skew(1), ["0.2"] * 5)

    def test_rejects_invalid_layout_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "units must be positive"):
            bucket_counts(0)
        with self.assertRaisesRegex(ValueError, "divisible"):
            aggregate_zipf_percentages(101, 20, 0.99)


if __name__ == "__main__":
    unittest.main()
