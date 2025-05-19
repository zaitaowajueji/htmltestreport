# -*- coding: utf-8 -*-
"""
用于UnitTest框架生成HTML格式的测试报告
"""

__author__ = "outman"
__version__ = "0.0.1"

import datetime
import sys
import io
from unittest import TestResult
from xml.sax import saxutils
from .template import Template


class OutputRedirector(object):
    """ Wrapper to redirect stdout or stderr """

    def __init__(self, fp):
        self.fp = fp

    def write(self, s):
        self.fp.write(s)

    def writelines(self, lines):
        self.fp.writelines(lines)

    def flush(self):
        self.fp.flush()


stdout_redirector = OutputRedirector(sys.stdout)
stderr_redirector = OutputRedirector(sys.stderr)


class _TestResult(TestResult):
    """测试结果"""
    def calculate_passrate(self):
        total_count = self.success_count + self.failure_count + self.error_count + self.skip_count
        if total_count > 0:
            self.passrate = (self.success_count / total_count) * 100
        else:
            self.passrate = 0
    def __init__(self):
        TestResult.__init__(self)
        self.stdout0 = None
        self.stderr0 = None
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
        self.skip_count = 0

        # result is a list of result in 4 tuple
        # (
        #   result code (0: success; 1: fail; 2: error),
        #   TestCase object,
        #   Test output (byte teststr),
        #   stack trace,
        # )
        self.result = []
        self.subtestlist = []
        self.passrate = float(0)

    def startTest(self, test):
        TestResult.startTest(self, test)
        # just one buffer for both stdout and stderr
        self.outputBuffer = io.StringIO()
        stdout_redirector.fp = self.outputBuffer
        stderr_redirector.fp = self.outputBuffer
        self.stdout0 = sys.stdout
        self.stderr0 = sys.stderr
        sys.stdout = stdout_redirector
        sys.stderr = stderr_redirector

    def complete_output(self):
        """
        Disconnect output redirection and return buffer.
        Safe to call multiple times.
        """
        if self.stdout0:
            sys.stdout = self.stdout0
            sys.stderr = self.stderr0
            self.stdout0 = None
            self.stderr0 = None
        return self.outputBuffer.getvalue()

    def stopTest(self, test):
        # Usually one of addSuccess, addError or addFailure would have been called.
        # But there are some path in unittest that would bypass this.
        # We must disconnect stdout in stopTest(), which is guaranteed to be called.
        self.complete_output()

    def addSuccess(self, test):
        if test not in self.subtestlist:
            self.success_count += 1
            TestResult.addSuccess(self, test)
            output = self.complete_output()
            self.result.append((0, test, output, ''))
            sys.stderr.write('ok ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')

    def addError(self, test, err):
        self.error_count += 1
        TestResult.addError(self, test, err)
        _, _exc_str = self.errors[-1]
        output = self.complete_output()
        self.result.append((2, test, output, _exc_str))
        sys.stderr.write('Error ')
        sys.stderr.write(str(test))
        sys.stderr.write('\n')

    def addFailure(self, test, err):
        self.failure_count += 1
        TestResult.addFailure(self, test, err)
        _, _exc_str = self.failures[-1]
        output = self.complete_output()
        self.result.append((1, test, output, _exc_str))
        sys.stderr.write('Failure ')
        sys.stderr.write(str(test))
        sys.stderr.write('\n')

    def addSkip(self, test, reason):
        self.skip_count += 1
        super().addSkip(test, reason)
        output = self.complete_output()
        self.result.append((3, test, output, ''))
        sys.stderr.write('Skip ')
        sys.stderr.write(str(test))
        sys.stderr.write('\n')

    def addSubTest(self, test, subtest, err):
        if err is not None:
            if getattr(self, 'failfast', False):
                self.stop()
            if issubclass(err[0], test.failureException):
                self.failure_count += 1
                errors = self.failures
                errors.append((subtest, self._exc_info_to_string(err, subtest)))
                output = self.complete_output()
                self.result.append((1, test, output + '\nSubTestCase Failed:\n' + str(subtest),
                                    self._exc_info_to_string(err, subtest)))
                sys.stderr.write('Failure ')
                sys.stderr.write(str(subtest))
                sys.stderr.write('\n')
            else:
                self.error_count += 1
                errors = self.errors
                errors.append((subtest, self._exc_info_to_string(err, subtest)))
                output = self.complete_output()
                self.result.append(
                    (2, test, output + '\nSubTestCase Error:\n' + str(subtest), self._exc_info_to_string(err, subtest)))
                sys.stderr.write('Error ')
                sys.stderr.write(str(subtest))
                sys.stderr.write('\n')
            self._mirrorOutput = True
        else:
            self.subtestlist.append(subtest)
            self.subtestlist.append(test)
            self.success_count += 1
            output = self.complete_output()
            self.result.append((0, test, output + '\nSubTestCase Pass:\n' + str(subtest), ''))
            sys.stderr.write('ok ')
            sys.stderr.write(str(subtest))
            sys.stderr.write('\n')


class HTMLTestReport(object):

    def __init__(self, file_path, title=None, description=None):
        self.file_path = file_path
        if title is None:
            self.title = Template.DEFAULT_TITLE
        else:
            self.title = title
        if description is None:
            self.description = Template.DEFAULT_DESCRIPTION
        else:
            self.description = description

        self.startTime = datetime.datetime.now()

    def run(self, test):
        "Run the given test case or test suite."
        result = _TestResult()
        test(result)
        self.stopTime = datetime.datetime.now()
        result.calculate_passrate()
        self.generateReport(test, result)
        file.write(f"通过率: {result.passrate}%\n")
        print('\nTime Elapsed: %s' % (self.stopTime - self.startTime), file=sys.stderr)
        return result

    def sortResult(self, result_list):
        # unittest does not seems to run in any particular order.
        # Here at least we want to group them together by class.
        rmap = {}
        classes = []
        for n, t, o, e in result_list:
            cls = t.__class__
            if cls not in rmap:
                rmap[cls] = []
                classes.append(cls)
            rmap[cls].append((n, t, o, e))
        r = [(cls, rmap[cls]) for cls in classes]
        return r

    def get_summary_data(self, result):
        """获取汇总数据"""
        startTime = str(self.startTime)[:19]
        duration = str(self.stopTime - self.startTime)
        total_count = result.success_count + result.failure_count + result.error_count + result.skip_count
        if total_count:
            self.passrate = str("%.2f" % (float(result.success_count) / float(total_count) * 100))

        return (startTime, duration, total_count, self.passrate, result.success_count, result.failure_count,
                result.error_count, result.skip_count)

    def generateReport(self, test, result):
        summary_data = self.get_summary_data(result)
        # report_attrs = self.getReportAttributes(result)
        generator = 'HTMLTestReport %s' % __version__
        stylesheet = self._generate_stylesheet()
        heading = self._generate_heading(summary_data)
        report = self._generate_report(result)
        ending = self._generate_ending()
        chart = self._generate_chart(result)
        output = Template.HTML_TMPL % dict(
            title=saxutils.escape(self.title),
            generator=generator,
            stylesheet=stylesheet,
            heading=heading,
            report=report,
            ending=ending,
            chart_script=chart
        )

        with open(self.file_path, 'wb') as f:
            f.write(output.encode('utf8'))
            def generateReport(self, test, result):
    # 已有代码...
    with open(self.file_path, 'wb') as f:
        f.write(f"通过率: {result.passrate}%\n".encode('utf8'))  # 添加这行展示通过率，注意编码
        f.write(output.encode('utf8'))
        

    def _generate_stylesheet(self):
        return Template.STYLESHEET_TMPL

    def _generate_heading(self, summary_data):
        start_time, duration, total_count, passrate, success_count, failure_count, error_count, skip_count = summary_data
        heading = Template.HEADING_TMPL % dict(
            title=saxutils.escape(self.title),
            description=saxutils.escape(self.description),
            start_time=start_time, duration=duration, total_count=total_count,
            passrate=passrate, success_count=success_count, failure_count=failure_count,
            error_count=error_count, skip_count=skip_count,
            parameters=''
        )
        return heading

    def _generate_report(self, result):
        rows = []
        sortedResult = self.sortResult(result.result)
        for cid, (cls, cls_results) in enumerate(sortedResult):
            # subtotal for a class
            np = nf = ne = ns = 0
            for n, t, o, e in cls_results:
                if n == 0:
                    np += 1
                elif n == 1:
                    nf += 1
                elif n == 3:
                    ns += 1
                else:
                    ne += 1

            # format class description
            if cls.__module__ == "__main__":
                name = cls.__name__
            else:
                name = "%s.%s" % (cls.__module__, cls.__name__)
            doc = cls.__doc__ and cls.__doc__.split("\n")[0] or ""
            desc = doc and '%s: %s' % (name, doc) or name

            row = Template.REPORT_CLASS_TMPL % dict(
                style=ne > 0 and 'errorClass' or nf > 0 and 'failClass' or 'passClass',
                desc=desc,
                count=np + nf + ne + ns,
                Pass=np,
                fail=nf,
                error=ne,
                skip=ns,
                cid='c%s' % (cid + 1),
            )
            rows.append(row)

            for tid, (n, t, o, e) in enumerate(cls_results):
                self._generate_report_test(rows, cid, tid, n, t, o, e)

        report = Template.REPORT_TMPL % dict(
            test_list=''.join(rows),
            count=str(result.success_count + result.failure_count + result.error_count + result.skip_count),
            Pass=str(result.success_count),
            notPass=str(result.failure_count + result.error_count),
            fail=str(result.failure_count),
            error=str(result.error_count),
            skip=str(result.skip_count),
            passrate=self.passrate,
        )
        return report

    def _generate_chart(self, result):
        chart = Template.ECHARTS_SCRIPT % dict(
            Pass=str(result.success_count),
            fail=str(result.failure_count),
            error=str(result.error_count),
            skip=str(result.skip_count),
            passrate=self.passrate
        )
        return chart

    def _generate_report_test(self, rows, cid, tid, n, t, o, e):
        # e.g. 'pt1.1', 'ft1.1', etc
        has_output = bool(o or e)
        tid = (n == 0 and 'p' or 'f') + 't%s.%s' % (cid + 1, tid + 1)
        name = t.id().split('.')[-1]
        doc = t.shortDescription() or ""
        desc = doc and ('%s: %s' % (name, doc)) or name
        tmpl = has_output and Template.REPORT_TEST_WITH_OUTPUT_TMPL or Template.REPORT_TEST_NO_OUTPUT_TMPL

        script = Template.REPORT_TEST_OUTPUT_TMPL % dict(
            id=tid,
            output=saxutils.escape(o + e),
        )

        row = tmpl % dict(
            tid=tid,
            Class=(n == 0 and 'hiddenRow' or ''),
            style=(n == 2 and 'errorCase' or (n == 1 and 'failCase' or (n == 3 and 'skipCase' or 'passCase'))),
            desc=desc,
            script=script,
            status=Template.STATUS[n],
        )
        rows.append(row)
        if not has_output:
            return

    def _generate_ending(self):
        return Template.ENDING_TMPL
