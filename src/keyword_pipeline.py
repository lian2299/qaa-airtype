"""Keyword-triggered hotkey pipeline for typed remote text."""
import time
import unicodedata
import pyautogui

try:
    from .config import load_config
    from .clipboard import (
        capture_clipboard_snapshot,
        restore_clipboard_snapshot,
    )
    from .utils import IS_WINDOWS
    from .keyboard import (
        HOTKEY_KEY_WHITELIST,
        paste_text,
        paste_literal_fragment,
        send_paste_hotkey,
        send_hotkey,
        send_shift_enter_windows,
        send_enter_windows,
        send_backspace_windows,
        send_ctrl_z_windows,
    )
except ImportError:
    from config import load_config
    from clipboard import (
        capture_clipboard_snapshot,
        restore_clipboard_snapshot,
    )
    from utils import IS_WINDOWS
    from keyboard import (
        HOTKEY_KEY_WHITELIST,
        paste_text,
        paste_literal_fragment,
        send_paste_hotkey,
        send_hotkey,
        send_shift_enter_windows,
        send_enter_windows,
        send_backspace_windows,
        send_ctrl_z_windows,
    )

# Predefined action names (alias path)
_ACTION_NAMES = frozenset({'paste', 'shift_enter', 'enter', 'backspace', 'undo'})

_SEGMENT_DELAY_S = 0.03
_SNAPSHOT_PASTE_SETTLE_S = 0.15


def _is_strippable_punct_char(ch):
    """Punctuation/symbol often inserted by voice IME around special terms."""
    if not ch:
        return False
    return unicodedata.category(ch).startswith('P')


def _strip_trailing_punct(text):
    i = len(text)
    while i > 0 and _is_strippable_punct_char(text[i - 1]):
        i -= 1
    return text[:i]


def _strip_leading_punct(text):
    i = 0
    n = len(text)
    while i < n and _is_strippable_punct_char(text[i]):
        i += 1
    return text[i:]


def strip_punctuation_around_keyword_segments(segments, enabled):
    """
    For each keyword segment, remove adjacent punctuation from neighboring literal segments.
    Voice input often wraps hotwords with commas/quotes; those should not be pasted.
    """
    if not enabled or not segments:
        return segments
    out = []
    for s in segments:
        if s.get('type') == 'literal':
            out.append({'type': 'literal', 'text': s.get('text') or ''})
        else:
            out.append(dict(s))

    n = len(out)
    for i in range(n):
        if out[i].get('type') != 'keyword':
            continue
        if i > 0 and out[i - 1].get('type') == 'literal':
            t = out[i - 1].get('text') or ''
            out[i - 1]['text'] = _strip_trailing_punct(t)
        if i + 1 < n and out[i + 1].get('type') == 'literal':
            t = out[i + 1].get('text') or ''
            out[i + 1]['text'] = _strip_leading_punct(t)

    return [s for s in out if not (s.get('type') == 'literal' and not (s.get('text') or ''))]


def _normalize_key_token(k):
    if k is None:
        return None
    s = str(k).strip().lower()
    if s == 'control':
        return 'ctrl'
    return s


def validate_keyword_actions(raw_list):
    """
    Return a clean list of rules: {keyword, action?} or {keyword, keys?}.
    Invalid entries are skipped.
    """
    if not raw_list:
        return []
    out = []
    seen_keywords = set()
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        kw = item.get('keyword')
        if kw is None or str(kw) == '':
            continue
        kw = str(kw)
        if kw in seen_keywords:
            continue
        action = item.get('action')
        keys = item.get('keys')
        if action is not None and keys is not None:
            continue
        if action is None and keys is None:
            continue
        if action is not None:
            a = str(action).strip().lower()
            if a not in _ACTION_NAMES:
                continue
            out.append({'keyword': kw, 'action': a})
            seen_keywords.add(kw)
            continue
        if not isinstance(keys, list) or not keys:
            continue
        normalized_keys = []
        ok = True
        for k in keys:
            nk = _normalize_key_token(k)
            if nk is None or nk not in HOTKEY_KEY_WHITELIST:
                ok = False
                break
            normalized_keys.append(nk)
        if not ok:
            continue
        out.append({'keyword': kw, 'keys': normalized_keys})
        seen_keywords.add(kw)
    return out


def parse_segments(text, rules):
    """
    Split text into segments: {'type': 'literal', 'text': str} or {'type': 'keyword', 'rule': dict}.
    Longest keyword match at each position.
    """
    if text is None:
        return []
    if not rules:
        return [{'type': 'literal', 'text': text}] if text else []

    n = len(text)
    segments = []
    i = 0
    literal_start = 0

    while i < n:
        best_rule = None
        best_len = 0
        for r in rules:
            kw = r.get('keyword') or ''
            if not kw:
                continue
            if text.startswith(kw, i) and len(kw) > best_len:
                best_len = len(kw)
                best_rule = r
        if best_rule:
            if i > literal_start:
                segments.append({'type': 'literal', 'text': text[literal_start:i]})
            segments.append({'type': 'keyword', 'rule': best_rule})
            i += best_len
            literal_start = i
        else:
            i += 1

    if literal_start < n:
        segments.append({'type': 'literal', 'text': text[literal_start:n]})
    return segments


def _dispatch_action_alias(action, use_ctrl_v):
    a = (action or '').lower()
    if a == 'paste':
        return bool(send_paste_hotkey(use_ctrl_v=use_ctrl_v))
    if a == 'shift_enter':
        if IS_WINDOWS:
            return bool(send_shift_enter_windows())
        pyautogui.hotkey('shift', 'enter')
        return True
    if a == 'enter':
        if IS_WINDOWS:
            return bool(send_enter_windows())
        pyautogui.press('enter')
        return True
    if a == 'backspace':
        if IS_WINDOWS:
            return bool(send_backspace_windows())
        pyautogui.press('backspace')
        return True
    if a == 'undo':
        if IS_WINDOWS:
            return bool(send_ctrl_z_windows())
        pyautogui.hotkey('ctrl', 'z')
        return True
    return False


def _dispatch_rule(rule, use_ctrl_v):
    if 'keys' in rule:
        return bool(send_hotkey(rule['keys']))
    if 'action' in rule:
        return _dispatch_action_alias(rule['action'], use_ctrl_v)
    return False


def segments_contain_keyword(segments):
    return any(s.get('type') == 'keyword' for s in segments)


def is_paste_rule(rule):
    """Return whether a keyword rule invokes a plain paste shortcut."""
    if (rule.get('action') or '').lower() == 'paste':
        return True
    keys = [str(k).strip().lower() for k in (rule.get('keys') or [])]
    return keys in (['ctrl', 'v'], ['shift', 'insert'])


def get_paste_keywords(rules):
    """Return configured keywords whose action is a paste shortcut."""
    return [
        rule.get('keyword')
        for rule in (rules or [])
        if rule.get('keyword') and is_paste_rule(rule)
    ]


def get_paste_occurrences(text, rules):
    """Return ordered signatures for paste keywords found in ``text``."""
    return [
        segment['rule'].get('keyword') or ''
        for segment in parse_segments(text or '', rules)
        if segment.get('type') == 'keyword' and is_paste_rule(segment.get('rule') or {})
    ]


def _restore_snapshot(snapshot):
    try:
        return bool(restore_clipboard_snapshot(snapshot))
    except Exception as e:
        print(f"[keyword_pipeline] clipboard snapshot restore failed: {e}")
        return False


def execute_typed_text(text, use_ctrl_v=None, preserve_clipboard=None, clipboard_snapshots=None):
    """
    Paste full text with optional keyword expansions.
    Returns True on success.
    If use_ctrl_v or preserve_clipboard is None, values are read from config.json.
    """
    cfg = load_config()
    if use_ctrl_v is None:
        use_ctrl_v = cfg.get('use_ctrl_v', False)
    if preserve_clipboard is None:
        preserve_clipboard = cfg.get('preserve_clipboard', False)

    rules = validate_keyword_actions(cfg.get('keyword_actions', []))
    segments = parse_segments(text, rules)
    if cfg.get('strip_punctuation_around_keywords', False):
        segments = strip_punctuation_around_keyword_segments(segments, True)

    if not segments_contain_keyword(segments):
        paste_text(text, use_ctrl_v=use_ctrl_v, preserve_clipboard=preserve_clipboard)
        return True

    try:
        staged = capture_clipboard_snapshot()
    except Exception as e:
        print(f"[keyword_pipeline] clipboard snapshot failed: {e}")
        staged = None
    paste_snapshots = iter(clipboard_snapshots or [])

    try:
        for seg in segments:
            if seg['type'] == 'literal':
                frag = seg.get('text') or ''
                if frag:
                    paste_literal_fragment(frag, use_ctrl_v=use_ctrl_v)
                    _restore_snapshot(staged)
                    time.sleep(_SEGMENT_DELAY_S)
            else:
                rule = seg['rule']
                restored_captured_snapshot = False
                if is_paste_rule(rule):
                    snapshot = next(paste_snapshots, None)
                    if snapshot is not None:
                        if not _restore_snapshot(snapshot):
                            _restore_snapshot(staged)
                            return False
                        time.sleep(0.08)
                        restored_captured_snapshot = True
                ok = _dispatch_rule(rule, use_ctrl_v)
                if not ok:
                    _restore_snapshot(staged)
                    return False
                time.sleep(_SNAPSHOT_PASTE_SETTLE_S if restored_captured_snapshot else _SEGMENT_DELAY_S)

        if preserve_clipboard:
            time.sleep(0.12)
            _restore_snapshot(staged)
        return True
    except Exception as e:
        print(f"execute_typed_text error: {e}")
        _restore_snapshot(staged)
        return False
