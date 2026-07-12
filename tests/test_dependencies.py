import sys


def test_project_uses_python_312_and_runtime_dependencies_import():
    assert sys.version_info[:2] == (3, 12)

    import fastapi  # noqa: F401
    import hypothesis  # noqa: F401
    import openai  # noqa: F401
    import PIL  # noqa: F401
    import pydantic  # noqa: F401
    import pytest  # noqa: F401
    import sentence_transformers  # noqa: F401
    import streamlit  # noqa: F401
