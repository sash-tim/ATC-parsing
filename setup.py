from setuptools import setup, find_packages

setup(
    name='ATC_parsing',
    version='1.0.1',
    packages=find_packages(),
    include_package_data=True,
    author='vladimir dobrynin',
    author_email='atc.parsing@gmail.com',
    description='Semantic parsing (NLTK CCG) of Air Traffic Control (ATC) commands',
    classifiers=['Programmimg Language :: Python :: 3',],
)