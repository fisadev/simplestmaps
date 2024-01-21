release:
	rm dist/ build/ -rf
	python setup.py sdist
	twine upload dist/*

test:
	echo "TODO tests"
