"""Lancia i test Node (tests/js/*.test.js), così un solo `pytest` copre anche il JS."""
import subprocess

from test_app_parita import KIT, trova_node

import pytest


def test_node_test_verdi():
    node = trova_node()
    if not node:
        pytest.skip("Node.js non trovato")
    # reporter fisso: senza terminale Node 22 sceglie TAP ("# fail 0"), Node 24 spec ("ℹ fail 0")
    r = subprocess.run([node, "--test", "--test-reporter=spec", "tests/js/*.test.js"],
                       cwd=KIT, capture_output=True, timeout=120)
    uscita = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, uscita[-3000:]
    assert "ℹ fail 0" in uscita
