import pytest

from punctual import main


def test_main_prints(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    assert "punctual" in capsys.readouterr().out
