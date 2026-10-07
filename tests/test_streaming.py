"""SSE stream parser."""

from agentrouter.streaming import (
    content_from_sse_data,
    extract_content_from_chunk,
    iter_response_content,
    iter_sse_content,
    parse_sse_line,
)


def _chunk(text):
    return {"choices": [{"delta": {"content": text}}]}


def test_extract_delta_content():
    assert extract_content_from_chunk(_chunk("hello")) == "hello"


def test_extract_message_fallback():
    assert extract_content_from_chunk({"choices": [{"message": {"content": "hi"}}]}) == "hi"


def test_extract_text_fallback():
    assert extract_content_from_chunk({"choices": [{"text": "t"}]}) == "t"


def test_extract_empty_choices():
    assert extract_content_from_chunk({"choices": []}) == ""
    assert extract_content_from_chunk({}) == ""


def test_done_marker_returns_none():
    assert content_from_sse_data("[DONE]") is None
    assert content_from_sse_data("  [DONE]  ") is None


def test_blank_data_returns_none():
    assert content_from_sse_data("") is None
    assert content_from_sse_data("   ") is None


def test_invalid_json_returns_none():
    assert content_from_sse_data("not json {") is None


def test_empty_content_returns_none():
    import json

    assert content_from_sse_data(json.dumps({"choices": []})) is None


def test_parse_data_line():
    import json

    line = "data: " + json.dumps(_chunk("tok"))
    assert parse_sse_line(line) == "tok"


def test_parse_skips_comments_and_blanks():
    assert parse_sse_line(": keep-alive") is None
    assert parse_sse_line("") is None
    assert parse_sse_line("   ") is None
    assert parse_sse_line("event: message") is None


def test_parse_done_line():
    assert parse_sse_line("data: [DONE]") is None


def test_iter_sse_content_joins_tokens():
    import json

    lines = [
        "data: " + json.dumps(_chunk("Hel")),
        "data: " + json.dumps(_chunk("lo")),
        ": ping",
        "",
        "data: [DONE]",
    ]
    assert list(iter_sse_content(lines)) == ["Hel", "lo"]


def test_iter_sse_content_skips_non_strings():
    assert list(iter_sse_content([None, 123])) == []


def test_iter_response_content_uses_iter_lines():
    import json

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            yield "data: " + json.dumps(_chunk("a"))
            yield "data: " + json.dumps(_chunk("b"))
            yield "data: [DONE]"

    assert list(iter_response_content(FakeResp())) == ["a", "b"]
