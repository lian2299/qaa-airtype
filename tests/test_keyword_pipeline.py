"""Tests for keyword_pipeline (no real keyboard or clipboard)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.keyword_pipeline import (
    parse_segments,
    validate_keyword_actions,
    segments_contain_keyword,
    strip_punctuation_around_keyword_segments,
    get_paste_keywords,
    get_paste_occurrences,
    is_paste_rule,
    execute_typed_text,
)
from src import state


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

    def test_ctrl_v_hotword_is_a_paste_occurrence(self):
        rules = validate_keyword_actions([
            {'keyword': '任意粘贴指令', 'keys': ['ctrl', 'v']},
            {'keyword': '不是粘贴指令', 'keys': ['shift', 'enter']},
        ])
        self.assertTrue(is_paste_rule(rules[0]))
        self.assertFalse(is_paste_rule(rules[1]))
        self.assertEqual(get_paste_keywords(rules), ['任意粘贴指令'])
        self.assertEqual(
            get_paste_occurrences('前面任意粘贴指令中间任意粘贴指令后面', rules),
            ['任意粘贴指令', '任意粘贴指令'],
        )

    def test_execute_uses_each_captured_clipboard_in_order(self):
        config = {
            'keyword_actions': [{'keyword': '插入剪贴板', 'keys': ['ctrl', 'v']}],
        }
        restored = []

        with patch('src.keyword_pipeline.load_config', return_value=config), \
                patch('src.keyword_pipeline.capture_clipboard_snapshot', return_value='original'), \
                patch('src.keyword_pipeline.restore_clipboard_snapshot', side_effect=lambda value: restored.append(value) or True), \
                patch('src.keyword_pipeline.paste_literal_fragment'), \
                patch('src.keyword_pipeline._dispatch_rule', return_value=True), \
                patch('src.keyword_pipeline.time.sleep'):
            ok = execute_typed_text(
                '甲插入剪贴板乙插入剪贴板丙',
                preserve_clipboard=True,
                clipboard_snapshots=['截图一', '复制内容二'],
            )

        self.assertTrue(ok)
        self.assertLess(restored.index('截图一'), restored.index('复制内容二'))
        self.assertEqual(restored[-1], 'original')


class ClipboardPlaceholderStateTests(unittest.TestCase):
    def setUp(self):
        state.clear_input_preview()

    def tearDown(self):
        state.clear_input_preview()

    def test_new_occurrences_capture_current_clipboard_once_each(self):
        captures = iter(['截图一', '复制内容二'])
        capture = lambda: next(captures)

        first = state.sync_paste_occurrences(['动态指令'], capture_fn=capture)
        repeated = state.sync_paste_occurrences(['动态指令'], capture_fn=capture)
        second = state.sync_paste_occurrences(['动态指令', '动态指令'], capture_fn=capture)

        self.assertEqual(first, ['截图一'])
        self.assertEqual(repeated, ['截图一'])
        self.assertEqual(second, ['截图一', '复制内容二'])

    def test_removed_trailing_occurrence_discards_its_binding(self):
        captures = iter(['一', '二', '三'])
        capture = lambda: next(captures)
        state.sync_paste_occurrences(['动态指令', '动态指令'], capture_fn=capture)
        state.sync_paste_occurrences(['动态指令'], capture_fn=capture)

        result = state.sync_paste_occurrences(['动态指令', '动态指令'], capture_fn=capture)

        self.assertEqual(result, ['一', '三'])


if __name__ == '__main__':
    unittest.main()
