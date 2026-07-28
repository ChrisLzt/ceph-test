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
        testcase.assertEqual(len(selected), 200, rd_name)
        testcase.assertEqual(skew_sum(run_text, actual_rds[rd_name]), Decimal("100"))
        for fwd_name in selected:
            line = definitions[fwd_name]
            testcase.assertIn(f"operation={operation}", line)
            testcase.assertIn("fileselect=random", line)
            testcase.assertIn("xfersize=4m", line)
            testcase.assertIn("threads=1", line)
