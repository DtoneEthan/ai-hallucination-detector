from setuptools import setup, find_packages

setup(
    name="ai-hallucination-detector",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.20",
        "beautifulsoup4>=4.9",
    ],
    entry_points={
        "console_scripts": [
            "hallucination-detector=hallucination_detector.cli:main",
        ],
    },
)
