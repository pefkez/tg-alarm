import os, json, threading, logging
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler import AlarmScheduler
from group_alarm import GroupAlarmManager

load_dotenv()

app = Flask(__name__)
scheduler = AlarmScheduler()
group_manager = GroupAlarmManager()

state = {
    "running": False,
    "target": None,
    "mode": "api",
    "started_at": None,
}

scheduler.load()


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/state')
def get_state():
    schedule_list = scheduler.list()
    return jsonify({
        **state,
        "schedules": schedule_list,
        "groups": [{"id": gid, **gm} for gid, gm in group_manager.groups.items()]
    })


@app.route('/api/target', methods=['POST'])
def set_target():
    data = request.json
    state['target'] = data.get('target', '').lstrip('@')
    return jsonify({"ok": True, "target": state['target']})


@app.route('/api/mode', methods=['POST'])
def set_mode():
    data = request.json
    mode = data.get('mode', 'api')
    if mode in ('api', 'macro', 'whatsapp', 'signal'):
        state['mode'] = mode
    return jsonify({"ok": True, "mode": state['mode']})


@app.route('/api/go', methods=['POST'])
def go():
    if not state['target']:
        return jsonify({"error": "No target"}), 400
    state['running'] = True
    state['started_at'] = __import__('datetime').datetime.now().isoformat()
    return jsonify({"ok": True})


@app.route('/api/stop', methods=['POST'])
def stop():
    state['running'] = False
    return jsonify({"ok": True})


@app.route('/api/schedule', methods=['GET'])
def get_schedules():
    return jsonify(scheduler.list())


@app.route('/api/schedule', methods=['POST'])
def add_schedule():
    data = request.json
    sid = scheduler.add({
        "time": data.get('time'),
        "days": data.get('days', [0, 1, 2, 3, 4, 5, 6]),
        "target": data.get('target', state['target']),
        "mode": data.get('mode', state['mode']),
        "enabled": True,
        "once": data.get('once', False),
        "label": data.get('label', 'Alarm')
    })
    return jsonify({"id": sid})


@app.route('/api/schedule/<sid>', methods=['DELETE'])
def delete_schedule(sid):
    scheduler.remove(sid)
    return jsonify({"ok": True})


@app.route('/api/groups', methods=['GET'])
def get_groups():
    return jsonify([{"id": gid, **gm} for gid, gm in group_manager.groups.items()])


@app.route('/api/groups', methods=['POST'])
def create_group():
    data = request.json
    gid = group_manager.create_group(
        str(int(__import__('time').time())),
        data.get('targets', [])
    )
    return jsonify({"id": gid})


def start_dashboard():
    scheduler.start()
    app.run(host='0.0.0.0', port=5050, debug=False)


if __name__ == '__main__':
    start_dashboard()
