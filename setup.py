from setuptools import setup, find_packages

setup(
    name="theus",
    version="2.1.0",
    description="Theus Agentic Framework - Industrial Grade Process-Oriented Programming (POP)",
    long_description=open("README.md", encoding="utf-8").read() if open("README.md", encoding="utf-8") else "",
    long_description_content_type="text/markdown",
    author="Do Huy Hoang",
    author_email="dohuyhoangvn93@gmail.com",
    url="https://github.com/dohuyhoang93/theus", 
    keywords=["ai", "agent", "pop", "process-oriented", "transactional", "state-management", "theus", "framework", "microkernel"],
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    install_requires=[
        "pydantic>=2.0",
        "pyyaml>=6.0",
        "typing-extensions>=4.0"
    ],
    entry_points={
        'console_scripts': [
            'theus = theus.cli:main', # Primary command
        ],
    },
    python_requires=">=3.8",
    project_urls={
        "Source": "https://github.com/dohuyhoang93/theus",
        "Bug Tracker": "https://github.com/dohuyhoang93/theus/issues",
    },
)
