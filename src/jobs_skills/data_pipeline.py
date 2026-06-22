"""Build normalized SkillsFuture jobs-skills feature tables.

This module implements M1 from docs/roadmap.md. It only ingests, normalizes,
joins, validates, and exports data tables. It does not perform scoring,
questionnaire logic, graph planning, or Telegram integration.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


SKILLS_FRAMEWORK_FILE = "jobsandskills-skillsfuture-skills-framework-dataset.xlsx"
TSC_MAPPING_FILE = "jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx"
UNIQUE_SKILLS_FILE = "jobsandskills-skillsfuture-unique-skills-list.xlsx"

PL_TEXT_MAP = {
    "basic": 1.0,
    "intermediate": 3.0,
    "advanced": 5.0,
}


@dataclass(frozen=True)
class PipelinePaths:
    project_root: Path
    dataset_dir: Path
    output_dir: Path

    @classmethod
    def from_args(cls, project_root: Path, dataset_dir: Path, output_dir: Path) -> "PipelinePaths":
        root = project_root.resolve()
        return cls(
            project_root=root,
            dataset_dir=(root / dataset_dir).resolve() if not dataset_dir.is_absolute() else dataset_dir.resolve(),
            output_dir=(root / output_dir).resolve() if not output_dir.is_absolute() else output_dir.resolve(),
        )


def clean_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    return text


def normalize_frame_strings(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object" or str(out[col].dtype).startswith("str"):
            out[col] = out[col].map(clean_text)
    return out


def normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def normalize_pl_value(value: object) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    mapped = PL_TEXT_MAP.get(text.lower())
    if mapped is not None:
        return mapped
    try:
        return float(text)
    except ValueError:
        return None


def normalize_pl_key(value: object) -> str | None:
    level = normalize_pl_value(value)
    if level is None:
        return None
    if float(level).is_integer():
        return str(int(level))
    return str(level)


def stable_id(prefix: str, parts: Iterable[object]) -> str:
    raw = "||".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def read_sources(paths: PipelinePaths) -> dict[str, pd.DataFrame]:
    framework = paths.dataset_dir / SKILLS_FRAMEWORK_FILE
    mapping = paths.dataset_dir / TSC_MAPPING_FILE
    unique = paths.dataset_dir / UNIQUE_SKILLS_FILE
    required = [framework, mapping, unique]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required dataset files: {missing}")

    return {
        "role_desc": normalize_frame_strings(pd.read_excel(framework, sheet_name="Job Role_Description")),
        "role_skills": normalize_frame_strings(pd.read_excel(framework, sheet_name="Job Role_TCS_CCS")),
        "skill_key": normalize_frame_strings(pd.read_excel(framework, sheet_name="TSC_CCS_Key")),
        "skill_ka": normalize_frame_strings(pd.read_excel(framework, sheet_name="TSC_CCS_K&A")),
        "tsc_mapping": normalize_frame_strings(pd.read_excel(mapping, sheet_name="data")),
        "unique_skills": normalize_frame_strings(pd.read_excel(unique, sheet_name="Unique Skills List")),
    }


def build_roles(role_desc: pd.DataFrame) -> pd.DataFrame:
    roles = role_desc.rename(
        columns={
            "Sector": "sector",
            "Track": "track",
            "Job Role": "job_role",
            "Job Role Description": "job_role_description",
            "Performance Expectation": "performance_expectation",
        }
    )[["sector", "track", "job_role", "job_role_description", "performance_expectation"]].drop_duplicates()
    roles.insert(0, "role_id", roles.apply(lambda row: stable_id("role", [row.sector, row.track, row.job_role]), axis=1))
    return roles.sort_values(["sector", "track", "job_role"]).reset_index(drop=True)


def build_skills(unique_skills: pd.DataFrame) -> pd.DataFrame:
    skills = unique_skills.rename(
        columns={
            "skill_title": "unique_skill_title",
            "skill_description": "unique_skill_description",
            "skill_type": "skill_type",
            "Emerging Skills": "is_emerging_skill",
            "CASL Skills": "is_casl_skill",
        }
    )[["unique_skill_title", "unique_skill_description", "skill_type", "is_emerging_skill", "is_casl_skill"]].copy()
    skills["is_emerging_skill"] = skills["is_emerging_skill"].map(normalize_bool)
    skills["is_casl_skill"] = skills["is_casl_skill"].map(normalize_bool)
    skills = skills.drop_duplicates(subset=["unique_skill_title"]).copy()
    skills.insert(0, "skill_id", skills["unique_skill_title"].map(lambda title: stable_id("skill", [title])))
    return skills.sort_values("unique_skill_title").reset_index(drop=True)


def build_mapping(tsc_mapping: pd.DataFrame, skills: pd.DataFrame) -> pd.DataFrame:
    mapping = tsc_mapping.rename(
        columns={
            "skills_framework_skill_code": "tsc_ccs_code",
            "skills_framework_skill_title": "tsc_ccs_title",
            "skills_framework_skill_desc": "tsc_ccs_description",
            "skills_framework_skill_pl": "proficiency_level_raw",
            "skills_framework_pl_desc": "proficiency_description",
            "Unique skill_updated_skill_title": "unique_skill_title",
            "Unique skill_updated_skill_desc": "unique_skill_description",
            "Unique skill_updated_skill_type": "unique_skill_type",
            "Unique skill_updated_sector_tagging": "unique_skill_sector_tagging",
        }
    ).copy()
    mapping["proficiency_level"] = mapping["proficiency_level_raw"].map(normalize_pl_value)
    mapping["proficiency_level_key"] = mapping["proficiency_level_raw"].map(normalize_pl_key)
    mapping = mapping.merge(skills[["skill_id", "unique_skill_title"]], on="unique_skill_title", how="left")
    mapping = mapping.drop_duplicates(subset=["tsc_ccs_code", "proficiency_level_key"]).copy()
    return mapping[
        [
            "tsc_ccs_code",
            "proficiency_level_key",
            "skill_id",
            "unique_skill_title",
            "unique_skill_description",
            "unique_skill_type",
            "unique_skill_sector_tagging",
            "proficiency_description",
        ]
    ]


def build_role_skill_requirements(
    role_skills: pd.DataFrame,
    roles: pd.DataFrame,
    mapping: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = role_skills.reset_index(names="source_row_number").rename(
        columns={
            "Sector": "sector",
            "Track": "track",
            "Job Role": "job_role",
            "TSC_CCS Title": "tsc_ccs_title",
            "TSC_CCS Type": "tsc_ccs_type",
            "Proficiency Level": "proficiency_level_raw",
            "TSC_CCS Code": "tsc_ccs_code",
        }
    ).copy()
    source["source_row_number"] = source["source_row_number"] + 2
    source["proficiency_level"] = source["proficiency_level_raw"].map(normalize_pl_value)
    source["proficiency_level_key"] = source["proficiency_level_raw"].map(normalize_pl_key)

    merged = source.merge(roles[["role_id", "sector", "track", "job_role"]], on=["sector", "track", "job_role"], how="left")
    merged = merged.merge(mapping, on=["tsc_ccs_code", "proficiency_level_key"], how="left", suffixes=("", "_mapped"))

    audit = merged.copy()
    merged["skill_weight"] = 1.0
    merged["source_file"] = SKILLS_FRAMEWORK_FILE
    merged["source_sheet"] = "Job Role_TCS_CCS"

    group_cols = ["role_id", "skill_id"]
    idx = (
        merged.sort_values(["proficiency_level", "source_row_number"], ascending=[False, True])
        .dropna(subset=["role_id", "skill_id"])
        .drop_duplicates(subset=group_cols, keep="first")
        .index
    )
    requirements = merged.loc[idx].copy()
    requirements.insert(
        0,
        "role_skill_requirement_id",
        requirements.apply(lambda row: stable_id("req", [row.role_id, row.skill_id]), axis=1),
    )
    requirements = requirements[
        [
            "role_skill_requirement_id",
            "role_id",
            "skill_id",
            "required_level",
            "skill_weight",
            "sector",
            "track",
            "job_role",
            "unique_skill_title",
            "tsc_ccs_code",
            "tsc_ccs_title",
            "tsc_ccs_type",
            "proficiency_level_raw",
            "proficiency_description",
            "source_file",
            "source_sheet",
            "source_row_number",
        ]
    ] if "required_level" in requirements.columns else requirements.rename(columns={"proficiency_level": "required_level"})[
        [
            "role_skill_requirement_id",
            "role_id",
            "skill_id",
            "required_level",
            "skill_weight",
            "sector",
            "track",
            "job_role",
            "unique_skill_title",
            "tsc_ccs_code",
            "tsc_ccs_title",
            "tsc_ccs_type",
            "proficiency_level_raw",
            "proficiency_description",
            "source_file",
            "source_sheet",
            "source_row_number",
        ]
    ]
    return requirements.sort_values(["sector", "track", "job_role", "unique_skill_title"]).reset_index(drop=True), audit


def build_skill_ka_items(skill_ka: pd.DataFrame, mapping: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = skill_ka.reset_index(names="source_row_number").rename(
        columns={
            "TSC_CCS Type": "tsc_ccs_type",
            "TSC_CCS Code": "tsc_ccs_code",
            "Sector": "sector",
            "TSC_CCS Category": "tsc_ccs_category",
            "TSC_CCS Title": "tsc_ccs_title",
            "TSC_CCS Description": "tsc_ccs_description",
            "Proficiency Level": "proficiency_level_raw",
            "Proficiency Description": "proficiency_description",
            "Knowledge / Ability Items": "ka_item",
            "Knowledge / Ability Classification": "ka_classification",
        }
    ).copy()
    source["source_row_number"] = source["source_row_number"] + 2
    source["proficiency_level"] = source["proficiency_level_raw"].map(normalize_pl_value)
    source["proficiency_level_key"] = source["proficiency_level_raw"].map(normalize_pl_key)
    merged = source.merge(mapping[["tsc_ccs_code", "proficiency_level_key", "skill_id", "unique_skill_title"]], on=["tsc_ccs_code", "proficiency_level_key"], how="left")
    merged["source_file"] = SKILLS_FRAMEWORK_FILE
    merged["source_sheet"] = "TSC_CCS_K&A"
    merged.insert(
        0,
        "skill_ka_item_id",
        merged.apply(lambda row: stable_id("ka", [row.tsc_ccs_code, row.proficiency_level_key, row.ka_classification, row.ka_item]), axis=1),
    )
    items = merged[
        [
            "skill_ka_item_id",
            "skill_id",
            "unique_skill_title",
            "tsc_ccs_code",
            "tsc_ccs_title",
            "tsc_ccs_type",
            "tsc_ccs_category",
            "sector",
            "proficiency_level",
            "proficiency_level_raw",
            "proficiency_description",
            "ka_item",
            "ka_classification",
            "source_file",
            "source_sheet",
            "source_row_number",
        ]
    ]
    return items.sort_values(["unique_skill_title", "proficiency_level", "ka_classification", "ka_item"]).reset_index(drop=True), merged


def find_sample_profiles(requirements: pd.DataFrame, pattern: str) -> pd.DataFrame:
    mask = requirements["job_role"].str.contains(pattern, case=False, na=False)
    cols = [
        "sector",
        "track",
        "job_role",
        "unique_skill_title",
        "required_level",
        "tsc_ccs_code",
        "tsc_ccs_title",
    ]
    return requirements.loc[mask, cols].sort_values(["sector", "track", "job_role", "required_level", "unique_skill_title"])



def frame_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    columns = list(frame.columns)

    def cell(value: object) -> str:
        text = "" if pd.isna(value) else str(value)
        return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(cell(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def write_report(
    paths: PipelinePaths,
    roles: pd.DataFrame,
    skills: pd.DataFrame,
    requirements: pd.DataFrame,
    role_skill_audit: pd.DataFrame,
    skill_ka_items: pd.DataFrame,
    skill_ka_audit: pd.DataFrame,
    mapping: pd.DataFrame,
) -> None:
    role_skill_total = len(role_skill_audit)
    role_skill_unique = len(requirements)
    role_skill_mapping_matches = int(role_skill_audit["skill_id"].notna().sum())
    role_skill_role_matches = int(role_skill_audit["role_id"].notna().sum())
    ka_total = len(skill_ka_audit)
    ka_mapping_matches = int(skill_ka_audit["skill_id"].notna().sum())
    ka_keys = skill_ka_audit[["tsc_ccs_code", "proficiency_level_key"]].drop_duplicates()
    role_skill_ka_matches = int(
        role_skill_audit[["tsc_ccs_code", "proficiency_level_key"]]
        .merge(ka_keys, on=["tsc_ccs_code", "proficiency_level_key"], how="left", indicator=True)["_merge"]
        .eq("both")
        .sum()
    )
    non_numeric_pl = role_skill_audit["proficiency_level_raw"].map(clean_text).str.lower().isin(PL_TEXT_MAP).sum()
    unmapped_unique_titles = int(mapping["skill_id"].isna().sum())

    data_analyst_samples = find_sample_profiles(requirements, "Data Analyst").head(30)
    data_scientist_samples = find_sample_profiles(requirements, "Data Scientist").head(30)

    report = [
        "# M1 Data Quality Report",
        "",
        "## Summary Counts",
        "",
        f"- Roles: {len(roles):,}",
        f"- Skills: {len(skills):,}",
        f"- Role-skill source rows: {role_skill_total:,}",
        f"- Role-skill normalized requirement rows: {role_skill_unique:,}",
        f"- K&A source rows: {ka_total:,}",
        f"- K&A normalized rows: {len(skill_ka_items):,}",
        "",
        "## Join Coverage",
        "",
        f"- Role-skill rows matched to roles: {role_skill_role_matches:,} / {role_skill_total:,} ({role_skill_role_matches / role_skill_total:.2%})",
        f"- Role-skill rows matched to unique skills: {role_skill_mapping_matches:,} / {role_skill_total:,} ({role_skill_mapping_matches / role_skill_total:.2%})",
        f"- Role-skill rows with matching K&A items: {role_skill_ka_matches:,} / {role_skill_total:,} ({role_skill_ka_matches / role_skill_total:.2%})",
        f"- K&A rows matched to unique skills: {ka_mapping_matches:,} / {ka_total:,} ({ka_mapping_matches / ka_total:.2%})",
        f"- TSC mapping rows missing unique skill ids: {unmapped_unique_titles:,}",
        "",
        "## Proficiency Normalization",
        "",
        "- Numeric proficiency levels are kept as numeric values.",
        "- Text proficiency levels are mapped with `Basic = 1`, `Intermediate = 3`, `Advanced = 5`.",
        f"- Role-skill rows with text proficiency levels normalized: {int(non_numeric_pl):,}",
        "",
        "## Source Traceability",
        "",
        "- `role_skill_requirements` preserves source file, sheet, row number, TSC/CCS code, source title, raw proficiency, and proficiency description.",
        "- `skill_ka_items` preserves source file, sheet, row number, TSC/CCS code, K&A classification, item text, and proficiency description.",
        "- MVP `skill_weight` is set to `1.0` for every role-skill requirement.",
        "",
        "## Sample Data Analyst Profile Rows",
        "",
        frame_to_markdown(data_analyst_samples) if not data_analyst_samples.empty else "No Data Analyst rows found.",
        "",
        "## Sample Data Scientist Profile Rows",
        "",
        frame_to_markdown(data_scientist_samples) if not data_scientist_samples.empty else "No Data Scientist rows found.",
        "",
    ]
    (paths.output_dir / "data_quality_report.md").write_text("\n".join(report), encoding="utf-8")


def write_outputs(paths: PipelinePaths, tables: dict[str, pd.DataFrame]) -> None:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        target = paths.output_dir / f"{name}.csv"
        temp_target = paths.output_dir / f".{name}.csv.tmp"
        if temp_target.exists():
            temp_target.unlink()
        frame.to_csv(str(temp_target), index=False, encoding="utf-8")
        if target.exists():
            target.unlink()
        temp_target.replace(target)


def run_pipeline(paths: PipelinePaths) -> dict[str, pd.DataFrame]:
    sources = read_sources(paths)
    roles = build_roles(sources["role_desc"])
    skills = build_skills(sources["unique_skills"])
    mapping = build_mapping(sources["tsc_mapping"], skills)
    requirements, role_skill_audit = build_role_skill_requirements(sources["role_skills"], roles, mapping)
    skill_ka_items, skill_ka_audit = build_skill_ka_items(sources["skill_ka"], mapping)

    tables = {
        "roles": roles,
        "skills": skills,
        "role_skill_requirements": requirements,
        "skill_ka_items": skill_ka_items,
    }
    write_outputs(paths, tables)
    write_report(paths, roles, skills, requirements, role_skill_audit, skill_ka_items, skill_ka_audit, mapping)
    return tables


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normalized SkillsFuture jobs-skills feature tables.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = PipelinePaths.from_args(args.project_root, args.dataset_dir, args.output_dir)
    tables = run_pipeline(paths)
    print(f"roles={len(tables['roles'])}")
    print(f"skills={len(tables['skills'])}")
    print(f"role_skill_requirements={len(tables['role_skill_requirements'])}")
    print(f"skill_ka_items={len(tables['skill_ka_items'])}")
    print(f"output_dir={paths.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


