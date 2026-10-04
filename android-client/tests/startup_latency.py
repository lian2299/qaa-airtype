"""Real-device F9 timings via the DUMP-protected diagnostic broadcast.

Start fake_server.py first. All test text is routed to that isolated sink.
The original preferences and other accessibility services are preserved.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
parser.add_argument('--label', required=True)
parser.add_argument('--behavior-only', action='store_true')
args = parser.parse_args()
adb = ['C:/Android/Sdk/platform-tools/adb.exe', '-s', args.serial]
package = 'local.qaa.airtype'
output = Path(__file__).resolve().parents[2] / '.local-build/startup-latency'
output.mkdir(parents=True, exist_ok=True)


def command(*parts, data=None):
    return subprocess.run(adb + list(parts), input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=12).stdout


def shell(*parts):
    return command('shell', *parts).decode('utf-8').strip()


def events():
    try:
        previous = shell('run-as', package, 'cat', 'files/events.previous.log')
    except subprocess.CalledProcessError:
        previous = ''
    return previous + '\n' + shell('run-as', package, 'cat', 'files/events.log')


def enable(value):
    shell('settings', 'put', 'secure', 'enabled_accessibility_services', shlex.quote(value))
    if not any(s.startswith(package + '/') for s in value.split(':')):
        time.sleep(1)  # Let asynchronous unbinding clear the crashed-service entry.
        return
    limit = time.monotonic() + 5
    while time.monotonic() < limit:
        state = shell('dumpsys', 'accessibility')
        bound = re.search(r'Bound services:\{(.*?)\}\s*Enabled services:', state, re.S)
        crashed = re.search(r'Crashed services:\{([^\n]*)', state)
        if bound and 'label=F9 远程语音,' in bound[1] and (not crashed or package + '/' not in crashed[1]):
            return
        time.sleep(.25)
    raise RuntimeError('F9 accessibility did not reconnect')


def preferences(data):
    command('shell', 'run-as', package, 'sh', '-c',
            shlex.quote('cat > shared_prefs/settings.xml'), data=data)


with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:15001/last_text', method='HEAD'), timeout=2):
    pass
enabled = shell('settings', 'get', 'secure', 'enabled_accessibility_services')
assert any(s.startswith(package + '/') for s in enabled.split(':')), 'Enable AirType accessibility first'
other = ':'.join(s for s in enabled.split(':') if not s.startswith(package + '/'))
original = command('shell', 'run-as', package, 'cat', 'shared_prefs/settings.xml')
backup = output / (args.label + '-settings.xml')
backup.write_bytes(original)
tree = ET.fromstring(original)
for node in list(tree):
    if node.get('name') in ('url', 'draft'):
        tree.remove(node)
ET.SubElement(tree, 'string', name='url').text = 'http://127.0.0.1:15001/'
samples = []
try:
    enable(other)
    shell('am', 'force-stop', package)
    preferences(ET.tostring(tree, encoding='utf-8', xml_declaration=True))
    shell('am', 'start', '-n', package + '/.MainActivity')
    enable(enabled)
    command('reverse', 'tcp:15001', 'tcp:15001')
    time.sleep(1)
    shell('am', 'start', '-n', package + '/.MainActivity', '-f', '0x10008000', '--es', 'command', 'snapshot', '--ez', 'return_remote', 'true')
    time.sleep(2)
    for index in range(0 if args.behavior_only else 10):
        scenario = 'foreground' if index < 6 else 'home'
        if scenario == 'home':
            shell('input', 'keyevent', 'KEYCODE_HOME')
            time.sleep(.5)
        before = events()
        shell('am', 'broadcast', '-a', package + '.SNAPSHOT', '-p', package, '--el', 'hold_ms', '1500')
        limit = time.monotonic() + 9
        while time.monotonic() < limit:
            log = events()
            # The log rotates; match only timestamps after the last old event.
            since = int(before.splitlines()[-1].split()[0]) if before else 0
            current = '\n'.join(line for line in log.splitlines() if line and int(line.split()[0]) > since)
            if 'FAILED ' in current:
                raise RuntimeError(current)
            if 'FINISHED' in current:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Startup/stop timed out: ' + current)
        key = re.search(r'(?m)^(\d+) KEY action=0', current)
        button = re.search(r'(?m)^(\d+) START_BUTTON', current)
        ready = re.search(r'(?m)^(\d+) READY', current)
        stop = re.search(r'(?m)^(\d+) STOP_REQUEST', current)
        finished = re.search(r'(?m)^(\d+) FINISHED', current)
        assert key and button and ready and stop and finished, current
        row = dict(scenario=scenario, round=index + 1,
                   key_to_button_ms=int(button[1]) - int(key[1]),
                   key_to_ready_ms=int(ready[1]) - int(key[1]),
                   button_to_ready_ms=int(ready[1]) - int(button[1]),
                   stop_to_finished_ms=int(finished[1]) - int(stop[1]))
        samples.append(row)
        (output / (args.label + '.json')).write_text(json.dumps(samples, indent=2), encoding='utf-8')
        print(json.dumps(row), flush=True)
        (output / (args.label + '-events.log')).write_text(log, encoding='utf-8')
        time.sleep(.5)
    if args.behavior_only:
        since = int(events().splitlines()[-1].split()[0])
        shell('am', 'broadcast', '-a', package + '.SNAPSHOT', '-p', package, '--el', 'hold_ms', '100')
        time.sleep(.9)
        current = '\n'.join(line for line in events().splitlines() if line and int(line.split()[0]) > since)
        assert 'READY ' in current and 'SNAPSHOT phase=RECORDING' in current and 'FINISHED' not in current and 'FAILED' not in current, current
        shell('am', 'broadcast', '-a', package + '.SNAPSHOT', '-p', package, '--el', 'hold_ms', '100')
        limit = time.monotonic() + 5
        while time.monotonic() < limit:
            current = '\n'.join(line for line in events().splitlines() if line and int(line.split()[0]) > since)
            if 'FINISHED' in current:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Second short press did not stop recording: ' + current)
        assert 'FAILED' not in current, current
        (output / (args.label + '-events.log')).write_text(current, encoding='utf-8')
        print('Short press keeps recording; second press stops: passed', flush=True)
finally:
    enable(other)
    shell('am', 'force-stop', package)
    preferences(original)
    shell('am', 'start', '-n', package + '/.MainActivity')
    enable(enabled)
    command('reverse', '--remove', 'tcp:15001')
    time.sleep(1)
    shell('am', 'start', '-n', package + '/.MainActivity', '-f', '0x10008000', '--es', 'command', 'snapshot', '--ez', 'return_remote', 'true')
