
all:
	#clang -I/usr/include/python3.10 -o udpcom.o -c test_harness/udpcom.c
	python setup.py build_ext --inplace


clean:
	python setup.py clean --all

debug: all
	gdb --args python3 test_udpcom_c.py
