release:
	rm dist/ build/ -rf
	python setup.py sdist
	twine upload dist/*

build_docs:
	(cd docs && jupyter nbconvert --to html --execute demo_and_docs.ipynb --output index.html)

test:
	echo "TODO tests"
