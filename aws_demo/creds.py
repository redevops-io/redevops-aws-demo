"""Vault → STS role-assumption for the ReDevOps AWS demo.

Security boundary = role assumption, not long-lived keys. A single *bootstrap* key
(read from Vault) is used ONLY to `sts:AssumeRole` into a least-privilege role per task:

    deployer  → Terraform / EKS / ECR provisioning
    agent     → AgentCore / Bedrock / runtime tool access
    readonly  → monitoring · Cost Explorer · CloudWatch · Inspector · Config · Macie reads

HARD RULE: key material (bootstrap secret, assumed-role secret/token) is NEVER logged,
printed, or placed in a repr/str. Tests assert this.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Literal, Optional, Tuple

import boto3

Role = Literal["deployer", "agent", "readonly"]

# config keys in secret/redevops/aws-demo/config that hold each role's ARN
_ARN_KEY: Dict[Role, str] = {
    "deployer": "deploy_role_arn",
    "agent": "agent_role_arn",
    "readonly": "readonly_role_arn",
}


def vault_cli_reader(path: str) -> Dict[str, str]:
    """Read a KV-v2 secret via the `vault` CLI (needs VAULT_ADDR + VAULT_TOKEN in env).

    Returns the inner `data.data` map. The value is never logged here; callers must
    keep it out of logs too.
    """
    out = subprocess.run(
        ["vault", "kv", "get", "-format=json", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)["data"]["data"]


@dataclass
class AwsDemoCreds:
    """Resolves short-lived, role-scoped ``boto3.Session`` objects for the demo account.

    Parameters
    ----------
    vault_reader:
        ``path -> {key: value}`` reader. Defaults to the ``vault`` CLI; inject a stub
        in tests so no real Vault (or key material on disk) is needed.
    session_ttl:
        Requested AssumeRole duration (seconds). Sessions are cached until ~2 min
        before expiry, then re-assumed.
    """

    vault_reader: Callable[[str], Dict[str, str]] = vault_cli_reader
    bootstrap_path: str = "secret/redevops/aws-demo/bootstrap"
    config_path: str = "secret/redevops/aws-demo/config"
    session_ttl: int = 3600

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    _cache: Dict[Role, Tuple[float, boto3.Session]] = field(default_factory=dict, repr=False, compare=False)
    _config: Optional[Dict[str, str]] = field(default=None, repr=False, compare=False)
    _boot: Optional[Dict[str, str]] = field(default=None, repr=False, compare=False)

    # ---- lazy Vault loads (secrets stay inside this object) ----
    def _load_config(self) -> Dict[str, str]:
        if self._config is None:
            self._config = self.vault_reader(self.config_path)
        return self._config

    def _load_bootstrap(self) -> Dict[str, str]:
        if self._boot is None:
            self._boot = self.vault_reader(self.bootstrap_path)
        return self._boot

    # ---- public config surface (non-secret) ----
    @property
    def region(self) -> str:
        return self._load_config()["region"]

    @property
    def account_id(self) -> str:
        return self._load_config()["account_id"]

    def role_arn(self, role: Role) -> str:
        return self._load_config()[_ARN_KEY[role]]

    # ---- the one operation that matters ----
    def session(self, role: Role) -> boto3.Session:
        """Return a ``boto3.Session`` scoped to *role*, assumed via STS from the bootstrap key.

        Cached per-role until near expiry. Raises ``KeyError`` for an unknown role.
        """
        if role not in _ARN_KEY:
            raise KeyError(f"unknown role {role!r}; expected one of {list(_ARN_KEY)}")
        with self._lock:
            cached = self._cache.get(role)
            if cached and cached[0] > time.time() + 120:
                return cached[1]

            cfg = self._load_config()
            boot = self._load_bootstrap()
            sts = boto3.client(
                "sts",
                aws_access_key_id=boot["access_key_id"],
                aws_secret_access_key=boot["secret_access_key"],
                region_name=cfg["region"],
            )
            resp = sts.assume_role(
                RoleArn=cfg[_ARN_KEY[role]],
                RoleSessionName=f"redevops-demo-{role}",
                DurationSeconds=self.session_ttl,
            )
            creds = resp["Credentials"]
            session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=cfg["region"],
            )
            expiry = creds["Expiration"]
            expiry_ts = expiry.timestamp() if hasattr(expiry, "timestamp") else time.time() + self.session_ttl
            self._cache[role] = (expiry_ts, session)
            return session

    # ---- never leak key material ----
    def __repr__(self) -> str:
        acct = self._config.get("account_id", "?") if self._config else "unloaded"
        loaded = "loaded" if self._boot is not None else "lazy"
        return f"<AwsDemoCreds account={acct} roles={list(_ARN_KEY)} bootstrap=***redacted*** ({loaded})>"

    __str__ = __repr__
