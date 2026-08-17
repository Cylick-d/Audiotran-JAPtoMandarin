def test_package_imports():
    import audiotran

    assert audiotran.__version__


def test_create_application_returns_qapplication():
    from PySide6.QtWidgets import QApplication

    from audiotran.app import create_application

    app = create_application(["audiotran-test"])

    assert isinstance(app, QApplication)
    assert QApplication.instance() is app
