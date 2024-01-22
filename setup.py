from setuptools import setup


setup(
    name="simplestmaps",
    version="1.4.0",
    description="Super simple on-liner maps in python.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Juan Pedro Fisanotti",
    author_email="fisadev@gmail.com",
    url="http://github.com/fisadev/simplestmaps",
    py_modules=["simplestmaps"],
    license="MIT",
    install_requires=["folium>=0.14.0"],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
)
