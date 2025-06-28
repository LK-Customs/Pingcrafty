#!/usr/bin/env python3
"""
Setup script for PingCrafty v0.2
"""

from setuptools import setup, find_packages
import os
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "A high-performance, modular Minecraft server scanner"

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, "r", encoding="utf-8") as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith("#")
        ]
else:
    requirements = [
        "asyncio-throttle>=1.0.2",
        "aiofiles>=23.1.0",
        "aiosqlite>=0.19.0",
        "pyyaml>=6.0.1",
        "aiohttp>=3.8.5",
        "rich>=13.4.2",
        "psutil>=5.9.5",
    ]

# Optional dependencies
extras_require = {
    "postgresql": ["asyncpg>=0.28.0"],
    "geolocation": ["geoip2>=4.7.0", "maxminddb>=2.2.0", "ipwhois>=1.2.0"],
    "export": ["openpyxl>=3.1.2", "pandas>=2.0.3"],
    "dev": [
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.1",
        "black>=23.7.0",
        "flake8>=6.0.0",
        "mypy>=1.5.0",
    ],
    "docs": [
        "sphinx>=7.1.0",
        "sphinx-rtd-theme>=1.3.0",
    ],
}

# All optional dependencies
extras_require["all"] = [
    dep for deps in extras_require.values() for dep in deps
]

setup(
    name="pingcrafty",
    version="0.2.0",
    author="PingCrafty Team",
    author_email="contact@pingcrafty.dev",
    description="A high-performance, modular Minecraft server scanner",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/pingcrafty-v2",
    project_urls={
        "Bug Reports": "https://github.com/your-org/pingcrafty-v2/issues",
        "Source": "https://github.com/your-org/pingcrafty-v2",
        "Documentation": "https://pingcrafty.readthedocs.io/",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet",
        "Topic :: System :: Networking",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "pingcrafty=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["config.yaml", "*.yml", "*.yaml"],
    },
    zip_safe=False,
    keywords=[
        "minecraft",
        "scanner",
        "server",
        "network",
        "async",
        "modular",
        "gaming",
        "protocol",
    ],
) 