"""Tests for keyword_pipeline (no real keyboard or clipboard)."""
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.keyword_pipeline import (
    parse_segments,
    validate_keyword_actions,
    segments_contain_keyword,
    strip_punctuation_around_keyword_segments,
)


class KeywordPipelineParseTests(unittest.TestCase):
    def test_parse_longest_match(self):
        rules = validate_keyword_actions(
            [
                {'keyword': 'a', 'action': 'enter'},
                {'keyword': 'ab', 'action': 'enter'},
            ]
        )
        segs = parse_segments('abx', rules)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]['type'], 'keyword')
        self.assertEqual(segs[0]['rule']['keyword'], 'ab')
        self.assertEqual(segs[1], {'type': 'literal', 'text': 'x'})

    def test_parse_empty_rules_is_single_literal(self):
        segs = parse_segments('hello', [])
        self.assertEqual(segs, [{'type': 'literal', 'text': 'hello'}])
        self.assertFalse(segments_contain_keyword(segs))

    def test_parse_no_keyword_hit(self):
        rules = validate_keyword_actions([{'keyword': 'zzz', 'action': 'paste'}])
        segs = parse_segments('hello', rules)
        self.assertEqual(segs, [{'type': 'literal', 'text': 'hello'}])
        self.assertFalse(segments_contain_keyword(segs))

    def test_parse_adjacent_keywords(self):
        rules = validate_keyword_actions(
            [
                {'keyword': 'aa', 'action': 'enter'},
                {'keyword': 'bb', 'action': 'backspace'},
            ]
        )
        segs = parse_segments('aabb', rules)
        self.assertTrue(segments_contain_keyword(segs))
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]['type'], 'keyword')
        self.assertEqual(segs[1]['type'], 'keyword')

    def test_validate_drops_invalid_and_duplicate(self):
        raw = [
            {'keyword': 'ok', 'action': 'paste'},
            {'keyword': 'ok', 'action': 'enter'},
            {'keyword': 'bad', 'action': 'unknown'},
            {'keyword': 'keys', 'keys': ['ctrl', 'badkey']},
        ]
        cleaned = validate_keyword_actions(raw)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]['keyword'], 'ok')

    def test_validate_keys_form(self):
        cleaned = validate_keyword_actions([{'keyword': 'x', 'keys': ['Shift', 'ENTER']}])
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]['keys'], ['shift', 'enter'])

    def test_strip_punctuation_around_keywords(self):
        rules = validate_keyword_actions([{'keyword': 'K', 'action': 'paste'}])
        segs = parse_segments('a，K，b', rules)
        stripped = strip_punctuation_around_keyword_segments(segs, True)
        self.assertEqual(len(stripped), 3)
        self.assertEqual(stripped[0], {'type': 'literal', 'text': 'a'})
        self.assertEqual(stripped[1]['type'], 'keyword')
        self.assertEqual(stripped[2], {'type': 'literal', 'text': 'b'})

    def test_strip_punctuation_disabled_noop(self):
        rules = validate_keyword_actions([{'keyword': 'K', 'action': 'paste'}])
        segs = parse_segments('a，K，b', rules)
        stripped = strip_punctuation_around_keyword_segments(segs, False)
        self.assertEqual(stripped, segs)


if __name__ == '__main__':
    unittest.main()
