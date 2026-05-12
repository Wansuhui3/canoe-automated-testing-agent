from setuptools import setup, find_packages

setup(
    name="canoe-automated-testing-agent",
    version="1.0.0",
    author="Wansuhui3",
    author_email="",
    description="AI-driven automated testing agent for vehicle bus (CAN/LIN/FlexRay) scenarios with CANoe",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Wansuhui3/canoe-automated-testing-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires=">=3.10",
    install_requires=[
        "cantools>=39.4.0",
        "pyyaml>=6.0",
        "jinja2>=3.1.0",
        "networkx>=3.1",
        "rich>=13.0.0",
        "click>=8.1.0",
        "lxml>=4.9.0",
        "openpyxl>=3.1.0",
        "matplotlib>=3.7.0",
    ],
    entry_points={
        "console_scripts": [
            "canoe-agent=tools.batch_runner:main",
            "dbc-checker=tools.dbc_checker:main",
        ],
    },
)
