import setuptools

with open("README.md") as handle:
    long_description = handle.read()

setuptools.setup(
    name='macos-media',
    version='1.0.1',
    author='Neil Walker',
    author_email='neil@wynded.co.uk',
    description='Access to the macOS media libraries',
    long_description=long_description,
    url='https://github.com/nsw42/macos-media',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: MacOS'
    ],
    python_requires='>=3.6',
)
