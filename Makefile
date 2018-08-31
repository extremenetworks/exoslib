.PHONY:	lst tarball all

all:	lst tarball
	
lst:
	tar -czf exoslib.lst exoslib.py

tarball:
	tar -czf exoslib.tar.gz *

clean:
	rm -f *.lst *.tar.gz

