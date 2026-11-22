import importlib.util
from pathlib import Path
import pytest


def test_wikisql_default_refuses_missing_files_without_loading_credentials(tmp_path, monkeypatch, capsys):
    from scripts import evaluate_wikisql as cli
    monkeypatch.setattr(cli, "Settings", lambda: pytest.fail("Offline mode read credentials"))
    monkeypatch.setattr("sys.argv", ["evaluate_wikisql.py", "--data-dir", str(tmp_path), "--output", str(tmp_path / "report.json")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "--download" in capsys.readouterr().err


def test_wikisql_input_checksum_mismatch_is_refused(tmp_path):
    from scripts.evaluate_wikisql import load_data
    (tmp_path / "corpus.parquet").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        load_data(tmp_path)


def test_live_cli_announces_full_corpus_call_estimate_before_evaluation(tmp_path, monkeypatch, capsys):
    from scripts import evaluate_wikisql as cli
    from types import SimpleNamespace
    monkeypatch.setattr(cli, 'load_data', lambda *args: (
        {str(i): 'SELECT x' for i in range(65)}, {'q': 'x'}, {'q': {'0': 1}}))
    monkeypatch.setattr(cli, 'Settings', lambda: SimpleNamespace(validate_embeddings=lambda: None))
    monkeypatch.setattr(cli, 'embeddings_for', lambda config: object())
    def evaluate(*args, **kwargs):
        assert '4 embedding calls' in capsys.readouterr().err
        return {'evaluated_queries': 1, 'subset': False, 'modes': {'vector': {'status': 'tested'}}}
    monkeypatch.setattr(cli, 'evaluate_external', evaluate)
    monkeypatch.setattr('sys.argv', ['evaluate_wikisql.py', '--data-dir', str(tmp_path),
        '--output', str(tmp_path / 'out.json'), '--limit', '1', '--live'])
    cli.main()
