"""Setup script for Zephy - Azure TFE Resources Toolkit."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Import version from package
exec(open("zephy/__version__.py").read())

setup(
    name="zephy",
    version=__version__,
    description="Compare Azure resources with Terraform Enterprise workspaces",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Henry Bravo",
    author_email="info@henrybravo.nl",
    python_requires=">=3.10",
    packages=find_packages(),
    package_data={
        "zephy": ["PRIMARY_RESOURCE_TYPES.json"],
    },
    include_package_data=True,
    install_requires=[
        "azure-identity>=1.15.0",
        "azure-mgmt-resource>=23.0.0",
        "requests>=2.31.0",
        "python-dateutil>=2.8.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.12.1",
            "mypy>=1.7.1",
            "flake8>=6.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "zephy=zephy.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
)