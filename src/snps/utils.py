""" Utility classes and functions.

"""

"""
BSD 3-Clause License

Copyright (c) 2019, Andrew Riha
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

import datetime
import gzip
import io
import logging
from multiprocessing import Pool
import os
import re
import shutil
import zipfile

from atomicwrites import atomic_write
import pandas as pd

import snps

logger = logging.getLogger(__name__)


class Parallelizer:
    def __init__(self, parallelize=False, processes=os.cpu_count()):
        """ Initialize a `Parallelizer`.

        Parameters
        ----------
        parallelize : bool
            utilize multiprocessing to speedup calculations
        processes : int
            processes to launch if multiprocessing
        """
        self._parallelize = parallelize
        self._processes = processes

    def __call__(self, f, tasks):
        """ Optionally parallelize execution of a function.

        Parameters
        ----------
        f : func
            function to execute
        tasks : list of dict
            tasks to pass to `f`

        Returns
        -------
        list
            results of each call to `f`
        """
        if self._parallelize:
            with Pool(self._processes) as p:
                return p.map(f, tasks)
        else:
            return map(f, tasks)


def create_dir(path):
    """ Create directory specified by `path` if it doesn't already exist.

    Parameters
    ----------
    path : str
        path to directory

    Returns
    -------
    bool
        True if `path` exists
    """
    # https://stackoverflow.com/a/5032238
    os.makedirs(path, exist_ok=True)

    if os.path.exists(path):
        return True
    else:
        return False


def save_df_as_csv(
    df, path, filename, comment="", prepend_info=True, atomic=True, **kwargs
):
    """ Save dataframe to a CSV file.

    Parameters
    ----------
    df : pandas.DataFrame
        dataframe to save
    path : str
        path to directory where to save CSV file
    filename : str or buffer
        filename for file to save or buffer to write to
    comment : str
        header comment(s); one or more lines starting with '#'
    prepend_info : bool
        prepend file generation information as comments
    atomic : bool
        atomically write output to a file on local filesystem
    **kwargs
        additional parameters to `pandas.DataFrame.to_csv`

    Returns
    -------
    str or buffer
        path to saved file or buffer (empty str if error)
    """
    buffer = False
    if isinstance(filename, io.IOBase):
        buffer = True

    if isinstance(df, pd.DataFrame) and len(df) > 0:
        if not buffer and not create_dir(path):
            return ""

        if buffer:
            destination = filename
        else:
            destination = os.path.join(path, filename)
            logger.info(f"Saving {os.path.relpath(destination)}")

        if prepend_info:
            s = (
                f"# Generated by snps v{snps.__version__}, https://pypi.org/project/snps/\n"
                f'# Generated at {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC\n'
            )
        else:
            s = ""

        s += comment

        if "na_rep" not in kwargs:
            kwargs["na_rep"] = "--"

        if buffer:
            destination.write(s)
            df.to_csv(destination, **kwargs)
            destination.seek(0)
        elif atomic:
            with atomic_write(destination, mode="w", overwrite=True) as f:
                f.write(s)
                # https://stackoverflow.com/a/29233924
                df.to_csv(f, **kwargs)
        else:
            with open(destination, mode="w") as f:
                f.write(s)
                df.to_csv(f, **kwargs)

        return destination
    else:
        logger.warning("no data to save...")
        return ""


def clean_str(s):
    """ Clean a string so that it can be used as a Python variable name.

    Parameters
    ----------
    s : str
        string to clean

    Returns
    -------
    str
        string that can be used as a Python variable name
    """
    # http://stackoverflow.com/a/3305731
    # https://stackoverflow.com/a/52335971
    return re.sub(r"\W|^(?=\d)", "_", s)


def zip_file(src, dest, arcname):
    """ Zip a file.

    Parameters
    ----------
    src : str
        path to file to zip
    dest : str
        path to output zip file
    arcname : str
        name of file in zip archive

    Returns
    -------
    str
        path to zipped file
    """
    with atomic_write(dest, mode="wb", overwrite=True) as f:
        with zipfile.ZipFile(f, "w") as f_zip:
            # https://stackoverflow.com/a/16104667
            f_zip.write(src, arcname=arcname)
    return dest


def gzip_file(src, dest):
    """ Gzip a file.

    Parameters
    ----------
    src : str
        path to file to gzip
    dest : str
        path to output gzip file

    Returns
    -------
    str
        path to gzipped file
    """
    with open(src, "rb") as f_in:
        with atomic_write(dest, mode="wb", overwrite=True) as f_out:
            with gzip.open(f_out, "wb") as f_gzip:
                shutil.copyfileobj(f_in, f_gzip)
    return dest
