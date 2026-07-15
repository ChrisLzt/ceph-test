import unittest
from decimal import Decimal

from workload_common.layout import SYSU_LAYOUT, rank_bucket_skews


class SysuLayoutTests(unittest.TestCase):
    def test_750_gib_mixed_size_layout(self) -> None:
        self.assertEqual(SYSU_LAYOUT.sizes_mib, (4, 8, 16, 32, 64))
        self.assertEqual(SYSU_LAYOUT.files_for_units(1), {4: 16, 8: 8, 16: 4, 32: 2, 64: 1})
        self.assertEqual(SYSU_LAYOUT.capacity_mib(2400), 750 * 1024)

    def test_decimal_zipf_is_not_integer_floor_normalized(self) -> None:
        skews = rank_bucket_skews(SYSU_LAYOUT, 800, 80, 100)
        values = [Decimal(value) for rank in skews.values() for value in rank.values()]
        self.assertEqual(sum(values), Decimal("100"))
        self.assertTrue(any(value < 1 for value in values))
        self.assertTrue(all(value > 0 for value in values))


if __name__ == "__main__":
    unittest.main()
