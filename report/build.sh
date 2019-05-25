#!/bin/sh

pdflatex main
bibtex main
pdflatex main
pdflatex main

echo
echo "Finished building the report."
