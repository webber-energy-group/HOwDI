# SPDX-License-Identifier: GPL-3.0-or-later

""" This code instantiates HOwDI as a package using the
setuptools module. This allows HOwDI to be imported anywhere in
your system, as long as the package is configured using `pip install .`
from this directory. Add a `-e` flag to the end of the command to make
the package "editable", meaning that changes to the code will not require
reinstallation of the package. This is useful for development purposes.
"""

from setuptools import setup

setup(
    name="HOwDI",
    version="0.0.0",
    packages=["HOwDI"],
    entry_points={
        "console_scripts": [
            "HOwDI = HOwDI.module_select:main",
            "HOWDI = HOwDI.module_select:main",
            "howdi = HOwDI.module_select:main",
        ]
    },
)
