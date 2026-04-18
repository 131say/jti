"""Headless MuJoCo: короткий прогон и экспорт physics_preview.mp4 (best-effort)."""

from __future__ import annotations

import logging
from pathlib import Path

import mujoco

logger = logging.getLogger(__name__)

# Размеры кратны 16 — совместимость с libx264 без лишнего ресайза.
_DEFAULT_WIDTH = 640
_DEFAULT_HEIGHT = 480


def run_headless_simulation(
    xml_path: Path,
    output_path: Path,
    *,
    duration_seconds: float = 2.0,
    fps: int = 24,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
) -> None | list[str]:
    """
    Загружает MJCF, прогоняет mj_step, пишет MP4.

    :return: ``None`` при успехе; иначе список строк для ``warnings`` job.
    """
    if not xml_path.is_file():
        msg = f"physics preview: XML не найден: {xml_path}"
        logger.warning("%s", msg)
        return [msg]

    try:
        import imageio.v2 as imageio
    except ImportError as e:
        msg = f"physics preview: imageio недоступен: {e!s}"
        logger.warning("%s", msg)
        return [msg]

    try:
        model = mujoco.MjModel.from_xml_path(str(xml_path.resolve()))
    except Exception as e:
        msg = f"physics preview: не удалось загрузить MJCF: {e!s}"
        logger.warning("%s", msg, exc_info=True)
        return [msg]

    data = mujoco.MjData(model)

    if model.nv > 0:
        data.qvel[0] = 3.0
    else:
        logger.info(
            "physics preview: nv=0, движение не ожидается (статичные кадры)."
        )

    timestep = float(model.opt.timestep)
    if timestep <= 0:
        timestep = 0.002

    nframes = max(1, int(duration_seconds * fps))
    steps_per_frame = max(1, int(round(1.0 / (fps * timestep))))

    renderer: mujoco.Renderer | None = None
    frames: list = []

    try:
        renderer = mujoco.Renderer(model, height, width)
        mujoco.mj_forward(model, data)

        for _ in range(nframes):
            for _ in range(steps_per_frame):
                mujoco.mj_step(model, data)
            renderer.update_scene(data)
            pixels = renderer.render()
            frames.append(pixels)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        imageio.mimsave(
            str(output_path),
            frames,
            fps=fps,
            codec="libx264",
            quality=8,
            macro_block_size=1,
        )
    except Exception as e:
        msg = f"physics preview: сбой рендера/кодирования: {e!s}"
        logger.warning("%s", msg, exc_info=True)
        return [msg]
    finally:
        if renderer is not None:
            try:
                renderer.close()
            except Exception as e:
                logger.debug("renderer.close: %s", e)

    if not output_path.is_file() or output_path.stat().st_size < 32:
        msg = "physics preview: выходной файл пуст или слишком мал"
        logger.warning("%s", msg)
        return [msg]

    return None
