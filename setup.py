from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name             = "digitalsoma",
    version          = "2.0.0",
    description      = "A physics-based digital twin framework for real-time animal physiology monitoring",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    author           = "Dr. ir. Ali Youssef",
    author_email     = "info@biotwinr.ca",
    url              = "https://github.com/BioTwinR/digitalsoma",
    licence          = "CC BY 4.0",
    python_requires  = ">=3.9",
    packages         = find_packages(exclude=["tests*", "examples*"]),
    install_requires = [],          # zero runtime dependencies
    extras_require   = {
        "yaml": ["PyYAML>=6.0"],
        "llm":  ["anthropic>=0.20"],
        "dev":  ["pytest>=7.0", "PyYAML>=6.0"],
    },
    classifiers = [
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
    ],
    keywords = [
        "digital twin", "animal physiology", "veterinary informatics",
        "pharmacovigilance", "VeDDRA", "livestock", "precision agriculture",
        "computational bio-ecosystems", "ontology", "sensor fusion",
    ],
    project_urls = {
        "Documentation": "https://github.com/BioTwinR/digitalsoma/tree/main/docs",
        "Source":        "https://github.com/BioTwinR/digitalsoma",
        "ORCID":         "https://orcid.org/0000-0002-9986-5324",
    },
)
