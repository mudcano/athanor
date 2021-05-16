import os
import sys
from setuptools import setup, find_packages

os.chdir(os.path.dirname(os.path.realpath(__file__)))

VERSION_PATH = os.path.join("athanor", "VERSION.txt")
OS_WINDOWS = os.name == "nt"


def get_requirements():
    """
    To update the requirements for athanor, edit the requirements.txt file.
    """
    with open("requirements.txt", "r") as f:
        req_lines = f.readlines()
    reqs = []
    for line in req_lines:
        # Avoid adding comments.
        line = line.split("#")[0].strip()
        if line:
            reqs.append(line)
    return reqs


def get_version():
    """
    When updating the athanor package for release, remember to increment the
    version number in athanor/VERSION.txt
    """
    return open(VERSION_PATH).read().strip()


def package_data():
    """
    By default, the distribution tools ignore all non-python files.

    Make sure we get everything.
    """
    file_set = []
    for d in ("athanor", "athanor_portal", "athanor_server"):
        for root, dirs, files in os.walk(d):
            for f in files:
                if ".git" in f.split(os.path.normpath(os.path.join(root, f))):
                    # Prevent the repo from being added.
                    continue
                file_name = os.path.relpath(os.path.join(root, f), d)
                file_set.append(file_name)
    return file_set

def get_scripts():
    """
    Determine which executable scripts should be added. For Windows,
    this means creating a .bat file.
    """
    if OS_WINDOWS:
        batpath = os.path.join("bin", "windows", "athanor.bat")
        scriptpath = os.path.join(sys.prefix, "Scripts", "athanor_launcher.py")
        with open(batpath, "w") as batfile:
            batfile.write('@"%s" "%s" %%*' % (sys.executable, scriptpath))
        return [batpath, os.path.join("bin", "windows", "athanor_launcher.py")]
    else:
        return [os.path.join("bin", "unix", "athanor")]

# setup the package
setup(
    name="athanor",
    version=get_version(),
    author="Volund",
    maintainer="Volund",
    url="https://github.com/volundmush/athanor",
    description="",
    license="???",
    long_description="""
    
    """,
    long_description_content_type="text/markdown",
    packages=find_packages(),
   # install_requires=get_requirements(),
    package_data={"": package_data()},
    zip_safe=False,
    scripts=get_scripts(),
    classifiers=[

    ],
    python_requires=">=3.7",
    project_urls={
        "Source": "https://github.com/volundmush/athanor",
        "Issue tracker": "https://github.com/volundmush/athanor/issues",
        "Patreon": "https://www.patreon.com/volund",
    },
)
