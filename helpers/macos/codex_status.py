#!/usr/bin/env python3
"""Mirror the first four pinned Codex tasks on the Kick75 F1-F4 LEDs.

The bridge is deliberately read-only with respect to Codex. It reads local
desktop state, derives one status per pinned task, and sends a runtime-only VIA
custom value to the keyboard over wired USB. No task, mapping, Codex setting,
or keyboard EEPROM value is changed.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Iterable

try:
    import hid  # type: ignore
except ModuleNotFoundError:
    hid = None


VENDOR_ID: Final = 0x19F5
PRODUCT_ID: Final = 0x32D5
RAW_USAGE_PAGE: Final = 0xFF60
RAW_USAGE: Final = 0x61
REPORT_LENGTH: Final = 32

VIA_CUSTOM_SET_VALUE: Final = 0x07
VIA_CUSTOM_GET_VALUE: Final = 0x08
VIA_CUSTOM_CHANNEL: Final = 0x00
CODEX_SLOT_STATUS_VIA_VALUE: Final = 0x81
SLOT_COUNT: Final = 4

STATUS_CODES: Final = {
    "off": 0,
    "idle": 1,
    "working": 2,
    "complete": 3,
    "attention": 4,
    "error": 5,
}
CODE_TO_STATUS: Final = {value: name for name, value in STATUS_CODES.items()}

DEFAULT_GLOBAL_STATE: Final = Path.home() / ".codex" / ".codex-global-state.json"
DEFAULT_STATE_DB: Final = Path.home() / ".codex" / "state_5.sqlite"
DEFAULT_HISTORY_DB: Final = Path.home() / ".codex" / "thread_history_1.sqlite"
NATIVE_STATUS_APP: Final = Path.home() / "Applications" / "Kick75 Codex Status.app"

PIN_ORDER_KEY: Final = "app-server-pinned-thread-order-v1"
CURRENT_PIN_ORDER_KEY: Final = "pinned-thread-ids"
UNIFIED_PIN_ORDER_KEY: Final = "unified-sidebar-pinned-order-v1"
CHATGPT_SIDEBAR_KEY: Final = "chatgpt-sidebar-state-v1"
UNREAD_KEY: Final = "unread-thread-ids-by-host-v1"
ATTENTION_TOOL_NAMES: Final = {"request_user_input", "request_permissions"}
ATTENTION_EVENT_TYPES: Final = {
    "request_user_input",
    "request_permissions",
    "exec_approval_request",
    "apply_patch_approval_request",
    "elicitation_request",
}
TERMINAL_EVENT_TYPES: Final = {"task_complete", "turn_aborted", "turn_cancelled"}


class StateUnavailable(RuntimeError):
    """A required local Codex state source is temporarily unavailable."""


class KeyboardUnavailable(RuntimeError):
    """The Kick75 Raw HID interface is not currently reachable."""


@dataclass(frozen=True)
class TurnState:
    status: str
    rollout_ordinal: int


@dataclass(frozen=True)
class SlotState:
    thread_id: str | None
    status: str
    title: str = ""


@dataclass(frozen=True)
class PinnedTask:
    source: str
    thread_id: str
    title: str = ""


@dataclass(frozen=True)
class RolloutSignals:
    needs_attention: bool = False
    working: bool = False
    completed: bool = False
    error: bool = False


@dataclass
class RolloutCursor:
    """Transient read-only state for one append-only Codex rollout."""

    offset: int = 0
    remainder: bytes = b""
    pending: set[str] = field(default_factory=set)
    anonymous_pending: bool = False
    working: bool = False
    completed: bool = False
    error: bool = False


@dataclass
class PinLayoutStabilizer:
    """Hold a confirmed visible-pin layout through a brief desktop-state rewrite."""

    confirmation_seconds: float = 1.0
    confirmed_slots: list[SlotState] | None = None
    candidate_ids: tuple[str | None, ...] | None = None
    candidate_started_at: float = 0.0

    def stabilize(self, slots: list[SlotState], now: float) -> list[SlotState]:
        thread_ids = tuple(slot.thread_id for slot in slots)

        if self.confirmed_slots is None:
            self.confirmed_slots = slots
            return slots

        confirmed_ids = tuple(slot.thread_id for slot in self.confirmed_slots)
        if thread_ids == confirmed_ids:
            self.candidate_ids = None
            self.confirmed_slots = slots
            return slots

        if thread_ids != self.candidate_ids:
            self.candidate_ids = thread_ids
            self.candidate_started_at = now
            return self._confirmed_slots_with_live_statuses(slots)

        if now - self.candidate_started_at < self.confirmation_seconds:
            return self._confirmed_slots_with_live_statuses(slots)

        self.confirmed_slots = slots
        self.candidate_ids = None
        return slots

    def _confirmed_slots_with_live_statuses(self, slots: list[SlotState]) -> list[SlotState]:
        assert self.confirmed_slots is not None
        current_by_id = {slot.thread_id: slot for slot in slots if slot.thread_id is not None}
        return [current_by_id.get(slot.thread_id, slot) for slot in self.confirmed_slots]


def slot_packet(command: int, statuses: Iterable[str] | None = None) -> bytes:
    """Build the macOS hidapi report-ID byte plus the 32-byte VIA body."""
    payload = bytearray(REPORT_LENGTH)
    payload[0] = command
    payload[1] = VIA_CUSTOM_CHANNEL
    payload[2] = CODEX_SLOT_STATUS_VIA_VALUE
    if statuses is not None:
        status_list = list(statuses)
        if len(status_list) != SLOT_COUNT or any(name not in STATUS_CODES for name in status_list):
            raise ValueError("Exactly four valid slot statuses are required.")
        payload[3:7] = bytes(STATUS_CODES[name] for name in status_list)
    return bytes([0]) + bytes(payload)


def raw_hid_device():
    """Open only the Kick75 VIA/Raw HID interface, never its typing interface."""
    if hid is None:
        raise KeyboardUnavailable(
            "The 'hid' package is missing. Use ~/.qmk_venv/bin/python for keyboard access."
        )
    matches = [
        device
        for device in hid.enumerate(VENDOR_ID, PRODUCT_ID)
        if device.get("usage_page") == RAW_USAGE_PAGE and device.get("usage") == RAW_USAGE
    ]
    if not matches:
        raise KeyboardUnavailable(
            "Kick75 VIA Raw HID was not found. Connect the keyboard by wired USB."
        )

    # macOS can enumerate a protected HID device while refusing to open it.
    # Do not treat that as a missing keyboard: the monitor should stay alive,
    # retry after a reconnect, and name the one-time recovery step accurately.
    open_errors = []
    for device in matches:
        try:
            return hid.Device(path=device["path"])
        # hidapi uses its own HIDException on macOS, rather than OSError.
        # Keep the catch local to opening the selected device so unrelated
        # programming errors are never hidden by the reconnect loop.
        except Exception as error:
            open_errors.append(str(error))

    detail = "; ".join(error for error in open_errors if error) or "access was denied"
    raise KeyboardUnavailable(
        "macOS is blocking the Kick75 status-control channel "
        f"({detail}). Quit VIA if it is open, then allow the Kick75 status helper "
        "under System Settings > Privacy & Security > Input Monitoring. "
        "The bridge will reconnect automatically once access is restored."
    )


def send_slot_statuses(statuses: list[str]) -> None:
    interface = raw_hid_device()
    try:
        interface.write(slot_packet(VIA_CUSTOM_SET_VALUE, statuses))
        response = list(interface.read(REPORT_LENGTH, timeout=1000))
    finally:
        interface.close()
    expected = [
        VIA_CUSTOM_SET_VALUE,
        VIA_CUSTOM_CHANNEL,
        CODEX_SLOT_STATUS_VIA_VALUE,
        *(STATUS_CODES[name] for name in statuses),
    ]
    if len(response) != REPORT_LENGTH or response[:7] != expected:
        raise KeyboardUnavailable(f"Kick75 did not confirm the status update: {response!r}")


def query_slot_statuses() -> list[str]:
    interface = raw_hid_device()
    try:
        interface.write(slot_packet(VIA_CUSTOM_GET_VALUE))
        response = list(interface.read(REPORT_LENGTH, timeout=1000))
    finally:
        interface.close()
    expected = [VIA_CUSTOM_GET_VALUE, VIA_CUSTOM_CHANNEL, CODEX_SLOT_STATUS_VIA_VALUE]
    if len(response) != REPORT_LENGTH or response[:3] != expected:
        raise KeyboardUnavailable(f"Kick75 did not confirm the status query: {response!r}")
    try:
        return [CODE_TO_STATUS[value] for value in response[3:7]]
    except KeyError as error:
        raise KeyboardUnavailable(f"Kick75 returned an unknown status value: {error.args[0]}") from error


def open_readonly_database(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise StateUnavailable(f"Codex state was not found at {path}")
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=1.0)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA busy_timeout = 1000")
        return connection
    except sqlite3.Error as error:
        raise StateUnavailable(f"Codex state is temporarily unavailable at {path}: {error}") from error


def read_desktop_state(path: Path) -> tuple[list[PinnedTask | None], set[str]]:
    try:
        raw_state = json.loads(path.read_text(encoding="utf-8"))
        atom_state = raw_state["electron-persisted-atom-state"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise StateUnavailable(f"Codex desktop state is temporarily unavailable at {path}: {error}") from error

    # The app-server list is the persisted source that matches the visible
    # Codex sidebar. The top-level list may retain a removed pin temporarily,
    # so use it only when the sidebar source is absent, never as a merge.
    sidebar_pins = atom_state.get(PIN_ORDER_KEY)
    codex_value = sidebar_pins if isinstance(sidebar_pins, list) else raw_state.get(CURRENT_PIN_ORDER_KEY, [])
    codex_tasks = [
        PinnedTask("codex", value)
        for value in codex_value
        if isinstance(value, str) and value
    ]

    # F1-F4 send Codex's native Command+1 through Command+4 shortcuts. Those
    # actions can open local Codex tasks, but cannot open ChatGPT conversations
    # in the unified sidebar. Match their exact pinned Codex source and order.
    unread_value = atom_state.get(UNREAD_KEY, {})
    unread_local = unread_value.get("local", []) if isinstance(unread_value, dict) else []
    unread = {value for value in unread_local if isinstance(value, str)}
    # Do not truncate here. The persisted pin list can temporarily retain
    # archived tasks; current_slots filters those before assigning F1-F4.
    return codex_tasks, unread


def latest_turns(history_db: Path, thread_ids: list[str]) -> dict[str, TurnState]:
    if not thread_ids:
        return {}
    placeholders = ",".join("?" for _ in thread_ids)
    query = f"""
        SELECT thread_id, status, rollout_ordinal
        FROM thread_turns
        WHERE thread_id IN ({placeholders})
        ORDER BY thread_id, rollout_ordinal DESC
    """
    try:
        with closing(open_readonly_database(history_db)) as connection:
            rows = connection.execute(query, thread_ids).fetchall()
    except sqlite3.Error as error:
        raise StateUnavailable(f"Could not read Codex task history: {error}") from error

    latest: dict[str, TurnState] = {}
    for thread_id, status, rollout_ordinal in rows:
        if thread_id not in latest:
            latest[thread_id] = TurnState(str(status), int(rollout_ordinal))
    return latest


def thread_metadata(state_db: Path, thread_ids: list[str]) -> dict[str, tuple[str, Path, bool]]:
    if not thread_ids:
        return {}
    placeholders = ",".join("?" for _ in thread_ids)
    try:
        with closing(open_readonly_database(state_db)) as connection:
            rows = connection.execute(
                f"SELECT id, title, rollout_path, archived FROM threads WHERE id IN ({placeholders})",
                thread_ids,
            ).fetchall()
    except sqlite3.Error as error:
        raise StateUnavailable(f"Could not read Codex task metadata: {error}") from error
    return {
        thread_id: (title or "", Path(rollout_path), bool(archived))
        for thread_id, title, rollout_path, archived in rows
    }


def _rollout_records(path: Path):
    """Yield valid JSONL records from a task rollout, read-only."""
    if not path.is_file():
        return
    try:
        with path.open("rb") as stream:
            for raw_line in stream:
                try:
                    yield json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
    except OSError:
        return


def apply_rollout_record(cursor: RolloutCursor, record: object) -> None:
    """Apply one verified rollout record to a task's current live state."""
    if not isinstance(record, dict):
        return
    record_type = record.get("type")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return

    payload_type = payload.get("type")
    if record_type == "response_item":
        call_id = payload.get("call_id") or payload.get("id")
        name = payload.get("name")
        if payload_type in {"custom_tool_call", "function_call"} and name in ATTENTION_TOOL_NAMES:
            if call_id:
                cursor.pending.add(str(call_id))
            else:
                cursor.anonymous_pending = True
        elif payload_type in {"custom_tool_call_output", "function_call_output"}:
            if call_id:
                cursor.pending.discard(str(call_id))
            else:
                cursor.anonymous_pending = False

    if payload_type == "task_started":
        cursor.pending.clear()
        cursor.anonymous_pending = False
        cursor.completed = False
        cursor.error = False
        cursor.working = True
    elif payload_type in ATTENTION_EVENT_TYPES:
        request_id = payload.get("call_id") or payload.get("request_id") or payload.get("id")
        if request_id:
            cursor.pending.add(str(request_id))
        else:
            cursor.anonymous_pending = True
    elif payload_type == "task_complete":
        cursor.pending.clear()
        cursor.anonymous_pending = False
        cursor.completed = True
        cursor.error = False
        cursor.working = False
    elif payload_type in {"turn_aborted", "turn_cancelled"}:
        cursor.pending.clear()
        cursor.anonymous_pending = False
        cursor.completed = False
        cursor.error = True
        cursor.working = False
    elif payload_type in {"server_request_resolved", "approval_resolved", "elicitation_resolved"}:
        request_id = payload.get("call_id") or payload.get("request_id") or payload.get("id")
        if request_id:
            cursor.pending.discard(str(request_id))
        else:
            cursor.anonymous_pending = False


def cursor_signals(cursor: RolloutCursor) -> RolloutSignals:
    return RolloutSignals(
        bool(cursor.pending) or cursor.anonymous_pending,
        cursor.working,
        cursor.completed,
        cursor.error,
    )


def rollout_signals(path: Path) -> RolloutSignals:
    """Read a complete rollout once for diagnostics and stateless callers."""
    cursor = RolloutCursor()
    for record in _rollout_records(path):
        apply_rollout_record(cursor, record)
    return cursor_signals(cursor)


class LiveRollouts:
    """Incrementally follow rollouts so active tasks never wait on history sync."""

    def __init__(self) -> None:
        self.cursors: dict[Path, RolloutCursor] = {}

    def signals(self, path: Path) -> RolloutSignals:
        if not path.is_file():
            return RolloutSignals()
        cursor = self.cursors.setdefault(path, RolloutCursor())
        try:
            if path.stat().st_size < cursor.offset:
                cursor = RolloutCursor()
                self.cursors[path] = cursor
            with path.open("rb") as stream:
                stream.seek(cursor.offset)
                data = cursor.remainder + stream.read()
                cursor.offset = stream.tell()
        except OSError:
            return cursor_signals(cursor)

        lines = data.splitlines(keepends=True)
        cursor.remainder = b""
        if lines and not lines[-1].endswith(b"\n"):
            cursor.remainder = lines.pop()
        for raw_line in lines:
            try:
                apply_rollout_record(cursor, json.loads(raw_line))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return cursor_signals(cursor)


def derive_status(
    turn: TurnState | None,
    signals: RolloutSignals,
    unread: bool = False,
) -> str:
    """Apply the approved priority: attention > working > complete > idle.

    Codex desktop's transient unread list is not a reliable acknowledgement
    signal: it can disappear while a finished task has not been reviewed.
    Keep completion green instead. A new turn takes priority and changes the
    key to blue while it is working, then green again when it finishes.
    """
    if signals.needs_attention:
        return "attention"
    if signals.working or (turn and turn.status == "inProgress"):
        return "working"
    if (turn and turn.status == "completed") or signals.completed:
        # Do not clear green from an unreliable unread-state refresh.
        # ``unread`` remains accepted for compatibility with older state files.
        return "complete"
    return "idle"


def current_slots(
    global_state: Path,
    state_db: Path,
    history_db: Path,
    live_rollouts: LiveRollouts | None = None,
) -> list[SlotState]:
    persisted_tasks, unread = read_desktop_state(global_state)
    persisted_ids = [task.thread_id for task in persisted_tasks if task.source == "codex"]
    metadata = thread_metadata(state_db, persisted_ids)

    # The desktop pin-order fallback can lag after a task is archived. Archived
    # tasks are not visible pins and must never occupy a physical F-key slot.
    active_tasks = [
        task
        for task in persisted_tasks
        if not metadata.get(task.thread_id, (task.title, Path(), False))[2]
    ][:SLOT_COUNT]
    pinned_tasks: list[PinnedTask | None] = active_tasks + [None] * (SLOT_COUNT - len(active_tasks))
    codex_ids = [task.thread_id for task in active_tasks]
    turns = latest_turns(history_db, codex_ids)

    result: list[SlotState] = []
    for task in pinned_tasks:
        if task is None:
            result.append(SlotState(None, "off"))
            continue
        title, rollout_path, _ = metadata.get(task.thread_id, (task.title, Path(), False))
        signals = (
            live_rollouts.signals(rollout_path)
            if live_rollouts is not None and rollout_path != Path()
            else rollout_signals(rollout_path) if rollout_path != Path() else RolloutSignals()
        )
        result.append(
            SlotState(
                task.thread_id,
                derive_status(turns.get(task.thread_id), signals, task.thread_id in unread),
                title,
            )
        )
    return result


def format_slots(slots: list[SlotState]) -> str:
    lines = []
    for index, slot in enumerate(slots, start=1):
        label = slot.title.strip().splitlines()[0][:64] if slot.title else slot.thread_id or "unassigned"
        lines.append(f"F{index}: {slot.status:<9} {label}")
    return "\n".join(lines)


def run_monitor(
    global_state: Path,
    state_db: Path,
    history_db: Path,
    interval: float,
    once: bool,
) -> None:
    last_sent: list[str] | None = None
    last_thread_ids: list[str | None] | None = None
    last_error: str | None = None
    last_error_at = 0.0
    live_rollouts = LiveRollouts()
    pin_layout = PinLayoutStabilizer()

    while True:
        try:
            slots = pin_layout.stabilize(
                current_slots(global_state, state_db, history_db, live_rollouts), time.monotonic()
            )
            statuses = [slot.status for slot in slots]
            thread_ids = [slot.thread_id for slot in slots]

            # The keyboard acknowledges green by physical F-key position. When
            # a different pinned task replaces a slot, briefly mark that slot
            # working before its real state so the previous task's acknowledgement
            # cannot make a new completed task appear white.
            if last_thread_ids is None or thread_ids != last_thread_ids:
                reset_statuses = statuses.copy()
                for slot, thread_id in enumerate(thread_ids):
                    changed_task = last_thread_ids is None or thread_id != last_thread_ids[slot]
                    if changed_task and thread_id is not None and statuses[slot] == "complete":
                        reset_statuses[slot] = "working"
                if reset_statuses != statuses:
                    send_slot_statuses(reset_statuses)
            if statuses != last_sent or thread_ids != last_thread_ids:
                send_slot_statuses(statuses)
                last_sent = statuses
                last_thread_ids = thread_ids
                print(format_slots(slots), flush=True)
            last_error = None
        except (StateUnavailable, KeyboardUnavailable, OSError, sqlite3.Error) as error:
            now = time.monotonic()
            message = str(error)
            if message != last_error or now - last_error_at >= 60:
                print(f"Kick75 status bridge waiting: {message}", file=sys.stderr, flush=True)
                last_error = message
                last_error_at = now
            if once:
                raise SystemExit(1) from error

        if once:
            return
        time.sleep(interval)


def run_status_stream(
    global_state: Path,
    state_db: Path,
    history_db: Path,
    interval: float,
) -> None:
    """Continuously emit derived statuses for the native Kick75 helper.

    This path deliberately never opens the keyboard. Keeping the Codex-state
    reader separate lets the signed macOS helper own the protected Raw HID
    channel while this process stays read-only with respect to both systems.
    """
    last_sent: list[str] | None = None
    last_emitted_at = 0.0
    last_error: str | None = None
    last_error_at = 0.0
    live_rollouts = LiveRollouts()
    pin_layout = PinLayoutStabilizer()

    while True:
        try:
            slots = pin_layout.stabilize(
                current_slots(global_state, state_db, history_db, live_rollouts), time.monotonic()
            )
            statuses = [slot.status for slot in slots]
            now = time.monotonic()
            # Re-emit unchanged states periodically so a native status helper
            # can recover after a USB/HID reconnect without waiting for the
            # next Codex task change.
            if statuses != last_sent or now - last_emitted_at >= 2.0:
                print(",".join(statuses), flush=True)
                last_sent = statuses
                last_emitted_at = now
            last_error = None
        except (StateUnavailable, sqlite3.Error) as error:
            now = time.monotonic()
            message = str(error)
            if message != last_error or now - last_error_at >= 60:
                print(f"Kick75 status reader waiting: {message}", file=sys.stderr, flush=True)
                last_error = message
                last_error_at = now
        time.sleep(interval)


def wait_for_native_status_helper(interval: float) -> None:
    """Keep the legacy Python launch agent idle after native installation.

    The signed macOS helper now owns the protected HID connection. Leaving the
    old ``--monitor`` process alive but idle prevents its KeepAlive job from
    repeatedly requesting the same keyboard interface.
    """
    print("Kick75 native status helper owns the keyboard connection.", flush=True)
    while True:
        time.sleep(max(interval, 60.0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--monitor", action="store_true", help="continuously mirror pinned Codex tasks")
    actions.add_argument("--get-slots", action="store_true", help="read the four current keyboard LED states")
    actions.add_argument("--slots", metavar="S1,S2,S3,S4", help="send four explicit visual-test states")
    actions.add_argument("--diagnose", action="store_true", help="show derived task states without using the keyboard")
    actions.add_argument(
        "--stream-statuses",
        action="store_true",
        help="continuously emit four statuses for the native Kick75 helper",
    )
    parser.add_argument("--once", action="store_true", help="with --monitor, send one update and exit")
    parser.add_argument("--interval", type=float, default=0.5, help="monitor interval in seconds (default: 0.5)")
    parser.add_argument("--global-state", type=Path, default=DEFAULT_GLOBAL_STATE, help=argparse.SUPPRESS)
    parser.add_argument("--state-db", type=Path, default=DEFAULT_STATE_DB, help=argparse.SUPPRESS)
    parser.add_argument("--history-db", type=Path, default=DEFAULT_HISTORY_DB, help=argparse.SUPPRESS)
    return parser


def parse_manual_slots(value: str) -> list[str]:
    statuses = [part.strip().lower() for part in value.split(",")]
    if len(statuses) != SLOT_COUNT or any(name not in STATUS_CODES for name in statuses):
        choices = ", ".join(STATUS_CODES)
        raise SystemExit(f"--slots needs four comma-separated states chosen from: {choices}")
    return statuses


def main() -> None:
    args = build_parser().parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero.")

    if args.get_slots:
        print(", ".join(query_slot_statuses()))
    elif args.slots:
        statuses = parse_manual_slots(args.slots)
        send_slot_statuses(statuses)
        print(f"Kick75 work lanes: {', '.join(statuses)}")
    elif args.diagnose:
        print(format_slots(current_slots(args.global_state, args.state_db, args.history_db)))
    elif args.stream_statuses:
        run_status_stream(args.global_state, args.state_db, args.history_db, args.interval)
    elif NATIVE_STATUS_APP.exists() and not args.once:
        wait_for_native_status_helper(args.interval)
    else:
        run_monitor(args.global_state, args.state_db, args.history_db, args.interval, args.once)


if __name__ == "__main__":
    main()

