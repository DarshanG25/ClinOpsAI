from pathlib import Path

from app.config.settings import BACKEND_ROOT, Settings


def test_env_file_paths_are_absolute_and_cover_repo_and_backend():
    env_files = tuple(Path(path) for path in Settings.model_config["env_file"])

    assert env_files == (BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env")
    assert all(path.is_absolute() for path in env_files)


def test_hf_token_accepts_mixed_case_env_name(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HF_token=test-token\n", encoding="utf-8")

    configured = Settings(_env_file=env_file)

    assert configured.hf_token == "test-token"