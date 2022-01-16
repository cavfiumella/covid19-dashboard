
"""Download Italian datasets for Covid19 contagions and vaccinations.

Main functions of this module are the higher-level functions `update_contagions`
and `update_vaccinations`; look at their documentation for further details.
Other functions are useful for module operations and should not used on their
own from the main app.
"""


import logging
from logging import getLogger
from pathlib import Path
import pandas as pd
from urllib.error import HTTPError
from typing import Optional
import joblib as jb
from tqdm.auto import tqdm
from urllib.request import urlopen
import json


# module logger
LOGGER = getLogger(__name__)


def create_dir(dir, /) -> None:
    """Create new directory `dir` if needed.

    Parameters:
    - dir: path to the new directory.
    """

    dir = Path(dir)

    if not dir.exists():
        dir.mkdir()
        LOGGER.info(f"New directory '{dir}'")
    else:
        LOGGER.debug(f"Directory '{dir}' exists, ignore creation")


def download_csv(url, raise_error: bool = False) -> pd.DataFrame:
    """Download a CSV file using pandas.
    This is just a wrapper that allows to handle HTTPError when needed.

    Parameters:
    - url: file remote url;
    - raise_error: raise exception on download failure.

    Return:
    A valid pandas.DataFrame if download succeded, None when `raise_error` is
    False; on failures HTTP error is logged when `raise_error` is False.
    """

    LOGGER.debug(f"Downloading '{url}'")

    try:
        df = pd.read_csv(url)
    except HTTPError as ex:
        s = f"Unable to download '{url}': HTTP Error {ex.errno}: {ex.reason}"

        if raise_error:
            raise RuntimeError(s)
        else:
            LOGGER.error(s)
            return False

    return df


def update_contagions(
    dir, start_date: Optional = "2020-02-24", end_date: Optional = None,
    force: bool = False, progress: bool = True
) -> None:
    """Update contagions data using Github repository `pcm-dpc/COVID-19`.

    Parameters:
    - dir: path to an existing or creatable directory;
    - start_date, end_date: range of dates for data to fetch, default value for
                            end date is the current date;
    - force: force update of all files;
    - progress: show progress bar while downloading new data.

    If one date between start and end dates (today date excluded) is missing the
    HTTP error or any exception occured is raised.
    """

    # arguments

    start_date = pd.Timestamp(start_date)

    if end_date == None:
        end_date = pd.Timestamp.now()
    else:
        end_date = pd.Timestamp(end_date)

    dir = Path(dir)

    LOGGER.debug(
        f"Updating contagions data: dir = '{dir}', " + \
        f"start_date = '{start_date.strftime('%Y-%m-%d')}', " + \
        f"end_date = '{end_date.strftime('%Y-%m-%d')}'"
    )

    # directory structure

    create_dir(dir)

    # map subdirs to their paths
    subdirs = list(map(
        lambda s: dir.joinpath(s), ["dati-andamento-nazionale", "dati-regioni"]
    ))

    list(map(create_dir, subdirs))

    # files

    remote = "https://raw.githubusercontent.com/pcm-dpc/COVID-19/master"

    files = [
        subdir.joinpath(
            f"dpc-covid19-ita-{subdir.parts[-1].lstrip('dati').lstrip('-')}" + \
            f"-{date.strftime('%Y%m%d')}.csv"
        )
        for date in pd.date_range(start_date, end_date, normalize=True)
        for subdir in subdirs
    ]

    # remove existing files

    existing_files = []

    for file in files:
        if file.exists():
            existing_files += [file]

    if not force:
        for file in existing_files:
            files.remove(file)

    # update

    def update(file: Path) -> None:
        """Perform the update of a single file.
        This function is useful to be parallelized with joblib.
        """

        url = "/".join([remote, *file.parts[-2:]])
        date = pd.Timestamp(file.parts[-1].rstrip(".csv")[-8:])
        today = pd.Timestamp.now().normalize()

        # do not raise exceptions if today is missing: let's wait
        df = download_csv(url, raise_error = date != today)

        # when date == today df could be None if data is missing for the
        # current date
        if type(df) == pd.DataFrame:
            df.to_csv(file)
            LOGGER.debug(f"New file '{file}'")

    debug = getLogger().level == logging.DEBUG

    jb.Parallel(n_jobs = 1 if debug else -1)(
        jb.delayed(update)(file)
        for file in tqdm(
            files, desc = "Downloading contagions data",
            disable = debug or not progress
        )
    )


def update_vaccinations(
    dir, force: bool = False, progress: bool = True
) -> None:
    """Update vaccinations data using Github repository
    `italia/covid19-opendata-vaccini`.

    Parameters:
    - dir: path to an existing or creatable directory;
    - force: force update of all files;
    - progress: show progress bar while downloading new data.

    An exception (mostly HTTPError) is raised when unable to download remote
    timestamp or one of the needed files when remote is fresher.
    """

    # arguments

    dir = Path(dir)

    LOGGER.debug(
        f"Updating vaccinations data: dir = '{dir}', force = {force}, " + \
        f"progress = {progress}"
    )

    # directory structure

    create_dir(dir)

    # files

    remote = "https://raw.githubusercontent.com/italia/" + \
             "covid19-opendata-vaccini/master/dati"

    files = [
        "consegne-vaccini-latest.csv",
        "somministrazioni-vaccini-latest.csv",
        "platea.csv",
        "platea-dose-addizionale-booster.csv"
    ]

    last_update_file = dir.joinpath("last-update-dataset.json")

    # map files to their paths
    files = list(map(lambda s: dir.joinpath(s), files))

    # update timestamps

    # local last update timestamp
    if last_update_file.exists():
        with last_update_file.open() as file:
            t_local = pd.Timestamp(json.load(file)["ultimo_aggiornamento"])
    else:
        # force update with a very old t_local
        t_local = pd.Timestamp(0, tz="UTC")

    # remote last update timestamp
    last_update_remote = json.load(
        urlopen("/".join([remote, last_update_file.parts[-1]]))
    )
    t_remote = pd.Timestamp(last_update_remote["ultimo_aggiornamento"])

    LOGGER.debug(f"Update timestamps: remote: '{t_remote}', local: '{t_local}'")

    # no updates
    if not force and t_remote <= t_local:
        LOGGER.debug("No updates")
        return None

    # update timestamp
    with last_update_file.open("w") as file:
        json.dump(last_update_remote, file)

    # remove existing files

    existing_files = []

    for file in files:
        if file.exists():
            existing_files += [file]

    if not force:
        for file in existing_files:
            files.remove(file)

    # update

    def update(file: Path) -> None:
        """Perform the update of a single file.
        This function is useful to be parallelized with joblib.
        """

        url = "/".join([remote, file.parts[-1]])
        df = download_csv(url, raise_error=True)

        df.to_csv(file)
        LOGGER.debug(f"New file '{file}'")

    debug = getLogger().level == logging.DEBUG

    jb.Parallel(n_jobs = 1 if debug else -1)(
        jb.delayed(update)(file)
        for file in tqdm(
            files, desc = "Downloading contagions data",
            disable = debug or not progress
        )
    )
