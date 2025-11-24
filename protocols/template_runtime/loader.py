"""Loader that turns YAML templates into protocol instances."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import yaml

from .adapters.template_protocol import TemplateProtocol
from .schema import CategorySpec, TemplateConfigError, TemplateSpec, parse_template_spec
from infra.app_paths import resource_path


class ProtocolTemplateLoader:
    """Loads protocol templates from YAML files and caches instantiated protocols."""

    def __init__(self, template_path: Path):
        self._template_path = template_path
        self._spec: Optional[TemplateSpec] = None
        self._cache: Dict[str, TemplateProtocol] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def spec(self) -> TemplateSpec:
        if self._spec is None:
            data = self._template_path.read_text(encoding="utf-8")
            raw = yaml.safe_load(data)
            self._spec = parse_template_spec(raw)
        return self._spec

    def protocol_for_category(self, category: str) -> TemplateProtocol:
        if category not in self._cache:
            spec = self.spec()
            category_spec = self._get_category_spec(spec, category)
            self._cache[category] = TemplateProtocol(spec, category_spec)
        return self._cache[category]

    @classmethod
    def default(cls) -> "ProtocolTemplateLoader":
        template_path = resource_path(
            "protocols", "templates", "acusim.yaml", must_exist=True
        )
        return cls(template_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_category_spec(self, spec: TemplateSpec, category: str) -> CategorySpec:
        try:
            return spec.categories[category]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise TemplateConfigError(
                f"Unknown category '{category}' in template"
            ) from exc


_default_loader: Optional[ProtocolTemplateLoader] = None


def load_template_protocol(category: str) -> TemplateProtocol:
    """Convenience helper that returns a protocol for the requested category."""

    global _default_loader
    if _default_loader is None:
        _default_loader = ProtocolTemplateLoader.default()
    return _default_loader.protocol_for_category(category)
