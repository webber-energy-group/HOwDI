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
