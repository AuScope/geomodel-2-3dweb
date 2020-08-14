## How to generate documentation

The documentation is published in https://auscope.github.io/geomodel-2-3dweb/ but to generate it yourself this is what to do.


"sphinx" (at least v1.6.7) is used to generate documentation for this project (http://www.sphinx-doc.org/en/master/index.html)


From the 'doc_src' directory, to generate .rst files for each of the .py source files:

`sphinx-apidoc -f -o source ../scripts/lib`


* To generate html documentation:

`make html`


* To remove html documentation:

`make clean`


* To copy to 'docs' directory for publishing in github pages:

`cp -r build/html/* ../docs`
