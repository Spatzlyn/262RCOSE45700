"""v1.1 A/B handoff runs: first responses stay invalid; the fence-stripped diagnostic never changes them."""
from backend.app import store
from backend.tools.export_v11_scoring import score, strip_fence

RUNS = ["v11_a_e18f74ffcc", "v11_b_9895a83702"]


def test_strip_fence_only_removes_outer_fence():
    assert strip_fence("```json\n{\"a\": 1}\n```\n") == '{"a": 1}'
    assert strip_fence('{"a": "```"}') == '{"a": "```"}'


def test_official_first_responses_are_invalid_and_scored_against_reviewed_gt():
    for run in RUNS:
        body = score(run, diagnostic=False)
        assert body["summary"]["prediction_status_counts"] == {"invalid": 6}
        assert {r["reference_version"] for r in body["items"]} == {"1.1-pilot6-reviewed-20261125"}
        assert all(r["scored"] and r["action_eval"]["pass_status"] == "excluded" for r in body["items"])
        assert body["summary"]["metrics"]["v1_valid"]["n"] == 6


def test_diagnostic_matches_model_team_offline_check():
    for run in RUNS:
        body = score(run, diagnostic=True)
        valid = sorted(r["item_id"] for r in body["items"] if r["prediction_status"] == "valid")
        assert valid == ["pilot_003", "pilot_004"]
    assert store.predictions(RUNS[0])["pilot_001"]["output_text"].lstrip().startswith("```")
