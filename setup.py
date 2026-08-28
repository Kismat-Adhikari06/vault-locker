from setuptools import setup, find_packages

setup(
    name="vaultlock",
    version="0.1.0",
    description="A lightweight folder locking application for Linux",
    author="VaultLock",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "bcrypt>=4.0.0",
    ],
    entry_points={
        "console_scripts": [
            "vaultlock=vaultlock.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Security",
    ],
)
