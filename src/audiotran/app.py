from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication


def create_application(argv: list[str]) -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    application = QApplication.instance()
    if application is None:
        application = QApplication(list(argv))

    if not application.applicationName():
        application.setApplicationName("audiotran")

    return application


def main(argv: list[str] | None = None) -> int:
    create_application(list(sys.argv if argv is None else argv))
    return 0
