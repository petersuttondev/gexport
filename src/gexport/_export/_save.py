import shutil
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import Literal, NoReturn

from gexport._export._gi import Gimp, Gio


def _raise_export_failed(path: Path) -> NoReturn:
    raise RuntimeError(f"Export failed: {path}")


def _save_via_proc(
    proc_name: str,
    image: Gimp.Image,
    path: Path,
    **kwargs: object,
) -> None:
    pdb = Gimp.get_pdb()
    assert pdb is not None
    proc = pdb.lookup_procedure(proc_name)
    assert proc is not None
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    config.set_property("image", image)
    config.set_property("file", Gio.File.new_for_path(str(path)))
    config.set_property("options", None)
    for key, value in kwargs.items():
        config.set_property(key.replace("_", "-"), value)
    result = proc.run(config)
    if result.index(0) != Gimp.PDBStatusType.SUCCESS:
        _raise_export_failed(path)


def _save_avif_via_avifenc(input_path: Path, output_path: Path) -> None:
    subprocess.run(
        (
            "avifenc",
            *("--qcolor", "75"),
            *("--qalpha", "75"),
            *("--speed", "0"),
            *("--output", output_path),
            *("--depth", "8"),
            *("--yuv", "420"),
            "--sharpyuv",
            *("--codec", "aom"),
            "--ignore-exif",
            "--ignore-xmp",
            "--ignore-profile",
            "--ignore-gain-map",
            input_path,
        ),
        stdin=subprocess.DEVNULL,
        check=True,
    )


def _save_avif_via_proc(image: Gimp.Image, path: Path) -> None:
    _save_via_proc(
        "file-heif-av1-export",
        image,
        path,
        quality=75,
        lossless=False,
        save_bit_depth=8,
        pixel_format="yuv420",
        encoder_speed="slow",
        include_exif=False,
        include_xmp=False,
    )


def _save_avif(image: Gimp.Image, path: Path, working_dir: Path) -> None:
    if shutil.which("avifenc") is None:
        print(
            "WARNING: avifenc not installed! Falling back to GIMP's AVIF exporter",
            file=sys.stderr,
        )
        _save_avif_via_proc(image, path)
        return

    png_path = working_dir / path.with_suffix(".png").name
    _save_png(image, png_path, preset="interchange")
    _save_avif_via_avifenc(png_path, path)
    png_path.unlink()


def _save_png(
    image: Gimp.Image,
    path: Path,
    *,
    preset: Literal["delivery", "interchange"] = "delivery",
) -> None:
    def for_preset[T](delivery: T, interchange: T) -> T:
        match preset:
            case "delivery":
                return delivery
            case "interchange":
                return interchange

    _save_via_proc(
        "file-png-export",
        image,
        path,
        interlaced=False,
        compression=for_preset(9, 0),
        bkgd=False,
        offs=False,
        phys=False,
        time=False,
        save_transparent=False,
        optimize_palette=for_preset(True, False),
        format="auto",
        include_exif=False,
        include_iptc=False,
        include_xmp=False,
        include_color_profile=False,
        include_thumbnail=False,
        include_comment=False,
    )


def _save_webp(image: Gimp.Image, path: Path) -> None:
    _save_via_proc(
        "file-webp-export",
        image,
        path,
        lossless=False,
        quality=90.0,
        alpha_quality=100.0,
        # Sharp YUV ignores alpha, so it puts a saturated halo on hard edges
        # next to transparent areas (e.g. orange on a brown wall). It may help
        # at hard edges between saturated colours but makes little visual
        # difference in low-saturation photos and increases file size roughly
        # 5%.
        use_sharp_yuv=False,
        include_color_profile=False,
        include_exif=False,
        include_iptc=False,
        include_thumbnail=False,
        include_xmp=False,
    )


def _save_generic(image: Gimp.Image, path: Path) -> None:
    if not Gimp.file_save(
        run_mode=Gimp.RunMode.NONINTERACTIVE,
        image=image,
        file=Gio.File.new_for_path(str(path)),
        options=None,
    ):
        _raise_export_failed(path)


def save_image(image: Gimp.Image, path: Path, working_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    match path.suffix.lower():
        case ".avif":
            save = partial(_save_avif, working_dir=working_dir)
        case ".png":
            save = _save_png
        case ".webp":
            save = _save_webp
        case _:
            save = _save_generic
    save(image, path)
