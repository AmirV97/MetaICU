"""Tests for the external-resource retrieval helper."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "AUMC_pipeline"
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aumc_pipeline.cli.retrieve_externals import ATHENA_REQUIRED_FILES, ATHENA_VOCABULARIES, EXTERNAL_REPOS


class RetrieveExternalsTests(unittest.TestCase):
    def test_print_plan_lists_required_repositories_and_athena_vocabularies(self) -> None:
        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/retrieve_externals.py"),
            "--parent-dir",
            "/tmp/aumc_workspace_fixture",
            "--required-only",
            "--print-plan",
        ]
        result = subprocess.run(cmd, cwd=PIPELINE_ROOT, check=True, capture_output=True, text=True)
        plan = json.loads(result.stdout)
        repo_names = {repo["name"] for repo in plan["repositories"]}
        self.assertIn("AMSTEL", repo_names)
        self.assertIn("AmsterdamUMCdb", repo_names)
        self.assertIn("BlendedICU", repo_names)
        self.assertNotIn("odyssey", repo_names)
        self.assertEqual(plan["raw_data_dir"], "/tmp/aumc_workspace_fixture/AUMC_raw")
        self.assertEqual(plan["external_root"], "/tmp/aumc_workspace_fixture/externals")
        self.assertEqual(plan["omop_vocab_dir"], "/tmp/aumc_workspace_fixture/externals/omop_vocab")
        self.assertEqual(plan["output_dir"], "/tmp/aumc_workspace_fixture/outputs")
        self.assertEqual(plan["athena_vocabularies"], ATHENA_VOCABULARIES)
        self.assertEqual(plan["athena_required_files"], ATHENA_REQUIRED_FILES)

    def test_write_readme_only_documents_repositories_and_athena_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            parent_dir = Path(tmpdir) / "workspace"
            cmd = [
                sys.executable,
                str(PIPELINE_ROOT / "scripts/retrieve_externals.py"),
                "--parent-dir",
                str(parent_dir),
                "--write-readme-only",
            ]
            subprocess.run(cmd, cwd=PIPELINE_ROOT, check=True, capture_output=True, text=True)
            self.assertTrue((parent_dir / "AUMC_raw").exists())
            self.assertTrue((parent_dir / "externals/omop_vocab").exists())
            self.assertTrue((parent_dir / "outputs").exists())
            self.assertTrue((parent_dir / "README.md").exists())
            readme = parent_dir / "externals/README.md"
            self.assertTrue(readme.exists())
            text = readme.read_text()
            for repo in EXTERNAL_REPOS:
                self.assertIn(repo.name, text)
                self.assertIn(repo.url, text)
            for vocab in ATHENA_VOCABULARIES:
                self.assertIn(vocab, text)
            for filename in ATHENA_REQUIRED_FILES:
                self.assertIn(filename, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
