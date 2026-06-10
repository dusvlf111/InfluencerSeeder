"""버튼매핑 탭 Mixin — 스텝(플로우)별 그룹 + 스텝마다 여러 후보(순서대로 시도).

각 수집 스텝(step_id)을 하나의 그룹으로 보여주고, 그 안에 셀렉터 후보를 여러 개
둘 수 있다. 수집 시 **위에서부터 차례로 시도**하다 처음 매칭되는 요소를 사용하고,
실패하면 다음 후보로 넘어간다(core.scraper._resolve_selector 의 priority fallback).

저장 계약은 기존 save_selectors(list[dict] with priority int) 를 그대로 유지한다 —
``_collect_selectors()`` 가 그룹/행 순서를 priority(1..) 로 부여한 list[dict] 를 반환.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QScrollArea, QGroupBox,
)

import core.storage as storage

# Type 셀 드롭다운 항목.
_MAP_TYPES = ["xpath", "css", "coord"]

# 표준 수집 스텝(플로우) 순서 + 표시 라벨. 저장된 데이터에 없어도 항상 보여줘
# 사용자가 후보를 추가할 수 있게 한다. 여기 없는 step_id 는 뒤에 추가로 표시.
_FLOW_STEPS = [
    ("search_icon",     "1. 검색/탐색 아이콘 클릭"),
    ("search_input",    "2. 검색어 입력창"),
    ("tag_result",      "3. 태그 검색결과 클릭"),
    ("post_link",       "4. 게시물(이미지) 링크"),
    ("profile_link",    "5. 프로필 이름/링크 클릭"),
    ("username_text",   "유저네임 텍스트"),
    ("followers_count", "팔로워 수"),
    ("following_count", "팔로우 수"),
    ("posts_count",     "게시물 수"),
    ("bio_text",        "소개글"),
    ("website_link",    "웹사이트"),
]
_FLOW_LABELS = dict(_FLOW_STEPS)

_MAPPING_NOTE = (
    "스텝마다 셀렉터 후보를 여러 개 둘 수 있습니다. 수집 시 위에서부터 차례로 "
    "시도하고, 위치를 못 찾으면 다음 후보로 넘어갑니다(실패하면 그 다음).  "
    "브라우저에서 요소 우클릭 → 검사 → Copy → Copy XPath / Copy selector 로 값을 "
    "복사해 [Selector Value] 에 붙여넣으세요. Type 은 xpath / css / coord."
)


class MappingTabMixin:
    # ── Build ───────────────────────────────────────────────────────────────────

    def _build_mapping_tab(self) -> QWidget:
        # 그룹 디스크립터: [{"step_id","step_name","table"}]
        self._mapping_groups = []

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        note = QLabel(_MAPPING_NOTE)
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        outer.addWidget(note)

        # 그룹 박스들이 들어갈 호스트 레이아웃(_populate_mapping 이 채운다).
        self._mapping_host = QVBoxLayout()
        self._mapping_host.setSpacing(12)
        outer.addLayout(self._mapping_host)

        # 하단: 임의 step_id 그룹 추가 + 전체 기본값 초기화.
        bottom = QHBoxLayout()
        btn_add_step = QPushButton("+ 스텝(step_id) 추가")
        btn_add_step.clicked.connect(self._mapping_add_step)
        btn_reset = QPushButton("전체 기본값으로 초기화")
        btn_reset.clicked.connect(self._mapping_reset)
        bottom.addWidget(btn_add_step)
        bottom.addStretch()
        bottom.addWidget(btn_reset)
        outer.addLayout(bottom)
        outer.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    # ── Group widget ─────────────────────────────────────────────────────────────

    def _mapping_build_group(self, step_id: str, step_name: str, candidates: list):
        """후보 테이블을 가진 스텝 그룹 박스를 만들어 호스트에 추가한다."""
        label = step_name or _FLOW_LABELS.get(step_id, step_id)
        box = QGroupBox(f"{label}   ({step_id})")
        box.setObjectName("mappingGroup")
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(6)

        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Type", "Selector Value (위 → 아래 순서로 시도)"])
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 80)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setWordWrap(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setMinimumHeight(120)
        for cand in candidates:
            self._mapping_set_cand(
                table, table.rowCount(),
                cand.get("selector_type", "xpath"),
                cand.get("selector_value", ""),
            )
        table.resizeRowsToContents()
        v.addWidget(table)

        # 그룹별 후보 조작 버튼(해당 table 에 스코프).
        row = QHBoxLayout()
        b_add = QPushButton("후보 추가")
        b_add.clicked.connect(lambda _=False, t=table: self._mapping_cand_add(t))
        b_del = QPushButton("후보 삭제")
        b_del.clicked.connect(lambda _=False, t=table: self._mapping_cand_del(t))
        b_up = QPushButton("위로")
        b_up.clicked.connect(lambda _=False, t=table: self._mapping_cand_move(t, -1))
        b_dn = QPushButton("아래로")
        b_dn.clicked.connect(lambda _=False, t=table: self._mapping_cand_move(t, 1))
        for b in (b_add, b_del, b_up, b_dn):
            row.addWidget(b)
        row.addStretch()
        v.addLayout(row)

        self._mapping_host.addWidget(box)
        self._mapping_groups.append(
            {"step_id": step_id, "step_name": label, "table": table}
        )

    # ── Candidate row helpers ────────────────────────────────────────────────────

    @staticmethod
    def _mapping_make_type_combo(sel_type):
        combo = QComboBox()
        combo.addItems(_MAP_TYPES)
        tv = str(sel_type or "xpath")
        idx = combo.findText(tv)
        if idx < 0:
            combo.addItem(tv)
            idx = combo.findText(tv)
        combo.setCurrentIndex(max(0, idx))
        return combo

    @classmethod
    def _mapping_set_cand(cls, table, r, sel_type, value):
        if r >= table.rowCount():
            table.insertRow(r)
        table.setCellWidget(r, 0, cls._mapping_make_type_combo(sel_type))
        table.setItem(r, 1, QTableWidgetItem(str(value or "")))

    def _mapping_cand_add(self, table):
        r = table.rowCount()
        self._mapping_set_cand(table, r, "xpath", "")
        table.resizeRowToContents(r)

    @staticmethod
    def _mapping_cand_del(table):
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        for r in rows:
            table.removeRow(r)

    def _mapping_cand_move(self, table, delta: int):
        rows = sorted({i.row() for i in table.selectedIndexes()})
        if not rows:
            return
        r = rows[0]
        target = r + delta
        if target < 0 or target >= table.rowCount():
            return

        def _type(row):
            w = table.cellWidget(row, 0)
            return w.currentText() if w else "xpath"

        def _val(row):
            it = table.item(row, 1)
            return it.text() if it else ""

        cur = (_type(r), _val(r))
        oth = (_type(target), _val(target))
        self._mapping_set_cand(table, r, oth[0], oth[1])
        self._mapping_set_cand(table, target, cur[0], cur[1])
        table.selectRow(target)

    # ── Populate / collect ───────────────────────────────────────────────────────

    def _populate_mapping(self, selectors: list):
        """스텝별 그룹을 다시 만들어 후보를 채운다.

        ``selectors`` 는 storage.load_selectors() 형식(priority 정렬됨). step_id 별로
        묶고, 표준 스텝(_FLOW_STEPS)은 후보가 없어도 항상 표시한다.
        """
        # 기존 그룹 제거.
        self._mapping_groups = []
        while self._mapping_host.count():
            item = self._mapping_host.takeAt(0)
            wdg = item.widget()
            if wdg is not None:
                wdg.setParent(None)
                wdg.deleteLater()

        grouped: dict[str, list] = {}
        names: dict[str, str] = {}
        for row in selectors:
            sid = (row.get("step_id") or "").strip()
            if not sid:
                continue
            grouped.setdefault(sid, []).append(row)
            names.setdefault(sid, row.get("step_name", ""))

        # 표준 스텝 먼저(없으면 빈 그룹), 그다음 사용자 정의 step_id.
        ordered = [sid for sid, _ in _FLOW_STEPS]
        ordered += [sid for sid in grouped if sid not in _FLOW_LABELS]

        for sid in ordered:
            self._mapping_build_group(
                sid,
                names.get(sid, _FLOW_LABELS.get(sid, "")),
                grouped.get(sid, []),
            )

    def _mapping_add_step(self):
        """빈 사용자 정의 step_id 그룹 하나 추가(이름은 비워두면 step_id 사용)."""
        # 중복되지 않는 임시 step_id 생성.
        existing = {g["step_id"] for g in self._mapping_groups}
        base = "custom_step"
        sid = base
        n = 1
        while sid in existing:
            n += 1
            sid = f"{base}{n}"
        self._mapping_build_group(sid, "", [{"selector_type": "xpath", "selector_value": ""}])

    def _mapping_reset(self):
        self._populate_mapping(storage.selector_defaults())

    def _collect_selectors(self) -> list[dict]:
        """그룹/행 순서를 priority(1..) 로 부여해 selectors.csv 스키마로 변환.

        값이 빈 후보 행은 건너뛴다. step_id 가 빈 그룹도 건너뛴다.
        """
        rows: list[dict] = []
        for g in self._mapping_groups:
            sid = (g["step_id"] or "").strip()
            if not sid:
                continue
            table = g["table"]
            prio = 0
            for r in range(table.rowCount()):
                item = table.item(r, 1)
                val = (item.text() if item else "").strip()
                if not val:
                    continue
                combo = table.cellWidget(r, 0)
                sel_type = combo.currentText() if combo else "xpath"
                prio += 1
                rows.append({
                    "step_id":        sid,
                    "step_name":      g["step_name"],
                    "priority":       prio,
                    "selector_type":  (sel_type or "xpath"),
                    "selector_value": val,
                })
        return rows
