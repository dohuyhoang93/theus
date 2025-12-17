from setuptools import setup, find_packages

setup(
    name="theus",
    version="0.1.4",
    description="Theus Agentic Framework (formerly POP SDK) - Industrial Grade Process-Oriented Programming",
    long_description=open("README.md", encoding="utf-8").read() if open("README.md", encoding="utf-8") else "",
    long_description_content_type="text/markdown",
    author="Do Huy Hoang",
    author_email="dohuyhoangvn93@gmail.com",
    url="https://github.com/dohuyhoang93/theus", # Assuming DeepSearch or new repo
    keywords=["ai", "agent", "pop", "process-oriented", "transactional", "state-management", "theus"],
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    install_requires=[
        "pydantic>=2.0",
        "pyyaml>=6.0",
        "typing-extensions>=4.0"
    ],
    entry_points={
        'console_scripts': [
            'pop = theus.cli:main', # Keep 'pop' command or rename to 'theus'? Usually keep compatibility. 
            'theus = theus.cli:main', # Allow both?
        ],
    },
    python_requires=">=3.8",
    project_urls={
        "Source": "https://github.com/dohuyhoang93/theus", # Updated
        "Bug Tracker": "https://github.com/dohuyhoang93/theus/issues",
    },
)
