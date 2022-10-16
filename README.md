# AMR Logic Converter

[![ci](https://img.shields.io/github/workflow/status/chanind/amr-logic-converter/CI/main)](https://github.com/chanind/amr-logic-converter)
[![Codecov](https://img.shields.io/codecov/c/github/chanind/amr-logic-converter/main)](https://codecov.io/gh/chanind/amr-logic-converter)
[![PyPI](https://img.shields.io/pypi/v/amr-logic-converter?color=blue)](https://pypi.org/project/amr-logic-converter/)

Convert Abstract Meaning Representation (AMR) to first-order logic statements.

This library is based on the ideas in the paper ["Expressive Power of Abstract Meaning Representations", J. Bos, Computational Linguistics 42(3), 2016](http://www.mitpressjournals.org/doi/pdf/10.1162/COLI_a_00257). Thank you to [@jobos](https://github.com/jobos) for the paper!

## Installation

```
pip install amr-logic-converter
```

## Usage

This library parses an AMR tree into first-order logic statements. An example of this is shown below:

```python
from amr_logic_converter import AmrLogicConverter

converter = AmrLogicConverter()

AMR = """
(x / boy
    :ARG0-of (e / giggle-01
        :polarity -))
"""

logic = converter.convert(AMR)
print(logic)
# boy(x) ^ ¬(:ARG0(e, x) ^ giggle-01(e))
```

### Programmatic logic manipulation

The output from the `convert` method can be displayed as a string, but it can also be manipulated in Python. For instance, in the example above, we could also write:

```python
converter = AmrLogicConverter()

AMR = """
(x / boy
    :ARG0-of (e / giggle-01
        :polarity -))
"""

expr = converter.convert(AMR)
type(expr) # <class 'amr_logic_converter.types.And'>
logic.args[0] # Predicate(value='boy', args=(Const(name='x', type='instance'),), alignment=None)
```

### Working with alignment markers

This library will parse alignment markers from AMR using the [penman library](https://penman.readthedocs.io/en/latest/), and will include [Alignment](https://penman.readthedocs.io/en/latest/api/penman.surface.html#penman.surface.Alignment) objects from penman in `Predicate` and `Const` objects when available. For example, we can access alignment markers like below:

```python
converter = AmrLogicConverter()

AMR = """
(x / boy~1
    :ARG0-of (e / giggle-01~3
        :polarity -))
"""

expr = converter.convert(AMR)
expr.args[0].alignment # Alignment((1,))
expr.args[1].body.args[1].alignment # Alignment((3,))
```

### Existentially Quantifying all Instances

In ["Expressive Power of Abstract Meaning Representations"](http://www.mitpressjournals.org/doi/pdf/10.1162/COLI_a_00257), all instances are wrapped by an existence quantifier. By default AmrLogicConverter does not include these as it's likely not useful, but if you'd like to include them as in the paper you can pass the option `

## Contributing

Contributions are welcome! Please leave an issue in the Github repo if you find any bugs, and open a pull request with and fixes or improvements that you'd like to contribute. Ideally please include new test cases to verify any changes or bugfixes if appropriate.

This project uses [poetry](https://python-poetry.org/) for dependency management and packaging, [black](https://black.readthedocs.io/en/stable/) for code formatting, [flake8](https://flake8.pycqa.org/en/latest/) for linting, and [mypy](https://mypy.readthedocs.io/en/stable/) for type checking.

## License

This project is licenced under a MIT license.
