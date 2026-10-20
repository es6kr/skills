"""Offline assignment policy and immutable data contracts."""
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Protocol
import hashlib
import json
import uuid
import ntpath

def uuid_text(value):
    if not isinstance(value, str):
        raise ValueError("schema_error")
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("schema_error") from None
    return value

def absolute_workspace(value):
    return isinstance(value, str) and bool(value) and (value.startswith("/") or (ntpath.isabs(value) and bool(ntpath.splitdrive(value)[0])))
from plane_client import html_to_text, format_browse_url

@dataclass(frozen=True)
class IdentityScope:
    """Trusted caller policy, never derived from issue/fixture/environment data."""
    host: str
    workspace: str
    project_id: str
    identifier: str

    def __post_init__(self):
        import re
        from urllib.parse import urlsplit

        if any(type(value) is not str for value in
               (self.host, self.workspace, self.project_id, self.identifier)):
            raise ValueError('schema_error')
        # GUARD: Reject rather than normalize URL/path tokens before comparison.
        if (not re.fullmatch(r'https://[A-Za-z0-9.\-\[\]:]+', self.host)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', self.workspace)
                or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', self.identifier)):
            raise ValueError('schema_error')
        try:
            origin = urlsplit(self.host)
            port = origin.port
            if (not origin.hostname or origin.username is not None
                    or origin.password is not None or origin.path or origin.query
                    or origin.fragment or (port is not None and port < 1)
                    or self.host.endswith(':')):
                raise ValueError('schema_error')
        except ValueError:
            raise ValueError('schema_error') from None
        uuid_text(self.project_id)


@dataclass(frozen=True)
class Config:
    host: str
    workspace: str
    project_id: str
    assignee_id: str
    repo: str | None = None
    scope: IdentityScope | None = None

    def __post_init__(self):
        if self.scope is None:
            raise ValueError('scope_required')
        if type(self.scope) is not IdentityScope:
            raise ValueError('schema_error')
        if (self.host, self.workspace, self.project_id) != (self.scope.host, self.scope.workspace, self.scope.project_id):
            raise ValueError('identity_mismatch')
        uuid_text(self.project_id)
        uuid_text(self.assignee_id)
        if self.repo is not None and not absolute_workspace(self.repo):
            raise ValueError('workspace_required')

@dataclass(frozen=True)
class State:
    id: str
    group: str
    is_triage: bool

@dataclass(frozen=True)
class Issue:
    id: str
    project_id: str
    assignees: tuple[str, ...]
    state_id: str
    sequence_id: int
    title: str
    body: str
    revision: str

@dataclass(frozen=True)
class Snapshot:
    issues: tuple[Issue, ...]
    states: Mapping[str, State]
    complete: bool
    error_code: str | None = None

@dataclass(frozen=True)
class Envelope:
    outbox_id: str
    task_key: str
    issue_id: str
    issue_url: str
    generation: int
    workspace_path: str | None
    content_revision: str
    title: str
    untrusted_body: str
    allowed_actions: tuple[str, ...] = ('classify', 'research', 'plan')
    execute_allowed: bool = False

@dataclass(frozen=True)
class Receipt:
    outbox_id: str
    request_sha256: str
    receiver_identity_revision: str
    run_id: str
    session_id: str
    observed_at: int
    status_readback: str

class ReadClient(Protocol):
    def request(self, path: str, method: str = 'GET', data: Any = None) -> Any: ...

class Receiver(Protocol):
    def submit(self, envelope: Envelope) -> Receipt: ...
    def lookup(self, outbox_id: str, request_sha256: str) -> Receipt | None: ...

def normalize_states(raw):
    if not isinstance(raw, list) or not raw:
        raise ValueError('schema_error')
    states = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('schema_error')
        sid = uuid_text(item.get('id'))
        group, triage = item.get('group'), item.get('is_triage')
        if not isinstance(group, str) or group not in {'backlog', 'cancelled', 'completed', 'started', 'unstarted'} or type(triage) is not bool or sid in states:
            raise ValueError('schema_error')
        states[sid] = State(sid, group, triage)
    return states

def normalize_issue(raw, config):
    if not isinstance(raw, dict):
        raise ValueError('schema_error')
    iid = uuid_text(raw.get('id'))
    project = raw.get('project', config.project_id)
    if project != config.project_id:
        raise ValueError('identity_mismatch')
    state = raw.get('state')
    if isinstance(state, dict):
        state = state.get('id')
    state = uuid_text(state)
    assignees = raw.get('assignees')
    if not isinstance(assignees, list):
        raise ValueError('schema_error')
    if assignees and not (all(isinstance(x, str) for x in assignees) or all(isinstance(x, dict) for x in assignees)):
        raise ValueError('schema_error')
    ids = tuple(sorted(set(uuid_text(x.get('id') if isinstance(x, dict) else x) for x in assignees)))
    title, sequence = raw.get('name'), raw.get('sequence_id')
    body = raw.get('description_html')
    if body is not None:
        if not isinstance(body, str):
            raise ValueError('schema_error')
        body = html_to_text(body)
    else:
        body = raw.get('description_stripped', '')
    if not isinstance(title, str) or not isinstance(body, str) or type(sequence) is not int or sequence < 1:
        raise ValueError('schema_error')
    if len(title) > 512 or len(body) > 16384:
        raise ValueError('content_limit')
    revision = digest(dict(title=title, body=body, state=state, assignees=ids))
    return Issue(iid, project, ids, state, sequence, title, body, revision)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

def task_key(config, issue_id, generation):
    return digest([config.host, config.workspace, config.project_id, issue_id,
                   config.assignee_id, generation])

def eligible(issue, config, states):
    state = states.get(issue.state_id)
    return bool(issue.project_id == config.project_id and config.assignee_id in issue.assignees
                and state is not None and state.is_triage is False
                and state.group in {'backlog', 'started', 'unstarted'})

def build_envelope(config, issue, generation, outbox_id):
    return Envelope(outbox_id, task_key(config, issue.id, generation), issue.id,
                    format_browse_url(config.host, config.workspace, config.scope.identifier, issue.sequence_id),
                    generation, config.repo, issue.revision, issue.title, issue.body)
