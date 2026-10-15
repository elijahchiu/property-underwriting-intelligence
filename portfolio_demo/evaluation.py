"""Command-line entry point for the fictional property-level scope holdout."""

import json

from .engine import evaluate_synthetic_scope_holdouts


def main():
    print(json.dumps(evaluate_synthetic_scope_holdouts(), indent=2))


if __name__ == "__main__":
    main()
