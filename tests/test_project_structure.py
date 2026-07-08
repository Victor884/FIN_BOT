from pathlib import Path
import unittest


class ProjectStructureTest(unittest.TestCase):
    def test_expected_project_directories_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]

        expected_paths = [
            root / "src" / "finbot" / "api",
            root / "src" / "finbot" / "telegram",
            root / "src" / "finbot" / "parser",
            root / "src" / "finbot" / "validation",
            root / "src" / "finbot" / "db",
            root / "src" / "finbot" / "sheets",
            root / "docs",
        ]

        for path in expected_paths:
            self.assertTrue(path.exists(), f"Missing expected path: {path}")


if __name__ == "__main__":
    unittest.main()
