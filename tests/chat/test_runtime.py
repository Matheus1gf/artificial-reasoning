import unittest
from unittest.mock import patch

from src.chat.provider import Settings
from src.chat.runtime import start_local_runtime, stop_local_runtime


class RuntimeTests(unittest.TestCase):
    def test_symbolic_mode_does_not_start_or_contact_a_model(self):
        with patch("src.chat.runtime.runtime_available") as available, patch("src.chat.runtime.subprocess.Popen") as spawn:
            self.assertIsNone(start_local_runtime(Settings()))
            available.assert_not_called()
            spawn.assert_not_called()

    def test_external_endpoint_does_not_start_a_local_process(self):
        settings = Settings(provider="ollama", model="test", base_url="https://my-model.example")
        with patch("src.chat.runtime.runtime_available") as available, patch("src.chat.runtime.subprocess.Popen") as spawn:
            self.assertIsNone(start_local_runtime(settings))
            available.assert_not_called()
            spawn.assert_not_called()

    def test_existing_local_server_is_reused_and_not_owned(self):
        with patch("src.chat.runtime.Path.is_file", return_value=True), patch("src.chat.runtime.runtime_available", return_value=True), patch("src.chat.runtime.subprocess.Popen") as spawn:
            owned = start_local_runtime(Settings(provider="ollama", model="test"))
            self.assertIsNone(owned)
            stop_local_runtime(owned)
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
