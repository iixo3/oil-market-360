from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    runtime_dir: Path
    db_path: Path
    public_dir: Path
    premium_dir: Path
    freight_dir: Path
    manual_dir: Path
    ibkr_enabled: bool
    ibkr_host: str
    ibkr_port: int
    ibkr_ports: tuple[int, ...]
    ibkr_client_id: int
    ibkr_timeout_seconds: float

    @classmethod
    def from_env(cls, root_dir: Path) -> "AppConfig":
        runtime_dir = root_dir / "runtime"
        manual_override = os.getenv("OIL360_CSV_IMPORT_DIR", "").strip()
        manual_dir = Path(manual_override) if manual_override else runtime_dir / "imports" / "manual"
        configured_port = int(os.getenv("OIL360_IBKR_PORT", "7497"))
        configured_ports = os.getenv("OIL360_IBKR_PORTS", "").strip()
        parsed_ports = tuple(
            int(part.strip())
            for part in configured_ports.split(",")
            if part.strip()
        )
        if not parsed_ports:
            parsed_ports = tuple(dict.fromkeys([configured_port, 7497, 4002, 7496, 4001]))
        return cls(
            root_dir=root_dir,
            runtime_dir=runtime_dir,
            db_path=runtime_dir / "oil360_history.sqlite",
            public_dir=runtime_dir / "imports" / "public",
            premium_dir=runtime_dir / "imports" / "premium",
            freight_dir=runtime_dir / "imports" / "freight",
            manual_dir=manual_dir,
            ibkr_enabled=os.getenv("OIL360_ENABLE_IBKR", "0") == "1",
            ibkr_host=os.getenv("OIL360_IBKR_HOST", "127.0.0.1"),
            ibkr_port=configured_port,
            ibkr_ports=parsed_ports,
            ibkr_client_id=int(os.getenv("OIL360_IBKR_CLIENT_ID", "19")),
            ibkr_timeout_seconds=float(os.getenv("OIL360_IBKR_TIMEOUT_SECONDS", "4.0")),
        )

    def ensure_runtime_dirs(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.premium_dir.mkdir(parents=True, exist_ok=True)
        self.freight_dir.mkdir(parents=True, exist_ok=True)
        self.manual_dir.mkdir(parents=True, exist_ok=True)
