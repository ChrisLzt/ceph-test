from __future__ import annotations

import os
from pathlib import Path
import unittest

from no_migration_workload.scripts.render import SPECS


ROOT = Path(__file__).resolve().parents[1]


class NoMigrationWrapperTests(unittest.TestCase):
    def test_suite_contains_exactly_five_run_only_workloads(self) -> None:
        directories = {
            path.name
            for path in ROOT.iterdir()
            if path.is_dir() and (path / "run_test.sh").is_file()
        }
        self.assertEqual(directories, set(SPECS))
        for workload in SPECS:
            directory = ROOT / workload
            for script in ("render_config.sh", "run_test.sh", "validate_model.sh"):
                path = directory / script
                self.assertTrue(path.is_file(), path)
                self.assertTrue(os.access(path, os.X_OK), path)
            self.assertFalse((directory / "prepare_data.sh").exists())
            self.assertFalse((directory / "rendered" / "prepare_data.vdb").exists())
            runner = (directory / "run_test.sh").read_text(encoding="utf-8")
            self.assertIn("./render_config.sh", runner)
            self.assertIn("operation=create", runner, "runner must explicitly reject create FWDs")

    def test_top_level_workflow_is_documented_and_validatable(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("/mnt/cephfs", readme)
        self.assertIn("不提供 `prepare_data.sh`", readme)
        self.assertIn("物理 bin 访问分布不迁移", readme)
        validator = ROOT / "validate_all.sh"
        self.assertTrue(validator.is_file())
        self.assertTrue(os.access(validator, os.X_OK))


if __name__ == "__main__":
    unittest.main()
