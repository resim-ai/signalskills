import textwrap
from pathlib import Path
import check_config as cc

GOOD = """
version: 1
topics:
  replay: {schema: {filename: video}}
  err: {schema: {t: float, err_m: float}}
  moment: {event: true, schema: {name: string, description: string, status: status, tags: "string[]", metrics: "metric[]"}}
metrics:
  Replay: {type: test, query_string: SELECT filename AS value FROM replay, template_type: system, template: video, skip_if_no_data: true, description: What ran.}
  Error: {type: test, query_string: "SELECT 'e' AS series, t, err_m FROM err", template_type: system, template: line, skip_if_no_data: true, description: Error over time (m).}
  Peak: {type: test, query_string: SELECT MAX(err_m) AS value FROM err, template_type: system, template: scalar, units: m, skip_if_no_data: true, description: Worst error.}
  A: {type: test, query_string: SELECT 1, template_type: system, template: table, skip_if_no_data: true, description: a.}
  B: {type: test, query_string: SELECT 1, template_type: system, template: histogram, skip_if_no_data: true, description: b.}
metrics sets:
  S: {metrics: [Replay, Error, Peak, A, B]}
"""


def check(tmp_path, text):
    p = tmp_path / "config.resim.yml"
    p.write_text(textwrap.dedent(text))
    return cc.violations(p)


def test_good_config_is_clean(tmp_path):
    assert check(tmp_path, GOOD) == []


def test_missing_skip_if_no_data(tmp_path):
    assert any("skip_if_no_data" in v for v in check(tmp_path, GOOD.replace("skip_if_no_data: true, description: b.", "description: b.")))


def test_unknown_template(tmp_path):
    assert any("bar_chart" in v for v in check(tmp_path, GOOD.replace("template: histogram", "template: bar_chart")))


def test_unknown_topic_type(tmp_path):
    assert any("double" in v for v in check(tmp_path, GOOD.replace("t: float", "t: double")))


def test_event_topic_needs_event_schema(tmp_path):
    assert any("moment" in v for v in check(tmp_path, GOOD.replace("status: status, ", "")))


def test_too_few_test_metrics(tmp_path):
    assert any("5-20" in v for v in check(tmp_path, GOOD.replace("[Replay, Error, Peak, A, B]", "[Replay, Error]")))


def test_video_must_lead_when_present(tmp_path):
    assert any("first" in v for v in check(tmp_path, GOOD.replace("[Replay, Error, Peak, A, B]", "[Error, Replay, Peak, A, B]")))


def test_scalar_needs_units(tmp_path):
    assert any("units" in v for v in check(tmp_path, GOOD.replace("units: m, ", "")))


def test_long_description(tmp_path):
    assert any("description" in v for v in check(tmp_path, GOOD.replace("description: a.", "description: " + "x" * 200)))


def test_set_references_unknown_metric(tmp_path):
    assert any("Nope" in v for v in check(tmp_path, GOOD.replace("B]", "Nope]")))


def test_custom_template_file_must_exist(tmp_path):
    text = GOOD.replace("template_type: system, template: table", "template_type: custom, template_file: raw.liquid")
    assert any("raw.liquid" in v for v in check(tmp_path, text))
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "raw.liquid").write_text("")
    assert check(tmp_path, text) == []


def test_bigint_rejected_because_the_sdk_emitter_rejects_it(tmp_path):
    assert any("bigint" in v for v in check(tmp_path, GOOD.replace("t: float", "t: bigint")))


def test_dashboard_only_set_needs_no_test_metrics(tmp_path):
    text = GOOD.replace("metrics sets:", "  Trend: {type: dashboard, query_string: SELECT 1, template_type: system, template: line, skip_if_no_data: true, description: t.}\nmetrics sets:\n  Trends: {metrics: [Trend]}")
    assert check(tmp_path, text) == []


GATE = """
  Margin: {type: test, query_string: SELECT err_m AS value FROM err, template_type: system, template: scalar, units: m, skip_if_no_data: SKIP, description: Margin., status: {query_string: "SELECT 1 FROM err WHERE err_m > ?", block: 0.5}}
"""


def _with_gate(skip):
    return GOOD.replace("metrics sets:", GATE.replace("SKIP", skip).strip("\n") + "\nmetrics sets:").replace("[Replay, Error, Peak, A, B]", "[Replay, Error, Peak, A, B, Margin]")


def test_skip_false_is_allowed(tmp_path):
    assert check(tmp_path, GOOD.replace("skip_if_no_data: true, description: b.", "skip_if_no_data: false, description: b.")) == []


def test_status_checked_metric_must_not_skip(tmp_path):
    assert any("status" in v and "skip_if_no_data" in v for v in check(tmp_path, _with_gate("true")))


def test_status_checked_metric_with_skip_false_is_clean(tmp_path):
    assert check(tmp_path, _with_gate("false")) == []
