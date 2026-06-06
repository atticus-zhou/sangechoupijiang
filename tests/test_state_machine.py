import unittest

from src.core.state_machine import IllegalTransitionError, StateMachine
from src.data.schemas import AgentId, SystemState


class StateMachineTests(unittest.TestCase):
    def test_valid_transition_is_recorded(self):
        state = StateMachine()

        transition = state.transition(
            SystemState.PLANNING,
            "start planning",
            AgentId.ZHONGSHU,
        )

        self.assertEqual(state.current_state, SystemState.PLANNING)
        self.assertEqual(transition.from_state, SystemState.RECEIVED)
        self.assertEqual(transition.to_state, SystemState.PLANNING)
        self.assertEqual(len(state.state_history), 1)

    def test_invalid_transition_is_rejected(self):
        state = StateMachine()

        with self.assertRaises(IllegalTransitionError):
            state.transition(SystemState.COMPLETED, "skip everything", AgentId.SHANGSHU)

    def test_terminal_state_is_detected(self):
        state = StateMachine()
        state.transition(SystemState.TERMINATED, "stop", AgentId.HUMAN)

        self.assertTrue(state.is_terminal())


if __name__ == "__main__":
    unittest.main()
