# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Plexa'
copyright = '2026, Kellan'
author = 'Kellan'
release = '0.1'


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.todo",
    "sphinx_autodoc_typehints",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_togglebutton",
    "sphinx_last_updated_by_git",
    "sphinxcontrib.mermaid",
    "sphinxext.opengraph",
]

templates_path = ['_templates']
exclude_patterns = []

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_mock_imports = []
suppress_warnings = ["sphinx_autodoc_typehints.forward_reference"]

autosectionlabel_prefix_document = True
todo_include_todos = True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']


# -- Set custom root for imports

from pathlib import Path
import sys

DOCS_SOURCE = Path(__file__).resolve().parent
PROJECT_ROOT = DOCS_SOURCE.parent.parent
SERVER_PACKAGE_ROOT = PROJECT_ROOT / "plexa_server"

sys.path.insert(0, str(PROJECT_ROOT))
