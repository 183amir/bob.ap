#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Andre Anjos <andre.anjos@idiap.ch>
# Thu 30 Jan 08:45:49 2014 CET

from setuptools import setup, find_packages, dist
dist.Distribution(dict(setup_requires=['bob.blitz', 'bob.core', 'bob.sp']))
from bob.blitz.extension import Extension, Library, build_ext

version = '2.0.0a0'

setup(

    name='bob.ap',
    version=version,
    description='Bindings for Bob\'s audio processing utilities',
    url='http://github.com/bioidiap/bob.ap',
    license='BSD',
    author='Andre Anjos',
    author_email='andre.anjos@idiap.ch',

    long_description=open('README.rst').read(),

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,

    install_requires=[
      'setuptools',
      'bob.blitz',
      'bob.core',
      'bob.sp',
      'scipy', # for testing
    ],

    namespace_packages=[
      "bob",
    ],

    ext_modules = [
      Extension("bob.ap.version",
        [
          "bob/ap/version.cpp",
        ],
        version = version,
        bob_packages = ['bob.core', 'bob.sp']
      ),

      Library("bob.ap.bob_ap",
        [
          "bob/ap/cpp/Energy.cpp",
          "bob/ap/cpp/FrameExtractor.cpp",
          "bob/ap/cpp/Spectrogram.cpp",
          "bob/ap/cpp/Ceps.cpp",
        ],
        version = version,
        bob_packages = ['bob.core', 'bob.sp']
      ),

      Extension("bob.ap._library",
        [
          "bob/ap/energy.cpp",
          "bob/ap/frame_extractor.cpp",
          "bob/ap/spectrogram.cpp",
          "bob/ap/ceps.cpp",
          "bob/ap/main.cpp",
          ],
        version = version,
        bob_packages = ['bob.core', 'bob.sp']
      ),
    ],

    cmdclass = {
      'build_ext': build_ext
    },

    classifiers = [
      'Development Status :: 3 - Alpha',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: BSD License',
      'Natural Language :: English',
      'Programming Language :: Python',
      'Programming Language :: Python :: 3',
      'Topic :: Software Development :: Libraries :: Python Modules',
    ],

  )
