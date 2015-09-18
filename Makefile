#!/usr/bin/make -f
# -*- makefile -*-
#

# SHELL = sh -e

scrape:

	@virtualenv/bin/python scrape.py

environment:

	@virtualenv virtualenv
	@virtualenv/bin/pip install pdfminer lxml
