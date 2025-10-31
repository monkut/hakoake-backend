from time import time
from unittest.runner import TextTestResult, TextTestRunner

import xmlrunner
from django.test.runner import DiscoverRunner
from xmlrunner.extra.djangotestrunner import XMLTestRunner as DjangoXMLTestRunner


class TimedTextTestResult(TextTestResult):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.clocks = {}
        self.elapsed = {}

    def startTest(self, test) -> None:  # noqa: ANN001, N802
        self.clocks[test] = time()  # テストケースの開始時間を記録
        super().startTest(test)
        if self.showAll:
            self.stream.write(self.getDescription(test))
            self.stream.write(" ... ")
            self.stream.flush()

    def addSuccess(self, test) -> None:  # noqa: ANN001, N802
        super().addSuccess(test)
        elapsed = time() - self.clocks[test]
        self.elapsed[test] = elapsed  # テストケースの経過時間を記録
        if self.dots:
            self.stream.write(".")
            self.stream.flush()


class TimedTextTestRunner(TextTestRunner):
    resultclass = TimedTextTestResult

    def run(self, test) -> TimedTextTestResult:  # noqa: ANN001
        result = super().run(test)
        if result.elapsed:
            self.stream.writeln("")
            #  テストケースがかかる時間を多い順に出力
            for test_result, elapsed in sorted(result.elapsed.items(), key=lambda x: x[1], reverse=True):
                self.stream.writeln(f"{elapsed:>8.3f}s:  {test_result}")
            self.stream.writeln("")
        return result


class TimedTestRunner(DiscoverRunner):
    test_runner = TimedTextTestRunner


class XMLTestRunnerForCI(DjangoXMLTestRunner):
    test_runner = xmlrunner.XMLTestRunner

    def run_suite(self, suite, **kwargs):  # noqa: ANN001
        runner_kwargs = self.get_test_runner_kwargs()
        # outsuffix='' にしないとテスト実行結果に実行時間のsuffixがついてしまって、
        # CircleCIの --split-by=timings が有効にならない
        runner = self.test_runner(outsuffix="", **runner_kwargs)
        results = runner.run(suite)
        if hasattr(runner_kwargs["output"], "close"):
            runner_kwargs["output"].close()
        return results
