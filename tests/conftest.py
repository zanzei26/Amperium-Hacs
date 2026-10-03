"""Load the pure modules without Home Assistant installed."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "amperium"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"amperium.{name}", PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"amperium.{name}"] = module
    spec.loader.exec_module(module)
    return module


pkg = types.ModuleType("amperium")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["amperium"] = pkg
const = _load("const")
derived = _load("derived")
hourpower = _load("hourpower")
api = _load("api")
