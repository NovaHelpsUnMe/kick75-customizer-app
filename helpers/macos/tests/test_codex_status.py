import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from helpers.macos import codex_status


class CodexStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.global_state = self.root / "global.json"
        self.state_db = self.root / "state.sqlite"
        self.history_db = self.root / "history.sqlite"
        self.rollouts = {f"task-{number}": self.root / f"task-{number}.jsonl" for number in range(1, 5)}

        with closing(sqlite3.connect(self.state_db)) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT, archived INTEGER NOT NULL DEFAULT 0)"
            )
            connection.executemany(
                "INSERT INTO threads (id, title, rollout_path) VALUES (?, ?, ?)",
                [(task, f"Task {task[-1]}", str(path)) for task, path in self.rollouts.items()],
            )
            connection.commit()
        with closing(sqlite3.connect(self.history_db)) as connection:
            connection.execute(
                "CREATE TABLE thread_turns (thread_id TEXT, status TEXT, rollout_ordinal INTEGER)"
            )
            connection.commit()

    def tearDown(self):
        self.temporary.cleanup()

    def write_desktop_state(
        self, pins, unread=(), chatgpt=(), unified=(), current_pins=None, include_sidebar=True
    ):
        pinned_conversations = [
            {"conversation": {"id": thread_id, "title": title, "isTask": True}}
            for thread_id, title in chatgpt
        ]
        atom_state = {
            codex_status.UNIFIED_PIN_ORDER_KEY: list(unified),
            codex_status.CHATGPT_SIDEBAR_KEY: {
                "profile": {"pinnedConversations": pinned_conversations}
            },
            codex_status.UNREAD_KEY: {"local": list(unread)},
        }
        if include_sidebar:
            atom_state[codex_status.PIN_ORDER_KEY] = list(pins)
        state = {"electron-persisted-atom-state": atom_state}
        if current_pins is not None:
            state[codex_status.CURRENT_PIN_ORDER_KEY] = list(current_pins)
        self.global_state.write_text(json.dumps(state), encoding="utf-8")

    def write_rollout(self, task, payloads):
        self.rollouts[task].write_text(
            "".join(json.dumps({"type": "response_item", "payload": payload}) + "\n" for payload in payloads),
            encoding="utf-8",
        )

    def add_turns(self, rows):
        with closing(sqlite3.connect(self.history_db)) as connection:
            connection.executemany("INSERT INTO thread_turns VALUES (?, ?, ?)", rows)
            connection.commit()

    def test_packet_contains_four_status_codes(self):
        packet = codex_status.slot_packet(
            codex_status.VIA_CUSTOM_SET_VALUE,
            ["idle", "working", "complete", "attention"],
        )
        self.assertEqual(len(packet), codex_status.REPORT_LENGTH + 1)
        self.assertEqual(list(packet[1:8]), [0x07, 0x00, 0x81, 1, 2, 3, 4])

    def test_protected_hid_interface_reports_macOS_access_recovery(self):
        class ProtectedHid:
            @staticmethod
            def enumerate(_vendor_id, _product_id):
                return [{"usage_page": codex_status.RAW_USAGE_PAGE, "usage": codex_status.RAW_USAGE, "path": b"protected"}]

            class Device:
                def __init__(self, path):
                    raise OSError("unable to open device")

        with patch.object(codex_status, "hid", ProtectedHid):
            with self.assertRaisesRegex(codex_status.KeyboardUnavailable, "Input Monitoring"):
                codex_status.raw_hid_device()

    def test_status_stream_output_is_exactly_four_transport_states(self):
        slots = [
            codex_status.SlotState("task-1", "working"),
            codex_status.SlotState("task-2", "complete"),
            codex_status.SlotState("task-3", "idle"),
            codex_status.SlotState(None, "off"),
        ]
        self.assertEqual(",".join(slot.status for slot in slots), "working,complete,idle,off")

    def test_pinned_order_and_status_priority(self):
        tasks = list(self.rollouts)
        self.write_desktop_state(tasks, unread=["task-4"])
        self.add_turns(
            [
                ("task-1", "interrupted", 8),
                ("task-2", "inProgress", 4),
                ("task-3", "inProgress", 2),
                ("task-4", "completed", 9),
            ]
        )
        request = {
            "type": "custom_tool_call",
            "name": "request_user_input",
            "call_id": "question-1",
        }
        self.write_rollout("task-1", [request])
        self.write_rollout("task-2", [request])
        self.write_rollout("task-3", [])
        self.write_rollout("task-4", [])

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)
        self.assertEqual([slot.thread_id for slot in slots], tasks)
        self.assertEqual([slot.status for slot in slots], ["attention", "attention", "working", "complete"])

    def test_current_top_level_pinned_order_is_used(self):
        tasks = list(self.rollouts)
        self.write_desktop_state([], current_pins=tasks, include_sidebar=False)

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)

        self.assertEqual([slot.thread_id for slot in slots], tasks)

    def test_visible_sidebar_pins_win_over_stale_top_level_order(self):
        self.write_desktop_state(
            ["task-1", "task-3", "task-4"],
            current_pins=["task-1", "task-2", "task-3", "task-4"],
        )

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)

        self.assertEqual([slot.thread_id for slot in slots], ["task-1", "task-3", "task-4", None])

    def test_empty_visible_sidebar_does_not_fall_back_to_stale_top_level_order(self):
        self.write_desktop_state([], current_pins=list(self.rollouts))

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)

        self.assertEqual([slot.thread_id for slot in slots], [None, None, None, None])

    def test_archived_stale_pins_do_not_occupy_f_keys(self):
        tasks = list(self.rollouts)
        stale_archived = "task-archived"
        fifth_visible = "task-5"
        fifth_rollout = self.root / "task-5.jsonl"
        with closing(sqlite3.connect(self.state_db)) as connection:
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?)",
                (stale_archived, "Archived task", str(self.root / "archived.jsonl"), 1),
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?)",
                (fifth_visible, "Task 5", str(fifth_rollout), 0),
            )
            connection.commit()
        fifth_rollout.write_text("", encoding="utf-8")
        self.write_desktop_state([tasks[0], stale_archived, tasks[1], tasks[2], fifth_visible])

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)

        self.assertEqual(
            [slot.thread_id for slot in slots],
            [tasks[0], tasks[1], tasks[2], fifth_visible],
        )

    def test_pin_layout_waits_one_second_before_replacing_confirmed_slots(self):
        first = [
            codex_status.SlotState("task-1", "idle"),
            codex_status.SlotState("task-2", "complete"),
            codex_status.SlotState(None, "off"),
            codex_status.SlotState(None, "off"),
        ]
        replacement = [
            codex_status.SlotState("task-1", "working"),
            codex_status.SlotState("task-3", "idle"),
            codex_status.SlotState(None, "off"),
            codex_status.SlotState(None, "off"),
        ]
        stabilizer = codex_status.PinLayoutStabilizer()

        self.assertEqual(stabilizer.stabilize(first, 0.0), first)
        self.assertEqual(stabilizer.stabilize(replacement, 0.1), [
            codex_status.SlotState("task-1", "working"),
            first[1],
            first[2],
            first[3],
        ])
        self.assertEqual(stabilizer.stabilize(replacement, 0.9)[1], first[1])
        self.assertEqual(stabilizer.stabilize(replacement, 1.1), replacement)

    def test_stale_failed_turn_is_not_a_live_attention_signal(self):
        self.write_desktop_state(["task-1"])
        self.add_turns([("task-1", "failed", 1)])

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)

        self.assertEqual(slots[0].status, "idle")

    def test_answered_request_is_not_attention(self):
        self.write_desktop_state(["task-1"])
        self.add_turns([("task-1", "inProgress", 1)])
        self.write_rollout(
            "task-1",
            [
                {
                    "type": "custom_tool_call",
                    "name": "request_permissions",
                    "call_id": "permission-1",
                },
                {"type": "custom_tool_call_output", "call_id": "permission-1"},
            ],
        )
        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)
        self.assertEqual([slot.status for slot in slots], ["working", "off", "off", "off"])

    def test_idle_pinned_task_and_empty_slots(self):
        self.write_desktop_state(["task-1"])
        self.write_rollout("task-1", [])
        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)
        self.assertEqual([slot.status for slot in slots], ["idle", "off", "off", "off"])

    def test_unread_completion_stays_green(self):
        self.write_desktop_state(["task-1"], unread=[])
        self.add_turns([("task-1", "completed", 1)])
        signals = codex_status.RolloutSignals(completed=True)
        self.assertEqual(codex_status.derive_status(None, signals, unread=True), "complete")

    def test_completed_task_stays_green_after_opening(self):
        signals = codex_status.RolloutSignals(completed=True)
        self.assertEqual(codex_status.derive_status(None, signals, unread=False), "complete")

    def test_completed_turn_stays_green_without_unread_signal(self):
        turn = codex_status.TurnState("completed", 1)
        self.assertEqual(codex_status.derive_status(turn, codex_status.RolloutSignals()), "complete")

    def test_live_task_started_overrides_missing_history_turn(self):
        self.write_desktop_state(["task-1"])
        self.write_rollout("task-1", [{"type": "task_started"}])

        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)

        self.assertEqual(slots[0].status, "working")

    def test_live_rollout_cursor_keeps_working_until_completion(self):
        self.write_desktop_state(["task-1"])
        self.write_rollout("task-1", [{"type": "task_started"}])
        live_rollouts = codex_status.LiveRollouts()

        first = codex_status.current_slots(
            self.global_state, self.state_db, self.history_db, live_rollouts
        )
        with self.rollouts["task-1"].open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": "response_item", "payload": {"type": "reasoning"}}) + "\n")
        second = codex_status.current_slots(
            self.global_state, self.state_db, self.history_db, live_rollouts
        )
        with self.rollouts["task-1"].open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": "event_msg", "payload": {"type": "task_complete"}}) + "\n")
        third = codex_status.current_slots(
            self.global_state, self.state_db, self.history_db, live_rollouts
        )

        self.assertEqual([first[0].status, second[0].status, third[0].status], ["working", "working", "complete"])

    def test_uses_only_pinned_codex_tasks_in_shortcut_order(self):
        self.write_desktop_state(
            ["task-2", "task-1", "task-3"],
            chatgpt=[("chat-1", "ChatGPT task")],
            unified=["chatgpt:conversation:chat-1", "codex:thread:local:task-1"],
        )
        for task in ("task-1", "task-2", "task-3"):
            self.write_rollout(task, [])
        slots = codex_status.current_slots(self.global_state, self.state_db, self.history_db)
        self.assertEqual(
            [slot.thread_id for slot in slots],
            ["task-2", "task-1", "task-3", None],
        )
        self.assertEqual([slot.status for slot in slots], ["idle", "idle", "idle", "off"])


if __name__ == "__main__":
    unittest.main()
