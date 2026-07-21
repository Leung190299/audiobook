import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.models import Script


def save_script(script: Script, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = output_dir / f"{script.trope}-{timestamp}.json"
    out_path.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
