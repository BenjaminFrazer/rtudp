from setuptools import setup, Extension

udpcom = Extension(
    name="udpcom.udpcom",  # <- matches your import path!
    sources=["udpcom/udpcom.c"],
    extra_compile_args=["-g", "-O0"],
    extra_link_args=["-g"],
)

setup(
    name="udpcom",
    version="0.0.1",
    packages=["udpcom"],
    ext_modules=[udpcom],
)
