from __future__ import annotations

from copy import deepcopy
import logging
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .analysis import run_analysis
from .briefing import generate_briefing
from .collector import collect_articles
from .config import get_analysis_now
from .db import clear_run_output_tables, connect, ensure_schema, seed_config_tables
from .press_release import (
    apply_manual_overrides_to_profile,
    build_config_from_press_release,
    build_press_session_paths,
    load_press_release_profile,
    load_session_manual_overrides,
    save_press_session_metadata,
)
from .session_outputs import build_session_daily_outputs
from .utils import collapse_whitespace


APP_TITLE = "MOLIT Media Monitor"
USAGE_GUIDE_TEXT = (
    "보도자료 배포일 오전 10시(한국시간)를 시작점으로 하여 D+3 23:59:59까지 보도된 관련 기사를 수집합니다. "
    "(실행 시점에서는 이 범위에서 현재까지 나온 기사만 수집)\n\n"
    "수집 방법: RSS/sitemap 또는 Google News에서 기사 추출 후 최종 수집\n"
    "RSS/sitemap - 각 소스의 최신 100개 기사 목록을 읽어 추출\n"
    "Google News - 쿼리별로 최대 50건까지 읽어 추출\n"
    "검색 쿼리 - 추출한 기사의 제목/요약에 검색 쿼리의 각 단어가 모두 포함되면 수집 후보로 판단\n"
    "핵심 키워드 - 핵심 키워드가 입력된 경우, 제목/요약에 모든 핵심 키워드가 포함된 기사만 최종 수집"
)


def main() -> int:
    app = MediaMonitorDesktopApp()
    app.mainloop()
    return 0


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def split_multiline_values(raw_text: str) -> list[str]:
    values = []
    seen = set()
    for raw_line in str(raw_text or "").splitlines():
        cleaned = collapse_whitespace(raw_line)
        normalized = cleaned.casefold()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        values.append(cleaned)
    return values


def safe_open_path(path: str | Path | None) -> None:
    if not path:
        return
    target = str(Path(path).resolve())
    if sys.platform.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
        return
    raise OSError("This desktop wrapper currently expects Windows for file opening.")


class QueueLogHandler(logging.Handler):
    def __init__(self, ui_queue: queue.Queue):
        super().__init__()
        self.ui_queue = ui_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        self.ui_queue.put(("log", message))


class WorkflowCancelledError(Exception):
    pass


class MediaMonitorDesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1480x920")
        self.minsize(1240, 760)

        self.base_dir = get_app_base_dir()
        self.session_root = self.base_dir / "sessions"
        self.inputs_dir = self.base_dir / "inputs" / "press_releases"

        self.current_input_path: Path | None = None
        self.current_profile: dict[str, Any] | None = None
        self.current_session_paths: dict[str, str] | None = None
        self.last_run_result: dict[str, Any] | None = None
        self.is_busy = False
        self.cancel_event = threading.Event()
        self.ui_queue: queue.Queue = queue.Queue()
        self.log_handler = QueueLogHandler(self.ui_queue)
        self.log_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        self.file_log_handler: logging.Handler | None = None

        self.file_var = tk.StringVar()
        self.title_var = tk.StringVar(value="-")
        self.release_var = tk.StringVar(value="-")
        self.session_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="보도자료 HWPX를 선택하면 자동 추출 결과가 표시됩니다.")
        self.result_var = tk.StringVar(value="")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.progress_detail_var = tk.StringVar(value="진행 대기")
        self.run_started_at: float | None = None

        self._configure_logging()
        self._build_widgets()
        self.after(150, self._process_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_logging(self) -> None:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        if not any(isinstance(handler, QueueLogHandler) for handler in root_logger.handlers):
            root_logger.addHandler(self.log_handler)
        logs_dir = self.base_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "app.log"
        existing_file_handler = next(
            (
                handler
                for handler in root_logger.handlers
                if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path.resolve()
            ),
            None,
        )
        if existing_file_handler is None:
            self.file_log_handler = logging.FileHandler(log_path, encoding="utf-8")
            self.file_log_handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
            )
            root_logger.addHandler(self.file_log_handler)
        else:
            self.file_log_handler = existing_file_handler

    def _build_widgets(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(4, weight=1)
        container.rowconfigure(6, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="보도자료 파일").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(header, textvariable=self.file_var, state="readonly").grid(row=0, column=1, sticky="ew")
        ttk.Button(header, text="HWPX 선택", command=self.choose_press_release).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(header, text="자동값 복원(쿼리, 키워드)", command=self.restore_auto_values).grid(
            row=0, column=3, padx=(8, 0)
        )
        ttk.Button(header, text="저장값 불러오기(직전 실행값)", command=self.reload_saved_values).grid(
            row=0, column=4, padx=(8, 0)
        )

        usage = ttk.LabelFrame(container, text="사용 안내", padding=10)
        usage.grid(row=1, column=0, sticky="ew", pady=(12, 10))
        usage.columnconfigure(0, weight=1)
        ttk.Label(
            usage,
            text=USAGE_GUIDE_TEXT,
            justify="left",
            anchor="w",
            wraplength=1180,
        ).grid(row=0, column=0, sticky="ew")

        info = ttk.LabelFrame(container, text="세션 정보", padding=10)
        info.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        info.columnconfigure(1, weight=1)
        info.columnconfigure(3, weight=1)

        ttk.Label(info, text="정책 제목").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.title_var).grid(row=0, column=1, sticky="w")
        ttk.Label(info, text="배포일시").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Label(info, textvariable=self.release_var).grid(row=0, column=3, sticky="w")
        ttk.Label(info, text="세션 ID").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(info, textvariable=self.session_var).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(info, text="안내").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(8, 0))
        ttk.Label(
            info,
            text=(
                "쿼리, 키워드 각 박스 내용은 수정하여 추가, 변경 또는 삭제할 수 있습니다.\n\n"
                "자동값 복원(쿼리, 키워드)는 쿼리·키워드 최초값 복원\n"
                "저장값 불러오기(직전 실행값)은 쿼리·키워드 직전 실행값"
            ),
            justify="left",
        ).grid(row=1, column=3, sticky="w", pady=(8, 0))

        editors = ttk.Frame(container)
        editors.grid(row=4, column=0, sticky="nsew")
        editors.columnconfigure(0, weight=1)
        editors.columnconfigure(1, weight=1)
        editors.rowconfigure(0, weight=1)

        self.query_text = self._build_editor(editors, 0, "검색 쿼리")
        self.core_keyword_text = self._build_editor(editors, 1, "핵심 키워드(수동 입력)")

        action_bar = ttk.Frame(container)
        action_bar.grid(row=5, column=0, sticky="ew", pady=(12, 10))
        action_bar.columnconfigure(5, weight=1)

        self.run_button = ttk.Button(action_bar, text="기사 검색", command=self.start_run)
        self.run_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = ttk.Button(action_bar, text="중단", command=self.stop_run, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        self.open_csv_button = ttk.Button(
            action_bar, text="기사 목록 열기", command=self.open_latest_csv, state="disabled"
        )
        self.open_csv_button.grid(row=0, column=2, padx=(0, 8))
        self.open_briefing_button = ttk.Button(
            action_bar,
            text="브리핑 열기",
            command=self.open_latest_briefing,
            state="disabled",
        )
        self.open_briefing_button.grid(row=0, column=3, padx=(0, 8))
        self.open_session_button = ttk.Button(
            action_bar,
            text="세션 폴더 열기",
            command=self.open_session_dir,
            state="disabled",
        )
        self.open_session_button.grid(row=0, column=4, padx=(0, 8))
        ttk.Label(action_bar, textvariable=self.status_var).grid(row=0, column=5, sticky="w")
        self.progress_bar = ttk.Progressbar(
            action_bar,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.progress_value,
        )
        self.progress_bar.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        ttk.Label(action_bar, textvariable=self.progress_detail_var).grid(
            row=2, column=0, columnspan=6, sticky="w", pady=(4, 0)
        )

        lower = ttk.PanedWindow(container, orient="horizontal")
        lower.grid(row=6, column=0, sticky="nsew")

        log_frame = ttk.LabelFrame(lower, text="실행 로그", padding=8)
        preview_frame = ttk.LabelFrame(lower, text="브리핑 미리보기", padding=8)
        lower.add(log_frame, weight=1)
        lower.add(preview_frame, weight=1)

        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        self.log_text = ScrolledText(log_frame, wrap="word", height=16)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

        ttk.Label(preview_frame, textvariable=self.result_var).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.preview_text = ScrolledText(preview_frame, wrap="word", height=16)
        self.preview_text.grid(row=1, column=0, sticky="nsew")
        self.preview_text.configure(state="disabled")

    def _build_editor(self, parent: ttk.Frame, column: int, title: str, editable: bool = True) -> tk.Text:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        editor = tk.Text(frame, wrap="none", height=18)
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=editor.xview)
        editor.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        editor.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        if not editable:
            editor.configure(state="disabled")
        return editor

    def choose_press_release(self) -> None:
        initial_dir = self.inputs_dir if self.inputs_dir.exists() else self.base_dir
        path = filedialog.askopenfilename(
            parent=self,
            title="보도자료 HWPX 선택",
            initialdir=str(initial_dir),
            filetypes=[("HWPX files", "*.hwpx"), ("All files", "*.*")],
        )
        if not path:
            return
        self.load_press_release(path, use_saved_overrides=True)

    def load_press_release(self, path: str | Path, use_saved_overrides: bool) -> None:
        try:
            profile = load_press_release_profile(path)
            session_paths = build_press_session_paths(profile, self.session_root)
            effective_profile = deepcopy(profile)
            overrides = None
            display_core_keywords: list[str] = []
            if use_saved_overrides:
                overrides = load_session_manual_overrides(session_paths)
                effective_profile = apply_manual_overrides_to_profile(profile, overrides)
                display_core_keywords = list(overrides.get("topic_keywords_replace", []))

            self.current_input_path = Path(path)
            self.current_profile = profile
            self.current_session_paths = session_paths
            self.last_run_result = None

            self.file_var.set(str(self.current_input_path))
            self.title_var.set(profile.get("title", "-"))
            self.release_var.set(profile.get("release_datetime", "-"))
            self.session_var.set(session_paths["session_id"])
            self._set_editor_values(self.query_text, effective_profile.get("google_queries", []))
            self._set_editor_values(self.core_keyword_text, display_core_keywords)
            self._set_preview_text("")
            self.result_var.set("")
            self.status_var.set("검색 규칙이 준비되었습니다. 필요하면 수정 후 실행을 누르십시오.")
            self._log(f"Loaded press release: {self.current_input_path}")
            self._set_output_buttons_enabled(False)
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"보도자료를 읽지 못했습니다.\n\n{error}")
            self._log(f"Failed to load press release: {error}")

    def restore_auto_values(self) -> None:
        if not self.current_profile:
            messagebox.showinfo(APP_TITLE, "먼저 보도자료를 선택하십시오.")
            return
        self._set_editor_values(self.query_text, self.current_profile.get("google_queries", []))
        self._set_editor_values(self.core_keyword_text, [])
        self.status_var.set("검색 쿼리는 자동 추출값으로, 핵심 키워드는 빈 상태로 되돌렸습니다.")

    def reload_saved_values(self) -> None:
        if not self.current_profile or not self.current_input_path:
            messagebox.showinfo(APP_TITLE, "먼저 보도자료를 선택하십시오.")
            return
        self.load_press_release(self.current_input_path, use_saved_overrides=True)

    def start_run(self) -> None:
        if self.is_busy:
            return
        if not self.current_profile:
            messagebox.showinfo(APP_TITLE, "먼저 보도자료 HWPX를 선택하십시오.")
            return

        overrides = self.build_manual_overrides_from_ui()
        self.cancel_event.clear()
        self.last_run_result = None
        self._set_output_buttons_enabled(False)
        self._set_busy(True)
        self.run_started_at = time.monotonic()
        self._set_progress(0, "실행 준비 중")
        self.status_var.set("기사 수집과 분석을 실행 중입니다. 잠시 기다리십시오.")
        worker = threading.Thread(
            target=self._run_workflow_worker,
            args=(deepcopy(self.current_profile), overrides),
            daemon=True,
        )
        worker.start()

    def stop_run(self) -> None:
        if not self.is_busy:
            return
        self.cancel_event.set()
        self.stop_button.configure(state="disabled")
        self.status_var.set("중단 요청을 보냈습니다. 현재 작업이 정리되면 멈춥니다.")
        self._set_progress(self.progress_value.get(), "중단 요청 중")

    def build_manual_overrides_from_ui(self) -> dict[str, Any]:
        return {
            "google_queries_add": [],
            "google_queries_disable": [],
            "google_queries_replace": split_multiline_values(self.query_text.get("1.0", "end")),
            "topic_keywords_add": [],
            "topic_keywords_disable": [],
            "topic_keywords_replace": split_multiline_values(self.core_keyword_text.get("1.0", "end")),
            "phrases_add": [],
            "phrases_disable": [],
            "phrases_replace": [],
            "notes": "Saved from desktop app",
        }

    def _run_workflow_worker(self, profile: dict[str, Any], overrides: dict[str, Any]) -> None:
        connection = None
        try:
            def check_cancel() -> None:
                if self.cancel_event.is_set():
                    raise WorkflowCancelledError("사용자 요청으로 실행이 중단되었습니다.")

            def push_progress(percent: float, message: str) -> None:
                self.ui_queue.put(("progress", {"percent": percent, "message": message}))

            def handle_collect_progress(completed: int, total: int, source_name: str) -> None:
                if total <= 0:
                    push_progress(60, "기사 수집 완료")
                    return
                percent = 10 + (50 * (completed / total))
                label = source_name or "소스 준비 중"
                push_progress(percent, f"기사 수집 중 ({completed}/{total}) - {label}")

            def handle_analysis_progress(event_type: str, current: int, total: int, message: str) -> None:
                if event_type == "body_fetch":
                    if total <= 0:
                        push_progress(76, "본문 수집 대상 확인 중")
                        return
                    percent = 68 + (12 * (current / total))
                    label = message or "본문 수집"
                    push_progress(percent, f"본문 수집 중 ({current}/{total}) - {label}")
                    return

                stage_percent_map = {
                    0: 60,
                    1: 65,
                    2: 68,
                    3: 80,
                    4: 84,
                    5: 88,
                    6: 88,
                }
                push_progress(stage_percent_map.get(current, 88), message)

            def handle_daily_output_progress(completed: int, total: int, day_label: str) -> None:
                if total <= 0:
                    push_progress(100, "출력 생성 완료")
                    return
                percent = 94 + (6 * (completed / total))
                label = day_label or "출력 생성"
                push_progress(percent, f"일별 출력 생성 중 ({completed}/{total}) - {label}")

            session_paths = build_press_session_paths(profile, self.session_root)
            config = build_config_from_press_release(profile, overrides)
            push_progress(4, "세션 준비 중")

            connection = connect(session_paths["db_path"])
            ensure_schema(connection)
            seed_config_tables(connection, config, reset=True)
            clear_run_output_tables(connection)
            save_press_session_metadata(profile, config, session_paths, overrides)
            push_progress(10, "세션 설정 저장 완료")

            check_cancel()
            collect_result = collect_articles(
                connection,
                config,
                progress_callback=handle_collect_progress,
                cancel_callback=check_cancel,
            )
            push_progress(60, "기사 수집 완료")
            check_cancel()
            processed = run_analysis(
                connection,
                config,
                fetch_bodies=True,
                progress_callback=handle_analysis_progress,
                cancel_callback=check_cancel,
            )
            latest_briefing = session_paths["latest_briefing"]
            check_cancel()
            push_progress(90, "브리핑 생성 중")
            generate_briefing(connection, config, latest_briefing)
            analysis_now = get_analysis_now(config)
            check_cancel()
            push_progress(94, "일별 출력 준비 중")
            session_summary = build_session_daily_outputs(
                connection,
                profile,
                config,
                session_paths,
                analysis_now,
                progress_callback=handle_daily_output_progress,
                cancel_callback=check_cancel,
            )
            push_progress(100, "실행 완료")

            result = {
                "session_paths": session_paths,
                "session_summary": session_summary,
                "collect_result": collect_result,
                "processed_count": len(processed),
            }
            self.ui_queue.put(("run_complete", result))
        except WorkflowCancelledError as error:
            self.ui_queue.put(("run_cancelled", str(error)))
        except Exception:
            self.ui_queue.put(("run_error", traceback.format_exc()))
        finally:
            if connection is not None:
                connection.close()

    def open_session_dir(self) -> None:
        if not self.last_run_result:
            return
        safe_open_path(self.last_run_result["session_paths"]["session_dir"])

    def open_latest_csv(self) -> None:
        if not self.last_run_result:
            return
        safe_open_path(self.last_run_result["session_summary"]["latest_reference_csv"])

    def open_latest_briefing(self) -> None:
        if not self.last_run_result:
            return
        safe_open_path(self.last_run_result["session_summary"]["latest_briefing_path"])

    def _handle_run_complete(self, result: dict[str, Any]) -> None:
        self.last_run_result = result
        session_paths = result["session_paths"]
        session_summary = result["session_summary"]
        collect_result = result["collect_result"]
        processed_count = result["processed_count"]

        self.current_session_paths = session_paths
        self.result_var.set(
            f"후보 {collect_result['prepared_count']}건 수집, 신규 {collect_result['inserted_count']}건 적재, 최종 선별 {processed_count}건"
        )
        try:
            briefing_text = Path(session_summary["latest_briefing_path"]).read_text(encoding="utf-8")
        except FileNotFoundError:
            briefing_text = ""
        self._set_preview_text(briefing_text)
        self._set_output_buttons_enabled(True)
        self._set_busy(False)
        self._set_progress(100, "실행 완료")
        self.status_var.set("실행이 완료되었습니다. CSV 또는 세션 폴더를 열어 확인하십시오.")

    def _handle_run_error(self, trace_text: str) -> None:
        self._set_busy(False)
        self._set_progress(self.progress_value.get(), "오류 발생")
        self.status_var.set("실행 중 오류가 발생했습니다. 로그를 확인하십시오.")
        self._log(trace_text.rstrip())
        messagebox.showerror(APP_TITLE, "실행 중 오류가 발생했습니다. 아래 로그를 확인하십시오.")

    def _handle_run_cancelled(self, message: str) -> None:
        self.last_run_result = None
        self._set_busy(False)
        self._set_output_buttons_enabled(False)
        self._set_progress(self.progress_value.get(), "중단됨")
        self.status_var.set("실행이 중단되었습니다. 기사 검색을 누르면 처음부터 다시 실행합니다.")
        self._log(message)

    def _process_ui_queue(self) -> None:
        while True:
            try:
                event_type, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "log":
                self._log(payload)
            elif event_type == "progress":
                self._handle_progress(payload)
            elif event_type == "run_cancelled":
                self._handle_run_cancelled(payload)
            elif event_type == "run_complete":
                self._handle_run_complete(payload)
            elif event_type == "run_error":
                self._handle_run_error(payload)

        self.after(150, self._process_ui_queue)

    def _set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        self.run_button.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")
        if not busy:
            self.run_started_at = None

    def _handle_progress(self, payload: dict[str, Any]) -> None:
        percent = float(payload.get("percent", 0) or 0)
        message = collapse_whitespace(payload.get("message", "")) or "진행 중"
        self._set_progress(percent, message)

    def _set_progress(self, percent: float, message: str) -> None:
        bounded_percent = max(0.0, min(100.0, float(percent)))
        self.progress_value.set(bounded_percent)
        progress_text = f"진행률 {bounded_percent:.0f}%"
        if self.run_started_at and 0 < bounded_percent < 100:
            elapsed_seconds = max(0.0, time.monotonic() - self.run_started_at)
            remaining_seconds = elapsed_seconds * ((100.0 - bounded_percent) / bounded_percent)
            progress_text = f"{progress_text} | 예상 남은 시간 {self._format_duration(remaining_seconds)}"
        self.progress_detail_var.set(f"{message} | {progress_text}")

    def _format_duration(self, seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        minutes, remaining_seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
        return f"{minutes:02d}:{remaining_seconds:02d}"

    def _set_output_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.open_csv_button.configure(state=state)
        self.open_briefing_button.configure(state=state)
        self.open_session_button.configure(state=state)

    def _set_editor_values(self, widget: tk.Text, values: list[str], readonly: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(values))
        if readonly:
            widget.configure(state="disabled")

    def _set_preview_text(self, text: str) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        root_logger = logging.getLogger()
        if self.log_handler in root_logger.handlers:
            root_logger.removeHandler(self.log_handler)
        if self.file_log_handler in root_logger.handlers:
            root_logger.removeHandler(self.file_log_handler)
        self.destroy()
