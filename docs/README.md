I use the 'sphinx' (at least v1.6.7) documentation generation to generate documentation for this project (http://www.sphinx-doc.org/en/master/index.html)

From the 'docs' directory, to generate .rst files for each of the .py source files:

sphinx-apidoc -f -o source ../scripts


To generate html documentation:

make html

To remove html documentation:

make clean


