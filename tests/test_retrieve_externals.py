"""Tests for the external-resource retrieval helper."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.tokenized.cli.retrieve_externals import ATHENA_REQUIRED_FILES, ATHENA_VOCABULARIES, EXTERNAL_REPOS, write_external_versions


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
        self.assertEqual(plan["raw_data_dir"], "/tmp/aumc_workspace_fixture/data/raw")
        self.assertEqual(plan["external_root"], "/tmp/aumc_workspace_fixture/externals")
        self.assertEqual(plan["omop_vocab_dir"], "/tmp/aumc_workspace_fixture/externals/omop_vocab")
        self.assertEqual(plan["output_dir"], "/tmp/aumc_workspace_fixture/vocab")
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
            self.assertTrue((parent_dir / "data/raw").exists())
            self.assertTrue((parent_dir / "data/raw_shards").exists())
            self.assertTrue((parent_dir / "externals/omop_vocab").exists())
            self.assertTrue((parent_dir / "vocab").exists())
            self.assertTrue((parent_dir / "data/pre-MEDS").exists())
            self.assertTrue((parent_dir / "data/MEDS").exists())
            self.assertTrue((parent_dir / "data/metadata").exists())
            self.assertTrue((parent_dir / "audits").exists())
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

    def test_external_versions_records_git_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            external_root = Path(tmpdir) / "externals"
            repo_dir = external_root / "AMSTEL"
            repo_dir.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo_dir, check=True)
            (repo_dir / "README.md").write_text("fixture\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo_dir, check=True, capture_output=True, text=True)

            repo = next(repo for repo in EXTERNAL_REPOS if repo.name == "AMSTEL")
            versions = write_external_versions(
                external_root,
                [repo],
                [{"name": "AMSTEL", "path": str(repo_dir), "status": "exists", "url": repo.url}],
            )
            payload = json.loads(versions.read_text())
            record = payload["repositories"][0]
            self.assertEqual(record["name"], "AMSTEL")
            self.assertTrue(record["is_git_repo"])
            self.assertTrue(record["commit"])
            self.assertFalse(record["dirty"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
