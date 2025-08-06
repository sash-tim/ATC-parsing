from setuptools import setup, find_packages

setup(
    name='ATC_parsing',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    author='sash-tim',
    description='Semantic parsing (NLTK CCG) of Air Traffic Control (ATC) communications',
    classifiers=['Programmimg Language :: Python :: 3',],
)