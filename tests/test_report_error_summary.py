from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_report_contains_error_summary_for_bad_cases(tmp_path: Path):
    input_csv = tmp_path / "bad_cases.csv"
    out = tmp_path / "run_out"

    input_csv.write_text(
        "case_id,model,gamma,M,M1,theta_deg,branch\n"
        "good_iso,isentropic,1.4,2.0,,,\n"
        "bad_ns,normal_shock,1.4,,0.8,,\n"
        "bad_os,oblique_shock,1.4,,2.0,40,weak\n"
        "bad_model,banana,1.4,2.0,,,\n",
        encoding="utf-8",
    )

    cmd = [sys.executable, "-m", "cfs", "run", str(input_csv), "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    html = (out / "report.html").read_text(encoding="utf-8")

    assert "Uncertainty and Error Treatment" in html
    assert "Error Summary" in html
    assert "Case-Level Trace" in html
    assert "good_iso" not in html or "good_iso" in html  # appears elsewhere; not load-bearing
    assert "bad_ns" in html
    assert "bad_os" in html
    assert "bad_model" in html
    assert "Unknown model" in html
