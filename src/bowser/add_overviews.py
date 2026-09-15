import logging
from enum import Enum
from os import fspath
from pathlib import Path
from typing import Sequence

import click
from osgeo import gdal
from tqdm.contrib.concurrent import thread_map

PathOrStr = Path | str

gdal.UseExceptions()

logger = logging.getLogger("bowser")


class Resampling(Enum):
    """GDAL resampling algorithm."""

    NEAREST = "nearest"
    AVERAGE = "average"
    LANCZOS = "lanczos"


# TODO: This thing can now be done with the 3.11 GDAL cli
# https://gdal.org/en/stable/programs/gdal_raster_overview_add.html#gdal-raster-overview-add
# gdal raster overview add --config COMPRESS_OVERVIEW=LZW data.tif 2 4 8 16


def add_overviews(
    file_path: Path | str,
    overview_levels: Sequence[int] = [4, 8, 16, 32, 64],
    resampling: Resampling = Resampling.NEAREST,
    external: bool = False,
    compression: str = "LZW",
):
    """Add GDAL compressed overviews to an existing file.

    Parameters
    ----------
    file_path : Path
        Path to the file to process.
    overview_levels : list
        List of overview levels to add.
    resampling : str or Resampling
        GDAL resampling algorithm for overviews.
        Default = "nearest"
    external : bool, default = False
        Use external overviews (.ovr files).
    compression: str, default = "LZW"
        Compression algorithm to use for overviews.
        See https://gdal.org/programs/gdaladdo.html for options.
    """
    flags = gdal.GA_Update if not external else gdal.GA_ReadOnly
    ds = gdal.Open(fspath(file_path), flags)
    if ds.GetRasterBand(1).GetOverviewCount() > 0:
        logger.info("%s already has overviews. Skipping.")
        return
    raster = gdal.Open(fspath(file_path), flags)
    gdal.SetConfigOption("COMPRESS_OVERVIEW", compression)
    gdal.SetConfigOption("GDAL_NUM_THREADS", "2")
    raster.BuildOverviews(resampling.value, overview_levels)


def process_files(
    file_paths: Sequence[PathOrStr],
    levels: Sequence[int],
    resampling: Resampling,
    max_workers: int = 5,
):
    """Process files to add GDAL overviews and compression.

    Parameters
    ----------
    file_paths : Sequence[PathOrStr]
        Sequence of file paths to process.
    levels : Sequence[int]
        Sequence of overview levels to add.
    resampling : str or Resampling
        GDAL resampling algorithm for overviews.
        Default = "nearest"
    max_workers : int, default = 5
        Number of parallel threads to run.
    """
    thread_map(
        lambda file_path: add_overviews(
            Path(file_path),
            overview_levels=list(levels),
            resampling=resampling,
        ),
        file_paths,
        max_workers=max_workers,
    )


@click.command()
@click.argument("file_paths", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--levels",
    "-l",
    multiple=True,
    default=[4, 8, 16, 32, 64],
    type=int,
    help="Overview levels to add.",
    show_default=True,
)
@click.option(
    "--resampling",
    "-r",
    type=click.Choice([r.value for r in Resampling]),
    default="nearest",
    help="Resampling algorithm to use when building overviews",
    show_default=True,
)
@click.option(
    "--max-workers",
    "-n",
    default=5,
    type=int,
    help="Number of parallel files to process",
)
def addo(file_paths, levels, resampling, max_workers):
    """Add compressed GDAL overviews to files."""
    return process_files(
        file_paths=file_paths,
        levels=levels,
        resampling=Resampling(resampling),
        max_workers=max_workers,
    )