from setuptools import setup, Extension

rtudp = Extension(
    name="rtudp.rtudp",  # <- matches your import path!
    sources=["rtudp/rtudp.c"],
    extra_compile_args=["-g", "-O0"],
    extra_link_args=["-g"],
)

setup(
    name="rtudp",
    version="0.0.1",
    packages=["rtudp"],
    ext_modules=[rtudp],
)
