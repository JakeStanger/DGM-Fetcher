from setuptools import setup

setup(
    name='DGM-Bot',
    version='1.0.0',
    packages=['dgm_bot'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['sqlalchemy', 'requests', 'beautifulsoup4', 'discord.py', 'elasticsearch'],
    url='https://github.com/JakeStanger/DGM-Fetcher',
    license='MIT',
    author='Jake Stanger',
    author_email='mail@jstanger.dev',
    description='Python scripts for scraping DGM Live tour pages and accompanying discord bot ',
    scripts=['bin/dgm-bot']
)