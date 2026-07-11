"""Minimal setup.py for BigBase deployment.

BigBase runs `pip install --break-system-packages -r requirements.txt`
which resolves `grimoire-dashboard` dependency but can't install the
package itself without pyproject.toml or setup.py.
"""

from setuptools import find_packages, setup

setup(
    name="grimoire-dashboard",
    version="0.1.8",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "dataconfy>=0.0.3",
        "fastapi>=0.115",
        "uvicorn[standard]>=0.34",
        "jinja2>=3.1",
        "httpx>=0.28",
        "pyyaml>=6.0",
        "pydantic>=2.10",
        "sqlmodel>=0.0.22",
        "aiosqlite>=0.21",
        "apscheduler>=3.11,<4",
        "prometheus-client>=0.22",
        "opentelemetry-api>=1.30",
        "opentelemetry-sdk>=1.30",
        "opentelemetry-instrumentation-fastapi>=0.51b0",
        "python-multipart>=0.0.18",
    ],
)
