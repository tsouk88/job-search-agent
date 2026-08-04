"""Deterministic verifier for the seniority/keyword exclusion task.

The expected sets are written by hand from the frozen fixtures. This file never
calls filter_jobs — a verifier that recomputed the answer with the code under
test would grade that code against itself and always pass.
"""

import json
import os
from pathlib import Path

import pytest

OUTPUT = Path(os.environ.get("OUTPUT_JSON", "/app/output.json"))
PREFILTER = Path(os.environ.get("PREFILTER_JSON", "/app/prefilter.json"))
EXPECTED = Path(os.environ.get("EXPECTED_JSON", "/tests/expected.json"))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def expected():
    return load(EXPECTED)


@pytest.fixture(scope="module")
def output():
    assert OUTPUT.exists(), f"{OUTPUT} was never written"
    data = load(OUTPUT)
    assert isinstance(data, list), f"expected a JSON list, got {type(data).__name__}"
    assert all(isinstance(job, dict) for job in data)
    return data


@pytest.fixture(scope="module")
def prefilter():
    assert PREFILTER.exists(), f"{PREFILTER} was never written"
    return load(PREFILTER)


def urls(jobs):
    return {job.get("apply_url") for job in jobs}


def text_of(job):
    return " ".join(
        str(job.get(field, "")) for field in ("position", "description", "location")
    ).lower()


def test_the_filter_saw_the_frozen_listings(prefilter, expected):
    """Guards the environment, not the agent: if the fixtures or the fan-out
    changed, every other assertion below is measuring something else."""
    assert urls(prefilter) == set(expected["keep"]) | set(expected["drop"])


def test_no_seniority_match_in_a_title_survived(output):
    offenders = [j["position"] for j in output if "senior" in j["position"].lower()]
    assert not offenders, f"excluded seniority term survived in: {offenders}"


def test_no_free_keyword_match_survived(output):
    offenders = [
        j["position"]
        for j in output
        if "game" in text_of(j) or "canonical" in text_of(j)
    ]
    assert not offenders, f"excluded keyword survived in: {offenders}"


def test_nothing_valid_was_dropped(output, expected):
    missing = set(expected["keep"]) - urls(output)
    assert not missing, f"the filter dropped listings it should have kept: {missing}"


def test_exact_result_set(output, expected):
    assert urls(output) == set(expected["keep"])
