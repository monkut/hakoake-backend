# malcom README

Management tool for live house performances


## Local Development

Python: 3.13

> Requires [uv](https://docs.astral.sh/uv/guides/install-python/) for dependency management


### Install the local development environment

1. Setup `pre-commit` hooks (_ruff_):

    ```bash
    # assumes pre-commit is installed on system via: `pip install pre-commit`
    pre-commit install
    ```

2. The following command installs project and development dependencies:

    ```bash
    uv sync 
    ```

### Add new packages

From the project root directory run the following:
```
uv add {PACKAGE TO INSTALL}
```

 ## Run code checks

 To run linters:
 ```
 # runs flake8, pydocstyle
 uv run poe check
 ```

To run type checker:
```
uv run pyright
```

## Running tests

This project uses the standard django testsuite for running testcases.

Tests cases are written and placed in the `tests` directory of *each* app.

To run the tests use the following command:
```
python manage.py test
```

> Alternatively, from the parent directory you can run:

```
uv run poe test
```

## CI/CD Required Environment Variables

The following are required for this project to be integrated with auto-deploy using the `github flow` branching strategy.

> With `github flow` master is the *release* branch and features are added through Pull-Requests (PRs)
> On merge to master the code will be deployed to the production environment.

[[LIST REQUIRED ENVIRONMENT VARIABLES HERE]]
