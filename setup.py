from setuptools import setup
from setuptools import find_packages

setup(
    name="gc-log-analyzer",
    version="0.0.1",
    description="A tool to analyze JVM GC and safepoint logs",
    url="http://blanco.io",
    author="Zac Blanco",
    author_email="zacdblanco@gmail.com",
    install_requires=["numpy", "matplotlib"],
    packages=find_packages(include=['gc_log_analyzer']),
    entry_points={
    'console_scripts': [
        'gc-log-analyzer=gc_log_analyzer:main',
    ],
},
)