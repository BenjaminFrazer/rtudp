
all:
	#clang -I/usr/include/python3.10 -o rtudp.o -c rtudp/rtudp.c
	python setup.py build_ext --inplace


clean:
	python setup.py clean --all

debug: all
	gdb --args python3 test_rtudp.py
