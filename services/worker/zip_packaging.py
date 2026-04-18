"""Упаковка project.zip без зависимости от CadQuery (тестируемо изолированно)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from worker.core.exceptions import BlueprintGenerationError


def create_project_zip(base_dir: Path, zip_path: Path) -> None:
    """
    Упаковывает промышленную структуру: assembly/, parts/, scripts/, simulation/, bom.csv.
    """
    assembly_glb = base_dir / "assembly" / "model.glb"
    assembly_step = base_dir / "assembly" / "assembly.step"
    sim_xml = base_dir / "simulation" / "simulation.xml"
    bom_csv = base_dir / "bom.csv"
    py_script = base_dir / "scripts" / "build_model.py"

    if not assembly_glb.is_file():
        raise BlueprintGenerationError("create_project_zip: нет assembly/model.glb")
    if not assembly_step.is_file():
        raise BlueprintGenerationError("create_project_zip: нет assembly/assembly.step")
    if not sim_xml.is_file():
        raise BlueprintGenerationError("create_project_zip: нет simulation/simulation.xml")
    if not bom_csv.is_file():
        raise BlueprintGenerationError("create_project_zip: нет bom.csv")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(assembly_glb, arcname="assembly/model.glb")
        zf.write(assembly_step, arcname="assembly/assembly.step")
        zf.write(sim_xml, arcname="simulation/simulation.xml")
        zf.write(bom_csv, arcname="bom.csv")
        if py_script.is_file():
            zf.write(py_script, arcname="scripts/build_model.py")

        mp4 = base_dir / "simulation" / "physics_preview.mp4"
        if mp4.is_file():
            zf.write(mp4, arcname="simulation/physics_preview.mp4")

        parts_dir = base_dir / "parts"
        if parts_dir.is_dir():
            for f in sorted(parts_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in (".stl", ".step"):
                    zf.write(f, arcname=f"parts/{f.name}")
