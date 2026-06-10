import re

import pytest

import core.storage as storage
from core.run_logger import RunLogger


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield


class TestRunLogger:
    def test_creates_logs_dir_and_file(self, tmp_path):
        logger = RunLogger()
        try:
            logs_dir = tmp_path / "logs"
            assert logs_dir.is_dir()
            assert logger.path.exists()
            assert logger.path.parent == logs_dir
            assert re.fullmatch(r"run-\d{8}-\d{6}\.log", logger.path.name)
        finally:
            logger.close()

    def test_write_records_level_and_step_format(self):
        logger = RunLogger()
        logger.write("info", "step3", "태그 클릭")
        logger.close()
        text = logger.path.read_text(encoding="utf-8")
        assert "[INFO]" in text
        assert "[step3]" in text
        assert "태그 클릭" in text
        # full line shape: [ISO] [LEVEL] [step_id] message
        line = text.strip().splitlines()[0]
        assert re.match(r"^\[\d{4}-\d{2}-\d{2}T", line)

    def test_multiple_writes_accumulate(self):
        logger = RunLogger()
        logger.write("info", "step1", "first")
        logger.write("error", "step2", "second")
        logger.write("info", "", "third")
        logger.close()
        lines = logger.path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        assert "[ERROR]" in lines[1]
        # empty step_id falls back to '-'
        assert "[-]" in lines[2]

    def test_readable_after_close(self):
        logger = RunLogger()
        logger.write("info", "step1", "hello")
        logger.close()
        assert "hello" in logger.path.read_text(encoding="utf-8")

    def test_write_after_close_is_noop(self):
        logger = RunLogger()
        logger.write("info", "step1", "before")
        logger.close()
        # must not raise and must not append
        logger.write("info", "step1", "after")
        text = logger.path.read_text(encoding="utf-8")
        assert "before" in text
        assert "after" not in text

    def test_close_is_idempotent(self):
        logger = RunLogger()
        logger.close()
        logger.close()  # must not raise
