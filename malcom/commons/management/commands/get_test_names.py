"""Command to get test names for CircleCI test parallelization."""

import re
from importlib import import_module
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from django.test.utils import get_runner


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--exclude-tags",
            nargs="*",
            default=[],
        )
        # output file
        parser.add_argument(
            "-o",
            "--output",
            type=str,
            default="test_names.txt",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003  # noqa: C901, PLR0912, PLR0915, PLR0911
        exclude_tags = options.get("exclude_tags")
        test_suite = get_runner(settings)(exclude_tags=exclude_tags).build_suite()
        tagged_tests = []

        project_name = Path(__file__).resolve().parent.parent.parent.parent.name
        for test in list(test_suite):
            test_class_str = str(test.__class__)

            # extract the full class name from the test_class_str
            # the pattern is like "<class 'project_name.tests.test_foo.TestFoo'>"
            # -> "project_name.tests.test_foo.TestFoo"
            extract_pattern = "(?<=')(.*?)(?=')"
            class_string_search_result = re.search(extract_pattern, test_class_str)
            if class_string_search_result:
                class_path_str = class_string_search_result.group(0)
                if not class_path_str.startswith(project_name):
                    try:
                        import_from = ".".join(class_path_str.split(".")[:-1])
                        import_name = class_path_str.split(".")[-1]
                        import_module(import_from, import_name)
                    except ModuleNotFoundError:
                        self.stdout.write(f"[IMPORT ERROR] {class_path_str}, {import_from}, {import_name}")
                        continue

                if "tests" not in class_path_str:
                    self.stdout.write(f"[WARN] 'tests' not in {class_path_str}")

                tagged_tests.append(class_path_str)

        assert len(tagged_tests) > 0, "No tests found."  # noqa: PLR2004
        # remove duplicates
        tagged_tests = sorted(set(tagged_tests))
        self.stdout.write(f"Found {len(tagged_tests)} classes.")

        if options.get("output"):
            output_path = Path(options.get("output"))
            with output_path.open("w") as f:
                for test in tagged_tests:
                    f.write(f"{test}\n")
