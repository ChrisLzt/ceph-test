import unittest

from INSPUR_workload.common.layout import INSPUR_LAYOUT


class InspurLayoutTests(unittest.TestCase):
    def test_layout_is_four_times_sysu_capacity_with_same_file_counts(self) -> None:
        self.assertEqual(INSPUR_LAYOUT.sizes_mib, (16, 32, 64, 128, 256))
        self.assertEqual(
            INSPUR_LAYOUT.files_for_units(1),
            {16: 16, 32: 8, 64: 4, 128: 2, 256: 1},
        )
        self.assertEqual(INSPUR_LAYOUT.unit_mib, 1280)
        self.assertEqual(INSPUR_LAYOUT.capacity_mib(2400), 3000 * 1024)
        self.assertEqual(sum(INSPUR_LAYOUT.files_for_units(2400).values()), 74400)


if __name__ == "__main__":
    unittest.main()
