import unittest

import pytest

from element_chat.chart import validate
from element_chat.config import load_configuration
from element_chat.support import CHART


class ChartTest(unittest.TestCase):
    def test_room_creation_policy_compiles(self) -> None:
        source = (CHART / "files" / "room_creation_policy.py").read_text()
        compile(source, "room_creation_policy.py", "exec")

    @pytest.mark.integration
    def test_chart_lints_and_renders(self) -> None:
        manifests = validate(*load_configuration()).split("\n---\n")
        hook = next(
            (
                m
                for m in manifests
                if "name: ess-synapse-check-config\n" in m and "kind: Job" in m
            ),
            None,
        )
        assert hook is not None, "the Synapse check-config hook is not rendered"
        # Hooks run before the chart's own resources exist, so a hook that mounts
        # one of them waits for it forever.
        for configmap in ("element-assets", "mas-translations", "synapse-policy"):
            self.assertTrue(
                f"name: {configmap}\n" not in hook,
                f"the hook mounts the ConfigMap {configmap}",
            )


if __name__ == "__main__":
    unittest.main()
