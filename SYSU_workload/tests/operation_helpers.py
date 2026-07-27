from __future__ import annotations

import re
from decimal import Decimal

from workload_common.tests.helpers import (
    fwd_definitions,
    rd_definitions,
    rd_fwd_names,
    skew_sum,
)


def assert_rd_operations(testcase, run_text: str, expected: dict[str, str]) -> None:
    definitions = fwd_definitions(run_text)
    actual_rds = {
        re.match(r"rd=([^,]+)", line).group(1): line
        for line in rd_definitions(run_text)
    }
    testcase.assertEqual(set(actual_rds), set(expected))
    for rd_name, operation in expected.items():
        selected = rd_fwd_names(actual_rds[rd_name], definitions)
        testcase.assertTrue(selected, rd_name)
        for fwd_name in selected:
            testcase.assertIn(
                f"operation={operation}",
                definitions[fwd_name],
                f"{rd_name} selected an unexpected FWD: {definitions[fwd_name]}",
            )


def assert_sysu_run_contract(
    testcase,
    run_text: str,
    *,
    expected_fwd_count: int,
) -> None:
    definitions = fwd_definitions(run_text)
    for line in definitions.values():
        testcase.assertRegex(line, r"operation=(read|write)")
        testcase.assertIn("fileselect=random", line)
        testcase.assertIn("xfersize=4m", line)
        testcase.assertIn("threads=1", line)
    testcase.assertNotIn("format=", run_text)
    for rd in rd_definitions(run_text):
        testcase.assertIn("fwdrate=max", rd)
        matched_count = len(rd_fwd_names(rd, definitions))
        testcase.assertLessEqual(matched_count, 512)
        testcase.assertEqual(matched_count, expected_fwd_count)
        testcase.assertEqual(skew_sum(run_text, rd), Decimal("100"))
