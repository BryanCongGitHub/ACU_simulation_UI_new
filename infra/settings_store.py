"""Centralized helpers for reading and writing application settings.

This module wraps ``QSettings`` access to keep persistence logic in one
place.  GUI components can import the light-weight dataclasses below and
avoid duplicating group names or key strings.  The helpers intentionally
keep the data structures simple so existing widgets can continue to work
without large refactors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import QSettings


@dataclass
class DeviceConfigSettings:
    """Persisted device configuration values shown in the sidebar."""

    acu_ip: str = ""
    acu_send_port: str = ""
    acu_receive_port: str = ""
    target_ip: str = ""
    target_receive_port: str = ""
    # optional preset name selected by the user (e.g. INV1, INV2)
    device_preset: str = ""


@dataclass
class WaveformSettings:
    """Persisted preferences for the waveform display widget."""

    selected_signals: List[str] = field(default_factory=list)
    time_range: Optional[str] = None
    auto_range: bool = True
    last_export_path: str = ""
    signal_order: List[str] = field(default_factory=list)
    splitter_sizes: Optional[List[int]] = None
    palette: Dict[str, str] = field(default_factory=dict)


@dataclass
class HeaderVisibilitySettings:
    """Column visibility toggles for the parse table dock."""

    timestamp: bool = True
    address: bool = True
    device_type: bool = True
    data_length: bool = True
    parsed_data: bool = True


@dataclass
class MainWindowState:
    """Geometry and dock layout for the main window."""

    geometry: Optional[bytes] = None
    main_state: Optional[bytes] = None
    sidebar_index: int = 0


# ---- Device configuration -------------------------------------------------


def load_device_config(
    defaults: DeviceConfigSettings | None = None,
) -> DeviceConfigSettings:
    settings = QSettings()
    settings.beginGroup("ACUSimulator")
    settings.beginGroup("DeviceConfig")
    try:
        data = DeviceConfigSettings(
            acu_ip=str(settings.value("acu_ip", getattr(defaults, "acu_ip", ""))),
            acu_send_port=str(
                settings.value("acu_send_port", getattr(defaults, "acu_send_port", ""))
            ),
            acu_receive_port=str(
                settings.value(
                    "acu_receive_port", getattr(defaults, "acu_receive_port", "")
                )
            ),
            target_ip=str(
                settings.value("target_ip", getattr(defaults, "target_ip", ""))
            ),
            target_receive_port=str(
                settings.value(
                    "target_receive_port", getattr(defaults, "target_receive_port", "")
                )
            ),
            device_preset=str(
                settings.value("device_preset", getattr(defaults, "device_preset", ""))
            ),
        )
    finally:
        settings.endGroup()
        settings.endGroup()
    return data


def save_device_config(data: DeviceConfigSettings) -> None:
    settings = QSettings()
    settings.beginGroup("ACUSimulator")
    settings.beginGroup("DeviceConfig")
    try:
        settings.setValue("acu_ip", data.acu_ip)
        settings.setValue("acu_send_port", data.acu_send_port)
        settings.setValue("acu_receive_port", data.acu_receive_port)
        settings.setValue("target_ip", data.target_ip)
        settings.setValue("target_receive_port", data.target_receive_port)
        try:
            settings.setValue("device_preset", data.device_preset)
        except Exception:
            # best-effort: do not break save if this key is not supported
            pass
    finally:
        settings.endGroup()
        settings.endGroup()
        settings.sync()


# ---- Waveform settings ----------------------------------------------------


def load_waveform_settings() -> WaveformSettings:
    settings = QSettings()
    settings.beginGroup("WaveformDisplay")
    try:
        selected_signals = list(settings.value("selected_signals", []))
        if not isinstance(selected_signals, list):
            selected_signals = []
        time_range = settings.value("time_range", None)
        auto_range = bool(settings.value("auto_range", True))
        last_export_path = str(settings.value("last_export_path", ""))
        signal_order = list(settings.value("signal_order", []))
        if not isinstance(signal_order, list):
            signal_order = []
        raw_sizes = settings.value("splitter_sizes", None)
        splitter_sizes: Optional[List[int]]
        if isinstance(raw_sizes, list):
            try:
                splitter_sizes = [int(x) for x in raw_sizes]
            except Exception:
                splitter_sizes = None
        else:
            splitter_sizes = None
        palette_value = settings.value("palette", "") or ""
        palette: Dict[str, str]
        if isinstance(palette_value, str) and palette_value:
            try:
                parsed = json.loads(palette_value)
                if isinstance(parsed, dict):
                    palette = {str(k): str(v) for k, v in parsed.items()}
                else:
                    palette = {}
            except Exception:
                palette = {}
        elif isinstance(palette_value, dict):
            palette = {str(k): str(v) for k, v in palette_value.items()}
        else:
            palette = {}
    finally:
        settings.endGroup()
    return WaveformSettings(
        selected_signals=selected_signals,
        time_range=time_range,
        auto_range=auto_range,
        last_export_path=last_export_path,
        signal_order=signal_order,
        splitter_sizes=splitter_sizes,
        palette=palette,
    )


def save_waveform_settings(data: WaveformSettings) -> None:
    settings = QSettings()
    settings.beginGroup("WaveformDisplay")
    try:
        settings.setValue("selected_signals", list(data.selected_signals))
        if data.time_range is not None:
            settings.setValue("time_range", data.time_range)
        settings.setValue("auto_range", bool(data.auto_range))
        settings.setValue("last_export_path", data.last_export_path)
        settings.setValue("signal_order", list(data.signal_order))
        if data.splitter_sizes is not None:
            settings.setValue("splitter_sizes", list(data.splitter_sizes))
        if data.palette:
            try:
                settings.setValue(
                    "palette", json.dumps(dict(data.palette), ensure_ascii=False)
                )
            except Exception:
                settings.setValue("palette", json.dumps({}, ensure_ascii=False))
    finally:
        settings.endGroup()
        settings.sync()


# ---- Parse table header visibility ---------------------------------------


def load_header_visibility() -> HeaderVisibilitySettings:
    settings = QSettings()
    settings.beginGroup("ACUSimulator")
    try:
        visibility = settings.value("parse_header_visibility", {})
    finally:
        settings.endGroup()
    if not isinstance(visibility, dict):
        visibility = {}
    return HeaderVisibilitySettings(
        timestamp=bool(visibility.get("timestamp", True)),
        address=bool(visibility.get("address", True)),
        device_type=bool(visibility.get("device_type", True)),
        data_length=bool(visibility.get("data_length", True)),
        parsed_data=bool(visibility.get("parsed_data", True)),
    )


def save_header_visibility(data: HeaderVisibilitySettings) -> None:
    settings = QSettings()
    settings.beginGroup("ACUSimulator")
    try:
        settings.setValue(
            "parse_header_visibility",
            {
                "timestamp": data.timestamp,
                "address": data.address,
                "device_type": data.device_type,
                "data_length": data.data_length,
                "parsed_data": data.parsed_data,
            },
        )
    finally:
        settings.endGroup()
        settings.sync()


# ---- Main window state ----------------------------------------------------


def load_mainwindow_state() -> MainWindowState:
    settings = QSettings()
    settings.beginGroup("ACUSimulator")
    try:
        geometry = settings.value("geometry", None)
        main_state = settings.value("main_state", None)
        sidebar_index = int(settings.value("sidebar_index", 0))
    finally:
        settings.endGroup()
    return MainWindowState(
        geometry=geometry if geometry else None,
        main_state=main_state if main_state else None,
        sidebar_index=sidebar_index,
    )


def save_mainwindow_state(state: MainWindowState) -> None:
    settings = QSettings()
    settings.beginGroup("ACUSimulator")
    try:
        if state.geometry is not None:
            settings.setValue("geometry", state.geometry)
        if state.main_state is not None:
            settings.setValue("main_state", state.main_state)
        settings.setValue("sidebar_index", state.sidebar_index)
    finally:
        settings.endGroup()
        settings.sync()


# ---- Utility helpers ------------------------------------------------------


def reset_groups(groups: List[str]) -> None:
    """Remove the given top-level groups from ``QSettings``."""

    settings = QSettings()
    for group in groups:
        settings.beginGroup(group)
        settings.remove("")
        settings.endGroup()
    settings.sync()


def export_groups(groups: List[str]) -> Dict[str, Dict[str, object]]:
    """Return a nested dict snapshot of the requested groups."""

    snapshot: Dict[str, Dict[str, object]] = {}
    settings = QSettings()
    for group in groups:
        settings.beginGroup(group)
        snapshot[group] = {}
        for key in settings.childKeys():
            snapshot[group][key] = settings.value(key)
        settings.endGroup()
    return snapshot


def import_groups(snapshot: Dict[str, Dict[str, object]]) -> None:
    """Write a snapshot created by :func:`export_groups` back to settings."""

    settings = QSettings()
    try:
        for group, values in snapshot.items():
            settings.beginGroup(group)
            for key, value in values.items():
                settings.setValue(key, value)
            settings.endGroup()
    finally:
        settings.sync()


def clear_all_settings() -> None:
    settings = QSettings()
    settings.clear()
    settings.sync()


def export_to_ini(path: str, groups: Optional[Iterable[str]] = None) -> None:
    src = QSettings()
    dest = QSettings(path, QSettings.IniFormat)

    prefixes = None if groups is None else {str(g) for g in groups}
    for key in src.allKeys():
        if prefixes is None:
            dest.setValue(key, src.value(key))
            continue
        for prefix in prefixes:
            if key == prefix or key.startswith(prefix + "/"):
                dest.setValue(key, src.value(key))
                break

    dest.sync()


def import_from_ini(path: str, groups: Optional[Iterable[str]] = None) -> None:
    src = QSettings(path, QSettings.IniFormat)
    dest = QSettings()

    prefixes = None if groups is None else {str(g) for g in groups}
    for key in src.allKeys():
        if prefixes is None:
            dest.setValue(key, src.value(key))
            continue
        for prefix in prefixes:
            if key == prefix or key.startswith(prefix + "/"):
                dest.setValue(key, src.value(key))
                break

    dest.sync()


def apply_default_waveform_settings() -> None:
    current = load_waveform_settings()
    current.selected_signals = []
    current.signal_order = []
    current.time_range = "10分钟"
    current.auto_range = True
    current.last_export_path = ""
    current.splitter_sizes = None
    save_waveform_settings(current)


def apply_default_device_config() -> None:
    default = DeviceConfigSettings(
        acu_ip="10.2.0.1",
        acu_send_port="49152",
        acu_receive_port="49156",
        target_ip="10.2.0.5",
        target_receive_port="49152",
    )
    save_device_config(default)
