"""SettingsView 탭별 Mixin 패키지.

각 탭 로직을 `*TabMixin`(plain class, QWidget 상속 X)으로 분리한다.
믹스인 메서드는 런타임에 `self`(=SettingsView 인스턴스)에서 동작하며,
`self._x = ...` 형태로 위젯/상태 속성을 SettingsView 에 그대로 세팅한다.
→ 테스트의 `view._w_browser`/`view._flow_table` 등 직접 참조가 유지된다.
"""

from .helpers import _as_bool
from .web_tab import WebTabMixin
from .delays_tab import DelaysTabMixin, _DELAY_STEPS
from .flow_tab import FlowTabMixin
from .target_tab import TargetTabMixin
from .mapping_tab import MappingTabMixin
from .flowbuilder_tab import FlowBuilderTabMixin
from .excluded_tab import ExcludedTabMixin
from .deps_tab import DepsTabMixin
from .config_io import ConfigIOMixin

__all__ = [
    "_as_bool",
    "_DELAY_STEPS",
    "WebTabMixin",
    "DelaysTabMixin",
    "FlowTabMixin",
    "TargetTabMixin",
    "MappingTabMixin",
    "FlowBuilderTabMixin",
    "ExcludedTabMixin",
    "DepsTabMixin",
    "ConfigIOMixin",
]
