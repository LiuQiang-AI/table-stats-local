from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


FIXED_HEADERS: List[Tuple[str, str]] = [
    ("loadDate", "装车日期"),
    ("loadPlace", "装车地"),
    ("vehicle", "车辆"),
    ("model", "产品型号"),
    ("loadNetWeight", "装车净重"),
    ("unloadDate", "卸车日期"),
    ("unloadPlace", "卸货地"),
    ("unloadTons", "卸车数（吨）"),
    ("freight", "运费"),
    ("settleTons", "结算吨数"),
    ("amount", "金额"),
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def parse_iso_date(s: Any) -> Optional[date]:
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except Exception:
        return default


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def default_config() -> Dict[str, Any]:
    return {
        "recentTableIds": [],
        "recentLimit": 12,
        "autosaveMs": 600,
        "initialRows": 31,
        "defaultVehicle": "蒙J87721",
        "defaultModel": "PAC",
        "loadPlaces": ["装车地A", "装车地B", "装车地C"],
        "unloadPlaces": ["卸货地A", "卸货地B", "卸货地C"],
        "updatedAt": now_iso(),
    }


def load_config(base_dir: Path) -> Dict[str, Any]:
    cfg_path = base_dir / "config.json"
    cfg = _read_json(cfg_path, default_config())
    if not isinstance(cfg, dict):
        cfg = default_config()
    base = default_config()
    for k, v in base.items():
        cfg.setdefault(k, v)
    if not isinstance(cfg.get("recentTableIds"), list):
        cfg["recentTableIds"] = []
    if not isinstance(cfg.get("loadPlaces"), list):
        cfg["loadPlaces"] = base["loadPlaces"]
    if not isinstance(cfg.get("unloadPlaces"), list):
        cfg["unloadPlaces"] = base["unloadPlaces"]
    return cfg


def save_config(base_dir: Path, cfg: Dict[str, Any]) -> None:
    cfg = dict(cfg)
    cfg["updatedAt"] = now_iso()
    _write_json_atomic(base_dir / "config.json", cfg)


def touch_recent(cfg: Dict[str, Any], table_id: str) -> Dict[str, Any]:
    cfg = dict(cfg)
    recents = [table_id] + [x for x in cfg.get("recentTableIds", []) if x != table_id]
    limit = int(cfg.get("recentLimit") or 12)
    cfg["recentTableIds"] = recents[: max(1, limit)]
    return cfg


def list_table_files(tables_dir: Path) -> List[Path]:
    tables_dir.mkdir(parents=True, exist_ok=True)
    return sorted(tables_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_table_by_id(tables_dir: Path, table_id: str) -> Optional[Dict[str, Any]]:
    path = tables_dir / f"{table_id}.json"
    data = _read_json(path, None)
    return data if isinstance(data, dict) else None


def save_table(tables_dir: Path, table: Dict[str, Any]) -> None:
    table_id = str(table.get("id") or "").strip()
    if not table_id:
        raise ValueError("table.id 不能为空")
    table = dict(table)
    table["updatedAt"] = now_iso()
    _write_json_atomic(tables_dir / f"{table_id}.json", table)


def delete_table(tables_dir: Path, table_id: str) -> None:
    p = tables_dir / f"{table_id}.json"
    if p.exists():
        p.unlink()


def to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        try:
            return Decimal(str(v))
        except Exception:
            return None
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def fmt_decimal(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def compute_amount(row: Dict[str, Any]) -> str:
    freight = to_decimal(row.get("freight"))
    settle = to_decimal(row.get("settleTons"))
    if freight is None or settle is None:
        return ""
    return fmt_decimal(freight * settle)


def ensure_row_defaults(cfg: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(row)
    if not str(r.get("vehicle") or "").strip():
        r["vehicle"] = str(cfg.get("defaultVehicle") or "")
    if not str(r.get("model") or "").strip():
        r["model"] = str(cfg.get("defaultModel") or "")
    return r


def ensure_rows_from_start_date(cfg: Dict[str, Any], start_date_iso: str, row_count: int) -> List[Dict[str, Any]]:
    start_d = parse_iso_date(start_date_iso) or date.today()
    rows: List[Dict[str, Any]] = []
    for i in range(max(1, int(row_count))):
        d = start_d + timedelta(days=i)
        rows.append(
            ensure_row_defaults(
                cfg,
                {
                    "id": _new_id("row"),
                    "loadDate": d.isoformat(),
                    "loadPlace": "",
                    "vehicle": str(cfg.get("defaultVehicle") or ""),
                    "model": str(cfg.get("defaultModel") or ""),
                    "loadNetWeight": "",
                    "unloadDate": "",
                    "unloadPlace": "",
                    "unloadTons": "",
                    "freight": "",
                    "settleTons": "",
                    "amount": "",
                },
            )
        )
    return rows


def normalize_table(cfg: Dict[str, Any], table: Dict[str, Any]) -> Dict[str, Any]:
    t = dict(table)
    meta = t.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    start_date_iso = str(meta.get("startDate") or "").strip() or str(t.get("startDate") or "").strip() or today_iso()
    start_d = parse_iso_date(start_date_iso) or date.today()

    rows_in = t.get("rows", [])
    if not isinstance(rows_in, list):
        rows_in = []

    out_rows: List[Dict[str, Any]] = []
    for i, rr in enumerate(rows_in):
        if not isinstance(rr, dict):
            continue
        r = dict(rr)
        r.setdefault("id", _new_id("row"))
        r = ensure_row_defaults(cfg, r)
        r["loadDate"] = (start_d + timedelta(days=i)).isoformat()
        r["amount"] = compute_amount(r)
        out_rows.append(r)

    t["rows"] = out_rows
    t["startDate"] = start_d.isoformat()
    t["meta"] = {**meta, "startDate": start_d.isoformat()}
    return t


def create_table(cfg: Dict[str, Any], start_date_iso: str, initial_rows: int) -> Dict[str, Any]:
    start_date_iso = (start_date_iso or "").strip() or today_iso()
    rows = ensure_rows_from_start_date(cfg, start_date_iso, int(initial_rows))
    table_id = _new_id("tbl")
    t = {
        "id": table_id,
        "name": f"{start_date_iso}-",
        "startDate": start_date_iso,
        "columns": [{"key": k, "label": h} for k, h in FIXED_HEADERS],
        "rows": rows,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "meta": {"startDate": start_date_iso, "initialRows": int(initial_rows)},
    }
    return normalize_table(cfg, t)


def summarize_table(cfg: Dict[str, Any], table: Dict[str, Any]) -> Tuple[Dict[str, Any], Decimal]:
    t = normalize_table(cfg, table)
    total = Decimal("0")
    rows = t.get("rows", [])
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict):
                continue
            a = to_decimal(r.get("amount"))
            if a is not None:
                total += a

    start_iso = str(t.get("startDate") or "").strip() or today_iso()
    end_iso = ""
    if isinstance(rows, list) and rows:
        last = rows[-1]
        if isinstance(last, dict):
            end_iso = str(last.get("loadDate") or "").strip()
    if end_iso:
        t["name"] = f"{start_iso}-{end_iso}"
    else:
        t["name"] = f"{start_iso}-"
    return t, total


def export_csv_bytes(table: Dict[str, Any]) -> bytes:
    # UTF-8 BOM：Excel 直接识别中文
    bom = "\ufeff"
    headers = [h for _, h in FIXED_HEADERS]
    keys = [k for k, _ in FIXED_HEADERS]

    import io
    import csv as _csv

    sio = io.StringIO()
    w = _csv.writer(sio, lineterminator="\n")
    w.writerow(headers)
    rows = table.get("rows", [])
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict):
                continue
            w.writerow([r.get(k, "") for k in keys])
    return (bom + sio.getvalue()).encode("utf-8")

