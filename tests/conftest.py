"""Expose failing pytest reports as GitHub Actions annotations."""
import os


def pytest_runtest_logreport(report):
    if report.failed and os.environ.get("GITHUB_ACTIONS") == "true":
        # GitHub workflow commands require newlines, carriage returns, and percent
        # signs to be escaped so multiline tracebacks stay in one annotation.
        message = f"{report.nodeid}\n{report.longreprtext}"
        message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=pytest failure::{message}", flush=True)
