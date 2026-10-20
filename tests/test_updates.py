import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

import daily_arxiv


def result(paper_id, comment=None, summary=""):
    return SimpleNamespace(comment=comment, summary=summary, get_short_id=lambda: paper_id)


def row(code="null", title="Example | title"):
    return f"|**2026-10-20**|**{title}**|Example Team|[2610.00001](https://arxiv.org/abs/2610.00001)|{code}|\n"


class UpdateTests(unittest.TestCase):
    def test_prefers_repository_over_project_and_strips_punctuation(self):
        paper = result("2610.00001", "Project: https://example.org/project. Code: https://github.com/example/robot).")
        self.assertEqual(daily_arxiv.extract_code_link(paper), "https://github.com/example/robot")

    def test_abstract_repository_and_comment_project_fallback(self):
        paper = result("2610.00001", summary="Code: https://github.com/example/robot.")
        self.assertEqual(daily_arxiv.extract_code_link(paper), "https://github.com/example/robot")
        self.assertEqual(daily_arxiv.extract_code_link(result("1", "https://example.org/project.")), "https://example.org/project")
        self.assertIsNone(daily_arxiv.extract_code_link(result("1", "https://arxiv.org/abs/2610.00001")))

    def test_refreshes_missing_links_and_reuses_cache_without_replacing_known_links(self):
        original = {
            "VLA": {"2610.00001": row()},
            "Manipulation": {"2610.00001": row(), "2610.00002": row("**[link](https://github.com/example/keep)**")},
        }
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.json", Path(directory) / "second.json"
            for path in (first, second):
                path.write_text(json.dumps(original))
            with patch.object(daily_arxiv.arxiv_client, "results", return_value=iter([
                result("2610.00001v2", "https://github.com/example/new")
            ])) as fetch:
                cache = {}
                self.assertEqual(daily_arxiv.update_paper_links(first, cache), 2)
                self.assertEqual(daily_arxiv.update_paper_links(second, cache), 2)
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(fetch.call_args.args[0].id_list, ["2610.00001"])
            updated = json.loads(first.read_text())
            self.assertEqual(updated["VLA"]["2610.00001"], row("**[link](https://github.com/example/new)**"))
            self.assertEqual(updated["Manipulation"]["2610.00002"], original["Manipulation"]["2610.00002"])

    def test_absent_links_leave_original_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "papers.json"
            path.write_text(json.dumps({"VLA": {"2610.00001": row()}}, indent=2))
            before = path.read_bytes()
            with patch.object(daily_arxiv.arxiv_client, "results", return_value=iter([result("2610.00001")])):
                self.assertEqual(daily_arxiv.update_paper_links(path), 0)
            self.assertEqual(path.read_bytes(), before)

    def test_network_errors_fail_without_overwriting_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "papers.json"
            path.write_text(json.dumps({"VLA": {"2610.00001": row()}}))
            before = path.read_bytes()
            with patch.object(daily_arxiv.arxiv_client, "results", side_effect=RuntimeError("network failed")):
                with self.assertRaisesRegex(RuntimeError, "network failed"):
                    daily_arxiv.update_paper_links(path)
            self.assertEqual(path.read_bytes(), before)

    def test_both_workflows_have_schedule_manual_trigger_and_shared_write_lock(self):
        root = Path(__file__).resolve().parents[1]
        expected = {"cv-arxiv-daily.yml": "17 0 * * *", "update_paper_links.yml": "47 0 * * 0"}
        groups = []
        for name, cron in expected.items():
            # BaseLoader preserves the YAML 1.2 Actions key 'on' as a string.
            workflow = yaml.load((root / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)
            self.assertIn("workflow_dispatch", workflow["on"])
            self.assertEqual(workflow["on"]["schedule"][0]["cron"], cron)
            self.assertEqual(workflow["permissions"]["contents"], "write")
            self.assertEqual(workflow["concurrency"]["cancel-in-progress"], "false")
            groups.append(workflow["concurrency"]["group"])
            commands = [step.get("run", "") for step in workflow["jobs"]["build"]["steps"]]
            self.assertIn("python -m unittest discover -s tests -v", commands)
        self.assertEqual(groups[0], groups[1])


if __name__ == "__main__":
    unittest.main()
