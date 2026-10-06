"""On-disk storage of the AI agent conversations.

One JSON file per project, in the editor's machine-local data folder::

    <user config>/PygameStudio/agent_sessions/<project key>.json

A file holds up to :data:`MAX_SESSIONS` conversations (newest first). Every
record keeps exactly what the panel needs: the model messages (to carry on
chatting) plus the transcript log the panel draws from - see
``AgentSession.messages`` and ``AgentTranscript.entries``.

The folder can be overridden with ``__PYGAMESTUDIO_AGENT_SESSIONS_DIR``: the
tests point it at a temporary folder, so they never touch the real profile.
"""
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from pygamestudio.common.utils.config import get_editor_data_dir
from pygamestudio.gui.console.logger import Logger

#: How many conversations are kept per project (the oldest ones are dropped).
MAX_SESSIONS = 50
#: Longest stored title (taken from the first user message).
MAX_TITLE_CHARS = 80
#: Layout version of a store file.
STORE_VERSION = 1

#: Environment variable pointing the sessions folder somewhere else (tests).
ENV_SESSIONS_DIR = '__PYGAMESTUDIO_AGENT_SESSIONS_DIR'


def sessions_dir() -> Path:
    """The folder the conversation files live in."""
    override = os.environ.get(ENV_SESSIONS_DIR)
    if override:
        return Path(override)
    return get_editor_data_dir() / 'agent_sessions'


def project_key(project_path) -> str:
    """Stable file key of a project (normalized absolute path, hashed)."""
    raw = os.path.normcase(os.path.abspath(str(project_path or '').strip()))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def store_file(project_path) -> Path:
    """The JSON file of one project."""
    return sessions_dir() / '{}.json'.format(project_key(project_path))


def _empty_store(project_path) -> dict:
    return {'version': STORE_VERSION, 'project': str(project_path or ''), 'sessions': []}


def load_store(project_path) -> dict:
    """Read a project's store.

    A missing file reads as empty; an unreadable one is set aside as
    ``*.json.corrupt`` (never lost silently) and also reads as empty, so a
    broken file can never take the agent panel down.
    """
    path = store_file(project_path)
    if not path.is_file():
        return _empty_store(project_path)
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get('sessions'), list):
            raise ValueError('unexpected layout')
        data['version'] = data.get('version') or STORE_VERSION
        data['project'] = data.get('project') or str(project_path or '')
        return data
    except Exception as error:  # noqa: BLE001 - a broken file must not break the panel
        Logger.error('Could not read the agent sessions of {}: {}'.format(project_path, error))
        try:
            path.replace(path.with_name(path.name + '.corrupt'))
        except OSError:
            pass
        return _empty_store(project_path)


def _write_store(project_path, data) -> None:
    path = store_file(project_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.tmp')
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temp, path)
    except OSError as error:
        Logger.error('Could not save the agent sessions of {}: {}'.format(project_path, error))


def list_sessions(project_path) -> list:
    """Every stored conversation of the project, newest first."""
    return [record for record in load_store(project_path)['sessions']
            if isinstance(record, dict)]


def get_session(project_path, session_id) -> dict:
    """One conversation by id (None when it is gone)."""
    for record in list_sessions(project_path):
        if record.get('id') == session_id:
            return record
    return None


def latest_session(project_path) -> dict:
    """The conversation used last (None when the project has no history)."""
    sessions = list_sessions(project_path)
    return sessions[0] if sessions else None


def save_session(project_path, record) -> None:
    """Insert or update one conversation and cap the list at MAX_SESSIONS.

    The saved conversation moves to the front, so the file order is the
    order the history dialog lists (newest first).
    """
    if not project_path or not isinstance(record, dict) or not record.get('id'):
        return
    data = load_store(project_path)
    record = dict(record)
    record['updated_at'] = record.get('updated_at') or time.time()
    sessions = [item for item in data['sessions']
                if isinstance(item, dict) and item.get('id') != record['id']]
    sessions.insert(0, record)
    data['sessions'] = sessions[:MAX_SESSIONS]
    data['project'] = str(project_path)
    _write_store(project_path, data)


def delete_session(project_path, session_id) -> bool:
    """Drop one conversation; True when it was there."""
    data = load_store(project_path)
    kept = [item for item in data['sessions']
            if isinstance(item, dict) and item.get('id') != session_id]
    if len(kept) == len(data['sessions']):
        return False
    data['sessions'] = kept
    _write_store(project_path, data)
    return True


def new_session_id() -> str:
    """A fresh id for a conversation."""
    return uuid.uuid4().hex


def title_from_messages(messages) -> str:
    """The first user message, flattened to one short line."""
    for message in messages or []:
        if isinstance(message, dict) and message.get('role') == 'user':
            text = ' '.join(str(message.get('content') or '').split())
            if text:
                if len(text) > MAX_TITLE_CHARS:
                    text = text[:MAX_TITLE_CHARS - 1] + '\u2026'
                return text
    return ''
