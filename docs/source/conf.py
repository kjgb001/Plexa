"""Sphinx configuration for Plexa's authored and generated documentation."""

from __future__ import annotations

import os
import sys
from pathlib import Path


DOCS_SOURCE = Path(__file__).resolve().parent
PROJECT_ROOT = DOCS_SOURCE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

project = "Plexa"
copyright = "2026, Plexa contributors"
author = "Plexa contributors"
release = os.getenv("PLEXA_DOCS_VERSION", "development")
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
]

exclude_patterns = []
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
root_doc = "index"

myst_enable_extensions = ["colon_fence", "deflist", "fieldlist"]
myst_heading_anchors = 3

autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_member_order = "bysource"
autodoc_preserve_defaults = True
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = False

nitpicky = True
nitpick_ignore_regex = [
    (
        r"py:(class|data|exc|obj)",
        r"(FastAPI|APIRouter|HTTPException|Path|Response|'Message'|"
        r"abc\.ABC|argparse\.Namespace|collections\.abc\.(Callable|Iterable)|"
        r"datetime\.datetime|logging\.(Formatter|LogRecord)|"
        r"pathlib(\._local)?\.Path|annotated_types\.(Ge|Gt|Le)|"
        r"(fastapi|pydantic|starlette)\..*|"
        r"(ge|gt|le)=[0-9.]+)",
    ),
]
html_theme = "furo"
html_title = "Plexa Documentation"
html_short_title = "Plexa"
html_baseurl = os.getenv("PLEXA_DOCS_BASE_URL", "https://kjgb001.github.io/Plexa/")
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_show_sourcelink = False
html_theme_options = {
    "navigation_with_keys": True,
    "light_css_variables": {
        "color-brand-primary": "#1d7a68",
        "color-brand-content": "#1d7a68",
        "color-foreground-primary": "#14213d",
        "color-background-primary": "#fffdf8",
        "color-background-secondary": "#f3ede2",
    },
    "dark_css_variables": {
        "color-brand-primary": "#68d8c3",
        "color-brand-content": "#68d8c3",
        "color-foreground-primary": "#e5eefc",
        "color-background-primary": "#111827",
        "color-background-secondary": "#142033",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/kjgb001/Plexa",
            "html": """
                <svg stroke="currentColor" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8z"></path>
                </svg>
            """,
            "class": "",
        }
    ],
}

copybutton_prompt_text = r">>> |\.\.\. |\$ |# "
copybutton_prompt_is_regexp = True

linkcheck_ignore = [
    r"http://localhost(?::\d+)?(?:/.*)?",
    r"https://(?:inference|login|plexa)\.example\.edu(?:/.*)?",
]
# TypeDoc pages contain only generated GitHub source links, which are noisy and
# rate-limited when checked one line anchor at a time.
linkcheck_exclude_documents = [r"generated/client_api/.*"]
