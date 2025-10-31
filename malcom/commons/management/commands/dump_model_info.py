import inspect
import sys
from pathlib import Path
from typing import IO

from django.conf import settings
from django.core import management
from django.core.management import BaseCommand, CommandParser
from django.db import models

EXCLUDE_APPS_STARTSWITH = (
    "django.",
    "rangefilter",
    "django_extensions",
)
VALID_APPLICATIONS: list[str] = [app for app in settings.INSTALLED_APPS if not app.startswith(EXCLUDE_APPS_STARTSWITH)]


DEFAULT_OUTPUT_DIRECTORY = settings.BASE_DIR / "dump-model-result"


def filepath(v: str) -> Path:
    return Path(v)


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("-e", action="store_true", help="ER図を出力する場合はこのオプションを使用してください")
        parser.add_argument(
            "-a", "--apps", required=True, nargs="+", help="ER図を出力するアプリケーション名を入力してください"
        )
        parser.add_argument(
            "-o",
            "--output-directory",
            type=filepath,
            default=DEFAULT_OUTPUT_DIRECTORY,
            help=f"出力するDIRECTORY(default={DEFAULT_OUTPUT_DIRECTORY})",
        )

    def output_model_info(self, model: models.Model, f: IO[str]) -> None:
        f.write(f"{model.__name__} ({model._meta.verbose_name}) マスター\n")
        f.write(
            "--------------------------------------------------------------------------------------------------------------------\n"  # noqa: E501
        )
        f.write("\n")
        f.write(f":テーブル名: {model._meta.db_table}\n")
        f.write(f":モデル名: {model._meta.verbose_name}\n")
        constraints = None
        if model._meta.constraints:
            constraints = ",".join(str(c) for c in model._meta.constraints)
        f.write(f":テーブル制約: {constraints}\n")
        f.write("\n")
        f.write(".. list-table::\n")
        f.write("    :header-rows: 1\n")
        f.write("    :class: ssp-tiny\n")
        f.write("\n")
        f.write("    * - フィールド名\n")
        f.write("      - 列型\n")
        f.write("      - 詳細名\n")
        f.write("      - 値制限\n")
        f.write("      - 説明\n")

        for field in model._meta.fields:
            f.write("\n")
            f.write(f"    * - {field.name}\n")
            field_restrictions = ""
            internal_type = field.get_internal_type()
            internal_type_display = internal_type
            if internal_type == "ForeignKey":
                internal_type_display = (
                    f"{internal_type} {field.related_model._meta.db_table} {field.related_model._meta.verbose_name}"
                )
            elif internal_type == "CharField":
                max_length = field.max_length
                field_restrictions = f"(文字数) <= {max_length}"
                if field.choices:
                    db_values = "|".join(db_value for (db_value, display_value) in field.choices)
                    field_restrictions = field_restrictions + f", ({db_values})"

            f.write(f"      - {internal_type_display}\n")
            f.write(f"      - {field.verbose_name}\n")
            f.write(f"      - {field_restrictions}\n")
            f.write(f"      - {field.help_text}\n")
        f.write("\n")
        f.write("\n")

    def validate_inputted_applications(self, target_apps: list[str]) -> None:
        for app in target_apps:
            if app not in VALID_APPLICATIONS:
                self.stderr.write(f"入力されたアプリケーションは存在しません: {app}\n")
                sys.exit()

    def handle(self, *args, **options):  # noqa: ANN002, ANN003  # noqa: C901, PLR0912, PLR0915, PLR0911
        target_apps: list[str] = options["apps"]
        output_directory: Path = options["output_directory"]
        self.validate_inputted_applications(target_apps=target_apps)

        output_directory.mkdir(exist_ok=True)
        rst_output_directory = output_directory
        rst_output_directory.mkdir(exist_ok=True)
        er_output_directory = output_directory / "imgs"
        er_output_directory.mkdir(exist_ok=True)
        for app in target_apps:
            app_modules = app + ".models"
            output_table_def_filename = f"{app}-table-definition.rst"
            output_filepath = output_directory / output_table_def_filename
            self.stdout.write(f"creating {output_filepath} ...\n")
            with output_filepath.open(mode="w") as f:
                is_initial = True
                for name, obj in inspect.getmembers(sys.modules[app_modules]):
                    if is_initial:
                        # write header
                        f.write(f"\n.. _table-definition-{app}:\n\n")
                        f.write(
                            "====================================================================================================\n"  # noqa: E501
                        )
                        f.write(f"{app} 関連のテーブル定義\n")
                        f.write(
                            "====================================================================================================\n"  # noqa: E501
                        )
                        f.write("\n")
                        is_initial = False
                    # モデルクラス以外のものも取得されるため、ここで除外する
                    if not (inspect.isclass(obj) and issubclass(obj, models.Model)):
                        continue
                    # 抽象基底クラスは除外する
                    if obj._meta.abstract:
                        continue
                    # 関連するモデルで別のアプリで定義している
                    if not obj._meta.db_table.startswith(app):
                        continue
                    self.stdout.write(f"-- outputting model: {name}")
                    self.output_model_info(model=obj, f=f)
            self.stdout.write(f"creating {output_filepath} ... DONE\n")

            er_flag = options["e"]
            if er_flag:
                output_filename = f"{app}-model.png"
                output_filepath = er_output_directory / output_filename
                self.stdout.write(f"creating {output_filepath} ... \n")
                management.call_command(
                    "graph_models",
                    "--no-inheritance",
                    "--hide-relations-from-fields",
                    app,
                    output=str(output_filepath.resolve()),
                    exclude_models=["UserTimestampedModel", "TimestampedModel", "AbstractUser", "CustomUser"],
                )
                self.stdout.write(f"creating {output_filepath} ... DONE\n")
