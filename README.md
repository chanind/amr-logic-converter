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

In ["Expressive Power of Abstract Meaning Representations"](http://www.mitpressjournals.org/doi/pdf/10.1162/COLI_a_00257), all instances are wrapped by an existence quantifier. By default `AmrLogicConverter` does not include these as it's likely not useful, but if you'd like to include them as in the paper you can pass the option `existentially_quantify_instances=True` when constructing the `AmrLogicConverter` as below:

```python
converter = AmrLogicConverter(existentially_quantify_instances=True)

AMR = """
(x / boy
    :ARG0-of (e / giggle-01
        :polarity -))
"""

logic = converter.convert(AMR)
print(logic)
# ∃X(boy(X) ^ ¬∃E(:ARG0(E, X) ^ giggle-01(E)))
```

### Coreference Hoisting

When an instance is coreferenced in multiple places in the AMR, it's necessary to hoisting the existential quantification of that variable high enough that it can still wrap all instances of that variable. By default, the existential quantifier will be hoisted to the level of the lowest common ancestor of all nodes in the AMR tree where an instance is coreferenced. However, in ["Expressive Power of Abstract Meaning Representations"](http://www.mitpressjournals.org/doi/pdf/10.1162/COLI_a_00257), these coreferences are instead hoisted to the maximal possible scope, wrapping the entire formula. If you want this behavior, you can specify the option `maximally_hoist_coreferences=True` when creating the `AmrLogicConverter` instance. This is illustrated below:

```python
AMR = """
(b / bad-07
    :polarity -
    :ARG1 (e / dry-01
        :ARG0 (x / person
            :named "Mr Krupp")
        :ARG1 x))
"""

# default behavior, hoist only to the lowest common ancestor
converter = AmrLogicConverter(
    existentially_quantify_instances=True,
)
logic = converter.convert(AMR)
print(logic)
# ¬∃B(bad-07(B) ∧ ∃E(∃X(:ARG1(B, E) ∧ person(X) ∧ :named(X, "Mr Krupp") ∧ dry-01(E) ∧ :ARG0(E, X) ∧ :ARG1(E, X))))

# maximally hoist coferences
converter = AmrLogicConverter(
    existentially_quantify_instances=True,
    maximally_hoist_coreferences=True,
)
logic = converter.convert(AMR)
print(logic)
# ∃X(¬∃B(bad-07(B) ∧ ∃E(:ARG1(B, E) ∧ dry-01(E) ∧ :ARG0(E, X) ∧ :ARG1(E, X))) ∧ person(X) ∧ :named(X, "Mr Krupp"))
```

### Using Variables for Instances

If you want to use variables for each AMR instance instead of constants, you can pass the option `use_variables_for_instances=True` when creating the AmrLogicConverter instance. When `existentially_quantify_instances` is set, variable will always be used for instances regardless of this setting.

## Misc Options

- By default variables names are capitalized, but you can change this by setting `capitalize_variables=False`.
- By default, relations like `:ARG0-of(X, Y)` have their arguments flipped in logic and turned into `:ARG0(Y, X)`. If you don't want this normalization to occur, you can disable this by setting `invert_relations=False`.

## Contributing

Contributions are welcome! Please leave an issue in the Github repo if you find any bugs, and open a pull request with and fixes or improvements that you'd like to contribute. Ideally please include new test cases to verify any changes or bugfixes if appropriate.

This project uses [poetry](https://python-poetry.org/) for dependency management and packaging, [black](https://black.readthedocs.io/en/stable/) for code formatting, [flake8](https://flake8.pycqa.org/en/latest/) for linting, and [mypy](https://mypy.readthedocs.io/en/stable/) for type checking.

## License

This project is licenced under a MIT license.
