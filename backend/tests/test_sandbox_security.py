import os
from unittest.mock import patch
from agents.sandbox_security import docker_security_args


def test_includes_expected_hardening_flags():
    args = docker_security_args()
    assert "--read-only" in args
    assert "--cap-drop" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert "--pids-limit" in args
    assert "--cpus" in args
    assert "--security-opt" in args
    assert args[args.index("--security-opt") + 1] == "no-new-privileges"
    assert "--tmpfs" in args
    assert args[args.index("--tmpfs") + 1].startswith("/tmp:")


def test_cpus_and_pids_limit_are_env_configurable():
    with patch.dict(os.environ, {"SANDBOX_CPUS": "4", "SANDBOX_PIDS_LIMIT": "64"}):
        import importlib
        import agents.sandbox_security as mod
        importlib.reload(mod)
        args = mod.docker_security_args()
        assert args[args.index("--cpus") + 1] == "4"
        assert args[args.index("--pids-limit") + 1] == "64"
    importlib.reload(mod)  # restore defaults for other tests
