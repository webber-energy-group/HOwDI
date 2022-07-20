from setuptools import setup

setup(
    name="HOwDI",
    version="0.0.0",
    packages=["HOwDI"],
    entry_points={
        "console_scripts": [
            "HOwDI-run = HOwDI.run:main",
            "HOwDI-create_fig = HOwDI.postprocessing.create_plot:main",
            "HOwDI-traceback = HOwDI.postprocessing.traceback_path:main",
            "HOwDI-traceforward = HOwDI.postprocessing.traceforward_path:main",
            "HOwDI-help = HOwDI.help:main",
        ]
    },
)
