from src.json_utils import parse_json_loose


def test_parses_clean_json_array():
    result = parse_json_loose('[{"a": 1}, {"a": 2}]')
    assert result == [{"a": 1}, {"a": 2}]


def test_parses_json_wrapped_in_prose():
    text = 'Here are the results:\n[{"a": 1}]\nHope that helps!'
    result = parse_json_loose(text)
    assert result == [{"a": 1}]


def test_parses_json_in_code_fence():
    text = '```json\n{"a": 1}\n```'
    result = parse_json_loose(text)
    assert result == {"a": 1}


def test_falls_back_to_raw_on_garbage():
    result = parse_json_loose("not json at all")
    assert result == {"raw": "not json at all"}
