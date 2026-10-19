PYTHON ?= python3

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	$(PYTHON) -m codemind examples/slide_example.c

gui:
	$(PYTHON) -m codemind --gui

lab:
	$(MAKE) -C mini_compiler

test-lab: lab
	$(PYTHON) tests/lab_checks.py

.PHONY: test demo gui lab test-lab
