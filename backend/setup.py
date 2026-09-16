from setuptools import setup

setup(
    name="codereview-agent-cli",
    version="1.0.0",
    py_modules=["codereview_cli"],
    install_requires=[
        "typer",
        "requests",
        "rich",
        "GitPython",
        "prompt_toolkit",
    ],
    entry_points={
        "console_scripts": [
            "codereview=codereview_cli:app",
        ],
    },
)