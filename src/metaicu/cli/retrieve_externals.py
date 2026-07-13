"""Retrieve GitHub-hosted external resources and set up an AUMC workspace.

The OMOP/Athena vocabulary export is intentionally not downloaded here because
Athena requires a user account and vocabulary/license selections. This command
creates the expected folder layout and writes the Athena checklist instead.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ATHENA_VOCABULARIES = [
    "SNOMED",
    "LOINC",
    "RxNorm",
    "RxNorm Extension",
    "ATC",
    "UCUM",
    "OMOP Extension",
]

ATHENA_REQUIRED_FILES = [
    "CONCEPT.csv",
    "CONCEPT_RELATIONSHIP.csv",
    "CONCEPT_ANCESTOR.csv",
    "VOCABULARY.csv",
    "DOMAIN.csv",
    "RELATIONSHIP.csv",
    "CONCEPT_CLASS.csv",
    "CONCEPT_SYNONYM.csv",
    "DRUG_STRENGTH.csv",
]


@dataclass(frozen=True)
class ExternalRepo:
    """GitHub repository expected under the user-provided external root."""

    name: str
    url: str
    required: bool
    purpose: str


EXTERNAL_REPOS = [
    ExternalRepo("AMSTEL", "https://github.com/AmsterdamUMC/AMSTEL.git", True, "AmsterdamUMCdb-to-OMOP mappings, source concepts, USAGI evidence."),
    ExternalRepo("AmsterdamUMCdb", "https://github.com/AmsterdamUMC/AmsterdamUMCdb.git", True, "Official AmsterdamUMCdb dictionaries and flowsheet SQL groupings."),
    ExternalRepo("BlendedICU", "https://github.com/USM-CHU-FGuyon/BlendedICU.git", True, "Curated ICU variable and medication context resources."),
    ExternalRepo("YAIB-cohorts", "https://github.com/rvandewater/YAIB-cohorts.git", False, "Auxiliary ricu/YAIB cohort configuration evidence."),
    ExternalRepo("ricu", "https://github.com/eth-mds/ricu.git", False, "Auxiliary ICU concept/configuration context."),
    ExternalRepo("YAIB", "https://github.com/rvandewater/YAIB.git", False, "Auxiliary ICU benchmark/configuration context."),
    ExternalRepo("AUMCdb_MEDS", "https://github.com/prockenschaub/AUMCdb_MEDS.git", False, "Auxiliary AmsterdamUMCdb MEDS conversion reference."),
    ExternalRepo("odyssey", "https://github.com/VectorInstitute/odyssey.git", False, "Auxiliary tokenization/modeling reference code."),
    ExternalRepo("ReciPys", "https://github.com/rvandewater/ReciPys.git", False, "Auxiliary ICU preprocessing/reference code."),
    ExternalRepo("ricu-versions", "https://github.com/prockenschaub/ricu-versions.git", False, "Auxiliary ricu version/configuration reference."),
]


def selected_repos(required_only: bool) -> list[ExternalRepo]:
    """Return repositories requested by the command-line policy."""

    if required_only:
        return [repo for repo in EXTERNAL_REPOS if repo.required]
    return list(EXTERNAL_REPOS)


def workspace_paths(parent_dir: Path | None, external_root: Path | None) -> dict[str, Path]:
    """Resolve the public workspace layout."""

    if parent_dir is not None:
        return {
            "parent_dir": parent_dir,
            "raw_data_dir": parent_dir / "data/raw",
            "external_root": parent_dir / "externals",
            "omop_vocab_dir": parent_dir / "externals/omop_vocab",
            "output_dir": parent_dir / "vocab",
        }
    if external_root is None:
        external_root = Path("amsterdam_external")
    return {
        "parent_dir": external_root.parent,
        "raw_data_dir": external_root.parent / "data/raw",
        "external_root": external_root,
        "omop_vocab_dir": external_root / "omop_vocab",
        "output_dir": external_root.parent / "vocab",
    }


def create_workspace_dirs(paths: dict[str, Path]) -> None:
    """Create empty user-facing directories that are not cloned from GitHub."""

    paths["raw_data_dir"].mkdir(parents=True, exist_ok=True)
    paths["external_root"].mkdir(parents=True, exist_ok=True)
    paths["omop_vocab_dir"].mkdir(parents=True, exist_ok=True)
    paths["output_dir"].mkdir(parents=True, exist_ok=True)
    (paths["parent_dir"] / "data/raw_shards").mkdir(parents=True, exist_ok=True)
    (paths["parent_dir"] / "data/pre-MEDS").mkdir(parents=True, exist_ok=True)
    (paths["parent_dir"] / "data/MEDS").mkdir(parents=True, exist_ok=True)
    (paths["parent_dir"] / "data/metadata").mkdir(parents=True, exist_ok=True)
    (paths["parent_dir"] / "audits").mkdir(parents=True, exist_ok=True)


def run_git(args: list[str], cwd: Path | None = None) -> None:
    """Run a git command and fail immediately if git reports an error."""

    subprocess.run(["git", *args], cwd=cwd, check=True)


def git_output(args: list[str], cwd: Path) -> str:
    """Return stdout for a git command, or an empty string if it fails."""

    try:
        result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    except Exception:
        return ""
    return result.stdout.strip()


def write_external_versions(external_root: Path, repos: list[ExternalRepo], results: list[dict[str, str]]) -> Path:
    """Write clone/update status plus git branch and commit for retrieved resources."""

    by_name = {record["name"]: record for record in results}
    records = []
    for repo in repos:
        destination = external_root / repo.name
        clone_record = by_name.get(repo.name, {})
        is_git = (destination / ".git").exists()
        records.append(
            {
                "name": repo.name,
                "url": repo.url,
                "required": repo.required,
                "purpose": repo.purpose,
                "path": str(destination),
                "clone_status": clone_record.get("status", "not_requested"),
                "is_git_repo": is_git,
                "branch": git_output(["rev-parse", "--abbrev-ref", "HEAD"], destination) if is_git else "",
                "commit": git_output(["rev-parse", "HEAD"], destination) if is_git else "",
                "dirty": bool(git_output(["status", "--short"], destination)) if is_git else False,
            }
        )
    path = external_root / "external_versions.json"
    path.write_text(json.dumps({"repositories": records}, indent=2, sort_keys=True) + "\n")
    return path


def clone_or_update(repo: ExternalRepo, external_root: Path, update: bool, depth: int | None) -> dict[str, str]:
    """Clone a missing repository, or optionally update an existing clone."""

    destination = external_root / repo.name
    if destination.exists() and not (destination / ".git").exists():
        return {"name": repo.name, "path": str(destination), "status": "exists_non_git", "url": repo.url}
    if (destination / ".git").exists():
        if update:
            run_git(["pull", "--ff-only"], cwd=destination)
            status = "updated"
        else:
            status = "exists"
        return {"name": repo.name, "path": str(destination), "status": status, "url": repo.url}

    external_root.mkdir(parents=True, exist_ok=True)
    clone_args = ["clone"]
    if depth is not None and depth > 0:
        clone_args.extend(["--depth", str(depth)])
    clone_args.extend([repo.url, str(destination)])
    run_git(clone_args)
    return {"name": repo.name, "path": str(destination), "status": "cloned", "url": repo.url}


def athena_instructions() -> str:
    """Return user-facing Athena vocabulary download instructions."""

    vocab_lines = "\n".join(f"- {name}" for name in ATHENA_VOCABULARIES)
    file_lines = "\n".join(f"- {name}" for name in ATHENA_REQUIRED_FILES)
    return f"""# OMOP / Athena Vocabulary Export\n\nThe Amsterdam vocabulary workflow needs a local Athena vocabulary export. Athena downloads require a logged-in OHDSI Athena account and cannot be retrieved automatically by this script.\n\nOpen: https://athena.ohdsi.org/vocabulary/list\n\nSelect these vocabularies:\n\n{vocab_lines}\n\nNotes:\n\n- CPT4 is not required for the current Amsterdam ICU trajectory vocabulary and may require additional UMLS licensing.\n- If your local policies require CPT4 or other licensed vocabularies later, add them separately and record the license status.\n- After Athena prepares the download, extract the ZIP/TAR contents into `externals/omop_vocab/` under your parent workspace.\n\nThe extracted directory must contain at least:\n\n{file_lines}\n"""


def write_parent_readme(paths: dict[str, Path]) -> Path:
    """Write a README at parent-dir level explaining the expected layout."""

    parent = paths["parent_dir"]
    parent.mkdir(parents=True, exist_ok=True)
    text = f"""# MetaICU Workspace

This folder is structured for the MetaICU workflow.

Expected layout:

```text
{parent}/
├── data/
│   ├── raw/
│   ├── raw_shards/
│   ├── pre-MEDS/
│   ├── MEDS/
│   └── metadata/
├── externals/
│   └── omop_vocab/
├── vocab/
└── audits/
```

## What to place here

- Put the raw AmsterdamUMCdb CSV files in `data/raw/`. Required examples include `numericitems.csv`, `listitems.csv`, `drugitems.csv`, `freetextitems.csv`, `processitems.csv`, and `procedureorderitems.csv`.
- GitHub-hosted external repositories are cloned into `externals/` by `retrieve_externals.py`.
- Download the Athena/OMOP export manually and extract its CSV files into `externals/omop_vocab/`.

## Build command

```bash
python /path/to/MetaICU/scripts/build_amsterdam_vocab.py \
  step=build_vocab \
  paths.parent_dir={parent}
```

The vocabulary output will be:

```text
{paths['output_dir']}/aumc_supplied_vocab.csv
```
"""
    readme = parent / "README.md"
    readme.write_text(text)
    return readme


def write_external_readme(external_root: Path, repos: list[ExternalRepo]) -> Path:
    """Write a README into the external root documenting retrieved resources."""

    external_root.mkdir(parents=True, exist_ok=True)
    repo_lines = "\n".join(
        f"| {repo.name} | {repo.url} | {'required' if repo.required else 'optional'} | {repo.purpose} |"
        for repo in repos
    )
    text = f"""# Amsterdam External Resources\n\nThis folder is intended to live at `{{parent_dir}}/externals` and is used by MetaICU as `paths.external_root`.\n\n## GitHub Resources\n\n| Folder | Repository | Status | Purpose |\n|---|---|---|---|\n{repo_lines}\n\n## Athena / OMOP Vocabulary\n\nDownload the Athena vocabulary export manually and extract it into `omop_vocab/` inside this folder. In the parent-dir workflow this is `{{parent_dir}}/externals/omop_vocab`.\n\n{athena_instructions()}\n"""
    readme = external_root / "README.md"
    readme.write_text(text)
    return readme


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve GitHub-hosted external resources for MetaICU.")
    parser.add_argument("--parent-dir", type=Path, help="Workspace root. Creates data/raw/, externals/, externals/omop_vocab/, vocab/, data/pre-MEDS/, data/MEDS/, data/metadata/, and audits/.")
    parser.add_argument("--external-root", default=None, type=Path, help="Advanced: directory where GitHub resources will be cloned. Prefer --parent-dir.")
    parser.add_argument("--required-only", action="store_true", help="Clone only resources required for the current vocabulary workflow.")
    parser.add_argument("--update", action="store_true", help="Run git pull --ff-only in repositories that already exist.")
    parser.add_argument("--depth", default=1, type=int, help="git clone depth. Use 0 for full history.")
    parser.add_argument("--print-plan", action="store_true", help="Print the repositories and Athena checklist without cloning.")
    parser.add_argument("--write-readme-only", action="store_true", help="Only create workspace folders and README files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repos = selected_repos(required_only=args.required_only)
    depth = None if args.depth == 0 else args.depth
    paths = workspace_paths(args.parent_dir, args.external_root)

    if args.print_plan:
        print(
            json.dumps(
                {
                    "parent_dir": str(paths["parent_dir"]),
                    "raw_data_dir": str(paths["raw_data_dir"]),
                    "external_root": str(paths["external_root"]),
                    "omop_vocab_dir": str(paths["omop_vocab_dir"]),
                    "output_dir": str(paths["output_dir"]),
                    "repositories": [asdict(repo) for repo in repos],
                    "athena_vocabularies": ATHENA_VOCABULARIES,
                    "athena_required_files": ATHENA_REQUIRED_FILES,
                },
                indent=2,
            )
        )
        return

    create_workspace_dirs(paths)

    if args.write_readme_only:
        parent_readme = write_parent_readme(paths)
        external_readme = write_external_readme(paths["external_root"], repos)
        print(json.dumps({"parent_readme": str(parent_readme), "external_readme": str(external_readme), "raw_data_dir": str(paths["raw_data_dir"]), "omop_vocab_dir": str(paths["omop_vocab_dir"]), "output_dir": str(paths["output_dir"])}, indent=2))
        return

    results = [clone_or_update(repo, paths["external_root"], update=args.update, depth=depth) for repo in repos]
    parent_readme = write_parent_readme(paths)
    external_readme = write_external_readme(paths["external_root"], repos)
    external_versions = write_external_versions(paths["external_root"], repos, results)
    print(
        json.dumps(
            {
                "parent_dir": str(paths["parent_dir"]),
                "raw_data_dir": str(paths["raw_data_dir"]),
                "external_root": str(paths["external_root"]),
                "omop_vocab_dir": str(paths["omop_vocab_dir"]),
                "output_dir": str(paths["output_dir"]),
                "repositories": results,
                "parent_readme": str(parent_readme),
                "external_readme": str(external_readme),
                "external_versions": str(external_versions),
                "athena_vocabularies_to_select": ATHENA_VOCABULARIES,
                "athena_required_files": ATHENA_REQUIRED_FILES,
            },
            indent=2,
        )
    )
    print("\n" + athena_instructions())


if __name__ == "__main__":
    main()
