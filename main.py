from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import storage


class AppRoot(BoxLayout):
    pass


class HomeScreen(Screen):
    tab = StringProperty("recent")

    def on_pre_enter(self, *args):
        # ScreenManager 在构建过程中会触发 on_pre_enter，此时 app.root 可能还没挂载完成
        Clock.schedule_once(lambda *_: self.refresh(), 0)

    def switch_tab(self, tab: str):
        self.tab = tab
        self.refresh()

    def refresh(self):
        app: TransportApp = App.get_running_app()  # type: ignore[assignment]
        app.refresh_lists()


class EditorScreen(Screen):
    title_text = StringProperty("未打开表格")
    meta_text = StringProperty("")
    status_text = StringProperty("")


class TransportApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir: Path = Path(self.user_data_dir)
        self.tables_dir: Path = self.base_dir / "tables"
        self.exports_dir: Path = self.base_dir / "exports"
        self.cfg: Dict[str, Any] = {}
        self.font_name: str = "Roboto"

        self.current_table: Optional[Dict[str, Any]] = None
        self._autosave_ev = None
        self._dirty = False

        self._editor_grid: Optional[GridLayout] = None
        self._hscroll: Optional[ScrollView] = None

    def build(self):
        self.title = "运输明细（离线）"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        self.cfg = storage.load_config(self.base_dir)
        storage.save_config(self.base_dir, self.cfg)

        self._setup_font()
        Builder.load_file("ui.kv")
        return AppRoot()

    def _setup_font(self) -> None:
        """
        解决中文显示：Kivy 默认 Roboto 在部分环境不含中文字形。
        优先使用项目内 assets/fonts 下的字体（推荐 NotoSansSC-Regular.otf），
        否则在 Android 上尝试系统字体。
        """
        candidates: List[Path] = []
        app_dir = Path(__file__).resolve().parent
        candidates.append(app_dir / "assets" / "fonts" / "NotoSansSC-Regular.otf")
        candidates.append(app_dir / "assets" / "fonts" / "NotoSansSC-Regular.ttf")
        candidates.append(app_dir / "assets" / "fonts" / "SourceHanSansCN-Regular.otf")
        candidates.append(app_dir / "assets" / "fonts" / "SourceHanSansCN-Regular.ttf")

        if platform == "android":
            # 不同 ROM 可能路径不同；尽量覆盖常见机型
            candidates.extend(
                [
                    Path("/system/fonts/NotoSansCJK-Regular.ttc"),
                    Path("/system/fonts/NotoSansSC-Regular.otf"),
                    Path("/system/fonts/NotoSansSC-Regular.ttf"),
                    Path("/system/fonts/DroidSansFallback.ttf"),
                ]
            )

        chosen = next((p for p in candidates if p.exists() and p.is_file()), None)
        if not chosen:
            self.font_name = "Roboto"
            return

        try:
            LabelBase.register(name="AppFont", fn_regular=str(chosen))
            self.font_name = "AppFont"
        except Exception:
            self.font_name = "Roboto"

    # --------- Home / list ---------
    def refresh_lists(self):
        if not self.root:
            return
        sm = self.root.ids.sm  # type: ignore[attr-defined]
        home: HomeScreen = sm.get_screen("home")  # type: ignore[assignment]
        rv = home.ids.rv
        tab = home.tab

        metas = self._list_tables_meta()
        recent_ids = list(self.cfg.get("recentTableIds") or [])

        items = []
        if tab == "recent":
            id_to_meta = {m["id"]: m for m in metas}
            for tid in recent_ids:
                m = id_to_meta.get(tid)
                if not m:
                    continue
                items.append(m)
        else:
            items = metas

        rv.data = [
            {
                "table_id": m["id"],
                "name_text": m["name"],
                "sub_text": f"{m.get('startDate','')} · {m.get('rowCount',0)} 行 · {m.get('updatedAt','')}",
            }
            for m in items
        ]

        # 清理不存在的 recent
        still = [x for x in recent_ids if x in {m["id"] for m in metas}]
        if still != recent_ids:
            self.cfg["recentTableIds"] = still
            storage.save_config(self.base_dir, self.cfg)

    def _list_tables_meta(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for p in storage.list_table_files(self.tables_dir):
            t = storage._read_json(p, None)  # type: ignore[attr-defined]
            if not isinstance(t, dict):
                continue
            out.append(
                {
                    "id": t.get("id") or p.stem,
                    "name": t.get("name") or p.stem,
                    "startDate": t.get("startDate") or (t.get("meta", {}) or {}).get("startDate") or "",
                    "rowCount": len(t.get("rows") or []) if isinstance(t.get("rows"), list) else 0,
                    "updatedAt": t.get("updatedAt") or "",
                }
            )
        return out

    # --------- Dialogs ---------
    def open_create_dialog(self):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        inp_date = TextInput(text=storage.today_iso(), multiline=False, hint_text="YYYY-MM-DD")
        inp_rows = TextInput(text=str(int(self.cfg.get("initialRows") or 31)), multiline=False, input_filter="int")

        content.add_widget(Label(text="开始日期（YYYY-MM-DD）", size_hint_y=None, height=dp(24)))
        content.add_widget(inp_date)
        content.add_widget(Label(text="初始行数", size_hint_y=None, height=dp(24)))
        content.add_widget(inp_rows)

        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        btn_cancel = Button(text="取消")
        btn_ok = Button(text="创建")
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_ok)
        content.add_widget(btns)

        pop = Popup(title="新建表格", content=content, size_hint=(0.9, None), height=dp(320))

        def _cancel(_):
            pop.dismiss()

        def _ok(_):
            start = inp_date.text.strip()
            try:
                rows = int(inp_rows.text.strip() or "1")
            except Exception:
                rows = int(self.cfg.get("initialRows") or 31)
            pop.dismiss()
            self.create_and_open(start, rows)

        btn_cancel.bind(on_release=_cancel)
        btn_ok.bind(on_release=_ok)
        pop.open()

    def confirm_delete(self, table_id: str, name: str):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        content.add_widget(Label(text=f"确定删除表格？\n{name}\n\n删除后不可恢复。"))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        btn_cancel = Button(text="取消")
        btn_ok = Button(text="删除")
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_ok)
        content.add_widget(btns)
        pop = Popup(title="确认删除", content=content, size_hint=(0.9, None), height=dp(260))

        def _cancel(_):
            pop.dismiss()

        def _ok(_):
            pop.dismiss()
            storage.delete_table(self.tables_dir, table_id)
            self.cfg = storage.touch_recent(self.cfg, table_id)  # will be cleaned by refresh
            self.cfg["recentTableIds"] = [x for x in self.cfg.get("recentTableIds", []) if x != table_id]
            storage.save_config(self.base_dir, self.cfg)
            self.refresh_lists()

        btn_cancel.bind(on_release=_cancel)
        btn_ok.bind(on_release=_ok)
        pop.open()

    def _info(self, title: str, msg: str):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        content.add_widget(Label(text=msg))
        btn = Button(text="确定", size_hint_y=None, height=dp(44))
        content.add_widget(btn)
        pop = Popup(title=title, content=content, size_hint=(0.9, None), height=dp(260))
        btn.bind(on_release=lambda *_: pop.dismiss())
        pop.open()

    # --------- Open / editor ---------
    def create_and_open(self, start_date: str, rows: int):
        t = storage.create_table(self.cfg, start_date, rows)
        storage.save_table(self.tables_dir, t)
        self.cfg = storage.touch_recent(self.cfg, t["id"])
        storage.save_config(self.base_dir, self.cfg)
        self.open_table(t["id"])

    def open_table(self, table_id: str):
        t = storage.load_table_by_id(self.tables_dir, table_id)
        if not t:
            self._info("打开失败", "表格不存在或已损坏。")
            self.refresh_lists()
            return

        t = storage.normalize_table(self.cfg, t)
        self.current_table = t
        self.cfg = storage.touch_recent(self.cfg, table_id)
        storage.save_config(self.base_dir, self.cfg)

        self._dirty = False
        self._cancel_autosave()

        sm = self.root.ids.sm  # type: ignore[attr-defined]
        editor: EditorScreen = sm.get_screen("editor")  # type: ignore[assignment]
        editor.title_text = str(t.get("name") or "")
        editor.meta_text = f"开始日期：{t.get('startDate','')} · 行数：{len(t.get('rows') or [])}"
        editor.status_text = "已加载"
        editor.ids.inp_start_date.text = str(t.get("startDate") or "")

        self._build_table_ui()
        sm.current = "editor"

    def go_home(self):
        self._cancel_autosave()
        sm = self.root.ids.sm  # type: ignore[attr-defined]
        sm.current = "home"
        self.refresh_lists()

    # --------- Table UI ---------
    def _build_table_ui(self):
        sm = self.root.ids.sm  # type: ignore[attr-defined]
        editor: EditorScreen = sm.get_screen("editor")  # type: ignore[assignment]
        host: BoxLayout = editor.ids.table_host
        host.clear_widgets()

        hscroll = ScrollView(do_scroll_x=True, do_scroll_y=False, bar_width=dp(6))
        vbox = BoxLayout(orientation="vertical", size_hint_x=None)
        vbox.bind(minimum_width=vbox.setter("width"))

        header = GridLayout(cols=len(storage.FIXED_HEADERS), size_hint_y=None, height=dp(34), spacing=dp(4))
        for _, label in storage.FIXED_HEADERS:
            header.add_widget(
                Label(
                    text=label,
                    size_hint_x=None,
                    width=dp(120),
                    bold=True,
                    color=(1, 1, 1, 0.9),
                    halign="center",
                    valign="middle",
                    text_size=(dp(120), None),
                )
            )
        vbox.add_widget(header)

        vscroll = ScrollView(do_scroll_x=False, do_scroll_y=True, bar_width=dp(6))
        grid = GridLayout(cols=len(storage.FIXED_HEADERS), spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        vscroll.add_widget(grid)
        vbox.add_widget(vscroll)

        hscroll.add_widget(vbox)
        host.add_widget(hscroll)

        self._editor_grid = grid
        self._hscroll = hscroll
        self._render_rows()

    def _render_rows(self):
        if not self.current_table or not self._editor_grid:
            return
        grid = self._editor_grid
        grid.clear_widgets()

        rows = self.current_table.get("rows") or []
        if not isinstance(rows, list):
            rows = []

        load_places = [str(x) for x in (self.cfg.get("loadPlaces") or [])]
        unload_places = [str(x) for x in (self.cfg.get("unloadPlaces") or [])]

        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue

            def add_cell(w):
                w.size_hint_x = None
                w.width = dp(120)
                w.height = dp(38)
                w.size_hint_y = None
                grid.add_widget(w)

            # 装车日期（只读）
            add_cell(TextInput(text=str(row.get("loadDate") or ""), readonly=True, multiline=False))

            # 装车地（下拉）
            sp_load = Spinner(text=str(row.get("loadPlace") or ""), values=load_places)

            def _on_load_place(sp, text, i=idx):
                self._set_cell(i, "loadPlace", text)

            sp_load.bind(text=_on_load_place)
            add_cell(sp_load)

            # 车辆
            ti_vehicle = TextInput(text=str(row.get("vehicle") or ""), multiline=False)
            ti_vehicle.bind(text=lambda inst, val, i=idx: self._set_cell(i, "vehicle", val))
            add_cell(ti_vehicle)

            # 产品型号
            ti_model = TextInput(text=str(row.get("model") or ""), multiline=False)
            ti_model.bind(text=lambda inst, val, i=idx: self._set_cell(i, "model", val))
            add_cell(ti_model)

            # 装车净重
            ti_load_w = TextInput(text=str(row.get("loadNetWeight") or ""), multiline=False, input_filter="float")
            ti_load_w.bind(text=lambda inst, val, i=idx: self._set_cell(i, "loadNetWeight", val))
            add_cell(ti_load_w)

            # 卸车日期
            ti_unload_date = TextInput(text=str(row.get("unloadDate") or ""), multiline=False, hint_text="YYYY-MM-DD")
            ti_unload_date.bind(text=lambda inst, val, i=idx: self._set_cell(i, "unloadDate", val))
            add_cell(ti_unload_date)

            # 卸货地（下拉）
            sp_unload = Spinner(text=str(row.get("unloadPlace") or ""), values=unload_places)

            def _on_unload_place(sp, text, i=idx):
                self._set_cell(i, "unloadPlace", text)

            sp_unload.bind(text=_on_unload_place)
            add_cell(sp_unload)

            # 卸车数（吨）
            ti_unload_tons = TextInput(text=str(row.get("unloadTons") or ""), multiline=False, input_filter="float")
            ti_unload_tons.bind(text=lambda inst, val, i=idx: self._set_cell(i, "unloadTons", val))
            add_cell(ti_unload_tons)

            # 运费
            ti_freight = TextInput(text=str(row.get("freight") or ""), multiline=False, input_filter="float")
            ti_settle = TextInput(text=str(row.get("settleTons") or ""), multiline=False, input_filter="float")
            add_cell(ti_freight)

            # 结算吨数
            add_cell(ti_settle)

            # 金额（只读）
            ti_amount = TextInput(text=str(row.get("amount") or ""), readonly=True, multiline=False)
            add_cell(ti_amount)

            def _update_amount_for_row(i: int):
                if not self.current_table:
                    return
                rr = self.current_table.get("rows") or []
                if not isinstance(rr, list) or i < 0 or i >= len(rr):
                    return
                r = rr[i]
                if not isinstance(r, dict):
                    return
                ti_amount.text = str(r.get("amount") or "")

            ti_freight.bind(
                text=lambda inst, val, i=idx: (self._set_cell(i, "freight", val), _update_amount_for_row(i))
            )
            ti_settle.bind(
                text=lambda inst, val, i=idx: (self._set_cell(i, "settleTons", val), _update_amount_for_row(i))
            )

    def _set_cell(self, row_idx: int, key: str, value: Any):
        if not self.current_table:
            return
        rows = self.current_table.get("rows") or []
        if not isinstance(rows, list) or row_idx < 0 or row_idx >= len(rows):
            return
        r = rows[row_idx]
        if not isinstance(r, dict):
            return
        r[key] = value
        if key in ("freight", "settleTons"):
            r["amount"] = storage.compute_amount(r)
        self._dirty_mark()

    def _dirty_mark(self):
        self._dirty = True
        sm = self.root.ids.sm  # type: ignore[attr-defined]
        editor: EditorScreen = sm.get_screen("editor")  # type: ignore[assignment]
        editor.status_text = "未保存（自动保存中）"
        self._schedule_autosave()

    def _schedule_autosave(self):
        self._cancel_autosave()
        ms = int(self.cfg.get("autosaveMs") or 600)
        self._autosave_ev = Clock.schedule_once(lambda *_: self._autosave(), ms / 1000.0)

    def _cancel_autosave(self):
        if self._autosave_ev is not None:
            try:
                self._autosave_ev.cancel()
            except Exception:
                pass
        self._autosave_ev = None

    def _autosave(self):
        if not self._dirty:
            return
        self.save_current(silent=True)

    # --------- Editor actions ---------
    def set_start_date(self, start_date: str):
        if not self.current_table:
            return
        start_date = (start_date or "").strip()
        d = storage.parse_iso_date(start_date)
        if not d:
            self._info("开始日期无效", "请输入 YYYY-MM-DD（例如 2026-02-25）。")
            return
        self.current_table["startDate"] = d.isoformat()
        self.current_table = storage.normalize_table(self.cfg, self.current_table)
        self._dirty_mark()
        self._render_rows()

    def add_row(self):
        if not self.current_table:
            return
        rows = self.current_table.get("rows") or []
        if not isinstance(rows, list):
            rows = []
        rows.append(
            storage.ensure_row_defaults(
                self.cfg,
                {
                    "id": storage._new_id("row"),  # type: ignore[attr-defined]
                    "loadDate": "",
                    "loadPlace": "",
                    "vehicle": "",
                    "model": "",
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
        self.current_table["rows"] = rows
        self.current_table = storage.normalize_table(self.cfg, self.current_table)
        self._dirty_mark()
        self._render_rows()

    def remove_last_row(self):
        if not self.current_table:
            return
        rows = self.current_table.get("rows") or []
        if not isinstance(rows, list) or not rows:
            return
        rows.pop()
        self.current_table["rows"] = rows
        self.current_table = storage.normalize_table(self.cfg, self.current_table)
        self._dirty_mark()
        self._render_rows()

    def save_current(self, silent: bool = False):
        if not self.current_table:
            return
        self.current_table = storage.normalize_table(self.cfg, self.current_table)
        storage.save_table(self.tables_dir, self.current_table)
        self._dirty = False

        sm = self.root.ids.sm  # type: ignore[attr-defined]
        editor: EditorScreen = sm.get_screen("editor")  # type: ignore[assignment]
        editor.title_text = str(self.current_table.get("name") or "")
        editor.meta_text = f"开始日期：{self.current_table.get('startDate','')} · 行数：{len(self.current_table.get('rows') or [])}"
        editor.status_text = "已保存"
        if not silent:
            self._info("保存成功", "已保存到本机（离线）。")

    def save_and_next(self):
        if not self.current_table:
            return
        self.save_current(silent=True)
        # 下一张：开始日期 = 当前最后一行装车日期 + 1 天
        rows = self.current_table.get("rows") or []
        last_date = None
        if isinstance(rows, list) and rows:
            last_date = storage.parse_iso_date((rows[-1] or {}).get("loadDate")) if isinstance(rows[-1], dict) else None
        if not last_date:
            last_date = storage.parse_iso_date(self.current_table.get("startDate")) or storage.parse_iso_date(storage.today_iso())
        next_start = (last_date + timedelta(days=1)).isoformat() if last_date else storage.today_iso()
        next_rows = len(rows) if isinstance(rows, list) and rows else int(self.cfg.get("initialRows") or 31)
        self.create_and_open(next_start, next_rows)

    def summary(self):
        if not self.current_table:
            return
        t, total = storage.summarize_table(self.cfg, self.current_table)
        self.current_table = t
        storage.save_table(self.tables_dir, self.current_table)
        self._dirty = False

        sm = self.root.ids.sm  # type: ignore[attr-defined]
        editor: EditorScreen = sm.get_screen("editor")  # type: ignore[assignment]
        editor.title_text = str(t.get("name") or "")
        editor.status_text = "已汇总并保存"

        self._render_rows()
        self._info("汇总完成", f"总金额：{total}\n\n表名已更新：{t.get('name')}")

    def export_csv(self):
        if not self.current_table:
            return
        b = storage.export_csv_bytes(self.current_table)
        name = str(self.current_table.get("name") or self.current_table.get("id") or "table").replace("/", "_")
        if not name.lower().endswith(".csv"):
            name = f"{name}.csv"
        out = self.exports_dir / name
        out.write_bytes(b)
        self._info("已导出", f"CSV 已导出到：\n{out}\n\n（UTF-8 BOM，Excel 可直接打开）")

    def delete_current(self):
        if not self.current_table:
            return
        tid = str(self.current_table.get("id") or "")
        tname = str(self.current_table.get("name") or tid)

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        content.add_widget(Label(text=f"确定删除当前表格？\n{tname}\n\n删除后不可恢复。"))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        btn_cancel = Button(text="取消")
        btn_ok = Button(text="删除")
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_ok)
        content.add_widget(btns)
        pop = Popup(title="确认删除", content=content, size_hint=(0.9, None), height=dp(260))

        def _cancel(_):
            pop.dismiss()

        def _ok(_):
            pop.dismiss()
            storage.delete_table(self.tables_dir, tid)
            self.cfg["recentTableIds"] = [x for x in self.cfg.get("recentTableIds", []) if x != tid]
            storage.save_config(self.base_dir, self.cfg)
            self.current_table = None
            self.go_home()

        btn_cancel.bind(on_release=_cancel)
        btn_ok.bind(on_release=_ok)
        pop.open()


if __name__ == "__main__":
    TransportApp().run()

