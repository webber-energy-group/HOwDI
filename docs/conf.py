import os
import sys

import sphinx_rtd_theme

import HOwDI

sys.path.insert(0, os.path.abspath("../HOwDI"))
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "HOwDI"
copyright = "2023, Braden Pecora"
author = "Braden Pecora"
release = HOwDI.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- LaTeX configuration -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#latex-configuration
latex_elements = {"preamble": r"\usepackage{chemformula}"}

# -- Options for TODO output -------------------------------------------------
todo_include_todos = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
