from setuptools import setup, Extension, find_packages
import sys

# Platform-specific compile args
extra_compile_args = ["-O2", "-Wall"]
extra_link_args = []

if sys.platform == "linux":
    extra_compile_args.extend(["-pthread", "-fPIC"])
    extra_link_args.append("-pthread")

rtudp = Extension(
    name="rtudp.rtudp",
    sources=["rtudp/rtudp.c"],
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
    define_macros=[('PY_SSIZE_T_CLEAN', None)],
)

setup(
    name="rtudp",
    version="0.1.0",
    packages=find_packages(),
    ext_modules=[rtudp],
    package_data={
        "rtudp": ["*.pyi"],
    },
    python_requires=">=3.7",
    zip_safe=False,
)
