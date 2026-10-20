"""Account-scoped shared workspaces with a persistent, ordered group chat."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.database import (
    ODDI_DRIVE_CHAT_STORAGE,
    SHARED_WORKSPACES_DATABASE_URL,
    _begin_write,
    _fetchall,
    _fetchone,
    _use_postgres,
    get_db,
    get_user_by_email,
    get_user_by_id,
)
from app.engine import process_message
from identity.identity import create_identity
from quota.manager import quota_manager

logger = logging.getLogger("oddi.shared_workspaces")
router = APIRouter(prefix="/api/shared-workspaces", tags=["shared workspaces"])

MAX_MESSAGE_LENGTH = 8000
MAX_NAME_LENGTH = 80
MAX_PROJECT_GOAL_LENGTH = 4000
MAX_TASK_TITLE_LENGTH = 180
INVITE_LIFETIME = timedelta(days=14)
_AI_PREFIX = re.compile(r"^\s*@oddi(?=$|\s|[:,])\s*[:,]?\s*(.*)$", re.IGNORECASE | re.DOTALL)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _dict(row: Any) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _public_role(role: Any) -> str:
    """Expose the workspace creator's role as Admin in the shared UI/API."""
    normalized = str(role or "member").strip().casefold()
    return "admin" if normalized == "owner" else normalized


def _shared_workspace_identity(user_id: int | str, email: str):
    """Apply the member quota to shared ODDI requests, including the admin."""
    identity = create_identity(user_id=str(user_id), email=email)
    return replace(identity, role="member", is_host=False)


def _check_store() -> None:
    if ODDI_DRIVE_CHAT_STORAGE and not SHARED_WORKSPACES_DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail=(
                "Shared workspaces are not configured for this hosted storage mode. "
                "The site owner must configure ODDI_SHARED_WORKSPACES_DATABASE_URL."
            ),
        )


async def _account(request: Request) -> dict[str, Any]:
    """Resolve an authenticated, non-temporary account using ODDI's auth rules."""
    from server import is_temporary_browser_account, require_user_id

    if is_temporary_browser_account(request):
        raise HTTPException(status_code=403, detail="Sign in with an ODDI account to use shared workspaces.")
    try:
        user_id = await run_in_threadpool(require_user_id, request)
    except HTTPException:
        raise
    except Exception as error:
        logger.warning("Shared workspace authentication lookup failed: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="ODDI could not verify this account right now.") from error

    try:
        numeric_user_id = int(user_id)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=403, detail="This account cannot join a shared workspace.")

    email = str(request.session.get("email") or "").strip().casefold()
    if not email or email.endswith("@local.oddi.invalid"):
        raise HTTPException(status_code=403, detail="Sign in with a verified ODDI account to use shared workspaces.")

    try:
        user_row = await run_in_threadpool(get_user_by_id, numeric_user_id)
        user = _dict(user_row)
    except Exception as error:
        logger.warning("Shared workspace account lookup failed: %s", type(error).__name__)
        user = None
    if user and str(user.get("email") or "").strip().casefold() != email:
        raise HTTPException(status_code=401, detail="This sign-in no longer matches the account. Sign in again.")

    display_name = str(request.session.get("username") or (user or {}).get("username") or email.split("@", 1)[0]).strip()
    return {"id": numeric_user_id, "email": email, "name": display_name[:120] or "ODDI member"}


def _connection():
    _check_store()
    return get_db("shared")


def _workspace_membership(conn, workspace_id: str, user_id: int):
    return _fetchone(
        conn,
        """SELECT w.id, w.name, w.owner_user_id, w.ai_active_message_id,
                  m.role AS my_role
           FROM shared_workspaces w
           JOIN shared_workspace_members m ON m.workspace_id = w.id
           WHERE w.id = ? AND m.user_id = ?""",
        (workspace_id, user_id),
    )


def _require_membership(conn, workspace_id: str, user_id: int):
    row = _workspace_membership(conn, workspace_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="This shared workspace is unavailable to your account.")
    return row


def _workspace_projects(conn, workspace_id: str, include_tasks: bool = True) -> list[dict[str, Any]]:
    rows = _fetchall(
        conn,
        """SELECT id, workspace_id, name, goal, deadline, workflow_status,
                  created_by, created_at, updated_at
           FROM shared_workspace_projects WHERE workspace_id = ?
           ORDER BY created_at DESC, id""",
        (workspace_id,),
    )
    projects = [_dict(row) or {} for row in rows]
    if not projects:
        return []
    if include_tasks:
        task_rows = _fetchall(
            conn,
            """SELECT t.id, t.project_id, t.title, t.details, t.status,
                      t.assigned_user_id, t.sort_order, t.created_at, t.updated_at,
                      m.display_name AS assigned_user_name
               FROM shared_workspace_project_tasks t
               LEFT JOIN shared_workspace_members m
                 ON m.workspace_id = t.workspace_id AND m.user_id = t.assigned_user_id
               WHERE t.workspace_id = ?
               ORDER BY t.project_id, t.sort_order, t.created_at, t.id""",
            (workspace_id,),
        )
        task_groups: dict[str, list[dict[str, Any]]] = {}
        for row in task_rows:
            task = _dict(row) or {}
            task["assigned_user_id"] = int(task["assigned_user_id"]) if task.get("assigned_user_id") is not None else None
            task["sort_order"] = int(task.get("sort_order") or 0)
            task_groups.setdefault(str(task.get("project_id") or ""), []).append(task)
        for project in projects:
            project["tasks"] = task_groups.get(str(project.get("id") or ""), [])
    else:
        counts = _fetchall(
            conn,
            """SELECT project_id, COUNT(*) AS task_count,
                      SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS completed_count
               FROM shared_workspace_project_tasks WHERE workspace_id = ? GROUP BY project_id""",
            (workspace_id,),
        )
        count_by_project = {str(row["project_id"]): row for row in counts}
        for project in projects:
            counts_row = count_by_project.get(str(project.get("id") or ""), {})
            project["task_count"] = int(counts_row.get("task_count") or 0)
            project["completed_count"] = int(counts_row.get("completed_count") or 0)
    for project in projects:
        project["id"] = str(project.get("id") or "")
        project["workspace_id"] = str(project.get("workspace_id") or workspace_id)
        project["workflow_status"] = str(project.get("workflow_status") or "offered")
        project.pop("created_by", None)
        if include_tasks:
            tasks = project.get("tasks") or []
            project["task_count"] = len(tasks)
            project["completed_count"] = sum(1 for task in tasks if task.get("status") == "done")
    return projects


def _quota_payload(user_id: int, email: str) -> dict[str, Any]:
    identity = _shared_workspace_identity(user_id, email)
    status = quota_manager.user_quota_status(
        user_id=identity.user_id,
        role=identity.role,
        is_host=identity.is_host,
    )

    def whole_number(value):
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError, OverflowError):
            return None

    return {
        "unlimited": bool(status.get("exempt")),
        "available": bool(status.get("quota_available", True)),
        "requests_remaining": whole_number(status.get("requests_remaining")),
        "requests_limit": whole_number(status.get("requests_limit")),
        "tokens_remaining": whole_number(status.get("tokens_remaining")),
        "tokens_limit": whole_number(status.get("tokens_limit")),
        "usage_date": str(status.get("usage_date") or ""),
    }


def _public_message(row: Any, viewer_id: int) -> dict[str, Any]:
    item = _dict(row) or {}
    return {
        "seq": int(item.get("seq") or 0),
        "id": str(item.get("id") or ""),
        "kind": str(item.get("kind") or "user"),
        "text": str(item.get("body") or ""),
        "created_at": str(item.get("created_at") or ""),
        "sender": {
            "name": str(item.get("sender_name") or "ODDI"),
            "email": str(item.get("sender_email") or ""),
            "is_me": item.get("sender_user_id") is not None and int(item["sender_user_id"]) == viewer_id,
        },
        "ai_status": item.get("ai_status"),
        "ai_error": item.get("ai_error"),
    }


def _get_messages(workspace_id: str, viewer_id: int, after_seq: int = 0, limit: int = 100):
    conn = _connection()
    try:
        _require_membership(conn, workspace_id, viewer_id)
        if after_seq > 0:
            rows = _fetchall(
                conn,
                """SELECT * FROM shared_workspace_messages
                   WHERE workspace_id = ?
                     AND (seq > ? OR ai_status IN ('queued', 'processing'))
                   ORDER BY seq ASC LIMIT ?""",
                (workspace_id, after_seq, limit),
            )
        else:
            rows = _fetchall(
                conn,
                """SELECT * FROM (
                     SELECT * FROM shared_workspace_messages
                     WHERE workspace_id = ? ORDER BY seq DESC LIMIT ?
                   ) recent ORDER BY seq ASC""",
                (workspace_id, limit),
            )
        return [_public_message(row, viewer_id) for row in rows]
    finally:
        conn.close()


def _workspace_details(workspace_id: str, viewer_id: int):
    conn = _connection()
    try:
        workspace = _require_membership(conn, workspace_id, viewer_id)
        workspace_data = _dict(workspace) or {}
        member_rows = _fetchall(
            conn,
            """SELECT user_id, role, display_name, email, joined_at
               FROM shared_workspace_members WHERE workspace_id = ?
               ORDER BY CASE WHEN role = 'owner' THEN 0 ELSE 1 END, joined_at ASC""",
            (workspace_id,),
        )
        members = []
        is_owner = str(workspace_data.get("my_role") or "") == "owner"
        for row in member_rows:
            member = _dict(row) or {}
            member_id = int(member.get("user_id") or 0)
            member_email = str(member.get("email") or "")
            members.append({
                "id": member_id if is_owner else None,
                "name": str(member.get("display_name") or "ODDI member"),
                "email": member_email,
                "role": _public_role(member.get("role")),
                "is_me": member_id == viewer_id,
                "quota": _quota_payload(member_id, member_email),
            })

        invitations = []
        if workspace_data.get("my_role") == "owner":
            invite_rows = _fetchall(
                conn,
                """SELECT id, inviter_name, inviter_email, invitee_email, status,
                          created_at, responded_at, expires_at
                   FROM shared_workspace_invitations
                   WHERE workspace_id = ? AND status != 'revoked'
                   ORDER BY created_at DESC LIMIT 30""",
                (workspace_id,),
            )
            invitations = [_dict(row) or {} for row in invite_rows]

        projects = _workspace_projects(conn, workspace_id, include_tasks=True)
        if not is_owner:
            for project in projects:
                for task in project.get("tasks") or []:
                    task.pop("assigned_user_id", None)

        return {
            "workspace": {
                "id": str(workspace_data.get("id") or ""),
                "name": str(workspace_data.get("name") or "Shared workspace"),
                "my_role": _public_role(workspace_data.get("my_role")),
                "member_count": len(members),
                "max_members": None,
                "ai_busy": bool(workspace_data.get("ai_active_message_id")),
            },
            "members": members,
            "invitations": invitations,
            "projects": projects,
        }
    finally:
        conn.close()


def _workspace_list(user_id: int):
    conn = _connection()
    try:
        rows = _fetchall(
            conn,
            """SELECT w.id, w.name, w.updated_at, m.role AS my_role,
                      (SELECT COUNT(*) FROM shared_workspace_members allm
                       WHERE allm.workspace_id = w.id) AS member_count,
                      (SELECT body FROM shared_workspace_messages msg
                       WHERE msg.workspace_id = w.id ORDER BY msg.seq DESC LIMIT 1) AS last_message,
                      (SELECT MAX(activity.seq) FROM shared_workspace_messages activity
                       WHERE activity.workspace_id = w.id) AS latest_message_seq,
                      (SELECT COUNT(*) FROM shared_workspace_messages unread
                       WHERE unread.workspace_id = w.id
                         AND unread.seq > COALESCE((
                           SELECT reads.last_read_seq FROM shared_workspace_reads reads
                           WHERE reads.workspace_id = w.id AND reads.user_id = m.user_id
                         ), 0)
                         AND (unread.sender_user_id IS NULL OR unread.sender_user_id <> m.user_id)
                      ) AS unread_count
               FROM shared_workspaces w
               JOIN shared_workspace_members m ON m.workspace_id = w.id
               WHERE m.user_id = ?
               ORDER BY COALESCE((SELECT MAX(activity_order.seq) FROM shared_workspace_messages activity_order
                                  WHERE activity_order.workspace_id = w.id), 0) DESC,
                        w.updated_at DESC""",
            (user_id,),
        )
        result = []
        for row in rows:
            workspace_id = str(row["id"])
            projects = _workspace_projects(conn, workspace_id, include_tasks=False)
            result.append({
                "id": str(row["id"]),
                "name": str(row["name"] or "Shared workspace"),
                "updated_at": str(row["updated_at"] or ""),
                "my_role": _public_role(row["my_role"]),
                "member_count": int(row["member_count"] or 0),
                "last_message": str(row["last_message"] or "Start the group conversation"),
                "unread_count": int(row["unread_count"] or 0),
                "projects": projects,
            })
        return result
    finally:
        conn.close()


def _store_workspace_read_marker(conn, workspace_id: str, user_id: int) -> int:
    latest = _fetchone(
        conn,
        "SELECT COALESCE(MAX(seq), 0) AS last_read_seq FROM shared_workspace_messages WHERE workspace_id = ?",
        (workspace_id,),
    )
    last_read_seq = int(latest["last_read_seq"] or 0) if latest else 0
    conn.execute(
        """INSERT INTO shared_workspace_reads (workspace_id, user_id, last_read_seq)
           VALUES (?, ?, ?)
           ON CONFLICT (workspace_id, user_id) DO UPDATE SET
             last_read_seq = CASE
               WHEN excluded.last_read_seq > shared_workspace_reads.last_read_seq
               THEN excluded.last_read_seq ELSE shared_workspace_reads.last_read_seq END""",
        (workspace_id, user_id, last_read_seq),
    )
    return last_read_seq


def _mark_workspace_read(workspace_id: str, user_id: int):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        _require_membership(conn, workspace_id, user_id)
        last_read_seq = _store_workspace_read_marker(conn, workspace_id, user_id)
        conn.commit()
        return {"success": True, "last_read_seq": last_read_seq}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not mark shared workspace %s as read", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not update your unread messages.")
    finally:
        conn.close()


def _invitations_for_email(email: str):
    conn = _connection()
    try:
        now = _timestamp()
        conn.execute(
            """UPDATE shared_workspace_invitations SET status = 'expired', responded_at = ?
               WHERE lower(invitee_email) = ? AND status = 'pending' AND expires_at <= ?""",
            (now, email, now),
        )
        conn.commit()
        rows = _fetchall(
            conn,
            """SELECT i.id, i.workspace_id, i.inviter_name, i.inviter_email,
                      i.invitee_email, i.created_at, i.expires_at, w.name AS workspace_name
               FROM shared_workspace_invitations i
               JOIN shared_workspaces w ON w.id = i.workspace_id
               WHERE lower(i.invitee_email) = ? AND i.status = 'pending'
                 AND i.expires_at > ? ORDER BY i.created_at DESC""",
            (email, now),
        )
        return [_dict(row) or {} for row in rows]
    finally:
        conn.close()


def _unread_invitation_responses(user_id: int):
    conn = _connection()
    try:
        rows = _fetchall(
            conn,
            """SELECT i.id, i.invitee_email, i.status, i.responded_at,
                      w.name AS workspace_name
               FROM shared_workspace_invitations i
               JOIN shared_workspaces w ON w.id = i.workspace_id
               WHERE w.owner_user_id = ? AND i.status IN ('accepted', 'rejected')
                 AND i.inviter_notified_at IS NULL
               ORDER BY i.responded_at ASC LIMIT 30""",
            (user_id,),
        )
        return [_dict(row) or {} for row in rows]
    finally:
        conn.close()


def _ack_invitation_responses(user_id: int, invitation_ids: Any):
    ids = list(dict.fromkeys(
        value for value in (str(item or "").strip() for item in (invitation_ids or [])[:30])
        if re.fullmatch(r"[0-9a-fA-F-]{36}", value)
    )) if isinstance(invitation_ids, list) else []
    if not ids:
        return {"success": True, "acknowledged": 0}

    conn = _connection()
    try:
        _begin_write(conn, "shared")
        now = _timestamp()
        acknowledged = 0
        for invitation_id in ids:
            result = conn.execute(
                """UPDATE shared_workspace_invitations
                   SET inviter_notified_at = ?
                   WHERE id = ? AND status IN ('accepted', 'rejected')
                     AND inviter_notified_at IS NULL
                     AND workspace_id IN (
                       SELECT id FROM shared_workspaces WHERE owner_user_id = ?
                     )""",
                (now, invitation_id, user_id),
            )
            acknowledged += max(0, int(result.rowcount or 0))
        conn.commit()
        return {"success": True, "acknowledged": acknowledged}
    except Exception:
        conn.rollback()
        logger.exception("Could not acknowledge shared workspace notifications for user %s", user_id)
        raise HTTPException(status_code=500, detail="ODDI could not update workspace notifications.")
    finally:
        conn.close()


def _validate_email(email: str) -> str:
    email = str(email or "").strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return email


def _create_workspace(user: dict[str, Any], name: str):
    name = str(name or "").strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise HTTPException(status_code=400, detail=f"Choose a group name of 1 to {MAX_NAME_LENGTH} characters.")
    workspace_id = str(uuid.uuid4())
    now = _timestamp()
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        conn.execute(
            """INSERT INTO shared_workspaces (id, name, owner_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (workspace_id, name, user["id"], now, now),
        )
        conn.execute(
            """INSERT INTO shared_workspace_members
               (workspace_id, user_id, role, display_name, email, joined_at)
               VALUES (?, ?, 'owner', ?, ?, ?)""",
            (workspace_id, user["id"], user["name"], user["email"], now),
        )
        _store_workspace_read_marker(conn, workspace_id, user["id"])
        conn.commit()
        return _workspace_details(workspace_id, user["id"])
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not create shared workspace")
        raise HTTPException(status_code=500, detail="ODDI could not create that group. Please try again.")
    finally:
        conn.close()


def _create_project(user: dict[str, Any], payload: dict[str, Any]):
    name = str(payload.get("name") or "").strip()
    goal = str(payload.get("goal") or "").strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise HTTPException(status_code=400, detail=f"Choose a project name of 1 to {MAX_NAME_LENGTH} characters.")
    if not goal or len(goal) > MAX_PROJECT_GOAL_LENGTH:
        raise HTTPException(status_code=400, detail=f"Add a project goal of 1 to {MAX_PROJECT_GOAL_LENGTH} characters.")
    deadline = str(payload.get("deadline") or "").strip() or None
    if deadline:
        try:
            deadline = date.fromisoformat(deadline).isoformat()
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Choose a valid project deadline.") from error

    workspace_id = str(payload.get("workspace_id") or "").strip()
    create_group = not workspace_id
    group_name = str(payload.get("group_name") or "").strip()
    if create_group:
        if not group_name:
            group_name = name
        if len(group_name) > MAX_NAME_LENGTH:
            raise HTTPException(status_code=400, detail=f"Choose a group name of 1 to {MAX_NAME_LENGTH} characters.")
        workspace_id = str(uuid.uuid4())

    project_id = str(uuid.uuid4())
    now = _timestamp()
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        if create_group:
            conn.execute(
                """INSERT INTO shared_workspaces (id, name, owner_user_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (workspace_id, group_name, user["id"], now, now),
            )
            conn.execute(
                """INSERT INTO shared_workspace_members
                   (workspace_id, user_id, role, display_name, email, joined_at)
                   VALUES (?, ?, 'owner', ?, ?, ?)""",
                (workspace_id, user["id"], user["name"], user["email"], now),
            )
            _store_workspace_read_marker(conn, workspace_id, user["id"])
        else:
            workspace = _require_membership(conn, workspace_id, user["id"])
            if str(workspace["my_role"]) != "owner":
                raise HTTPException(status_code=403, detail="Only the group admin can create a project in this group.")

        conn.execute(
            """INSERT INTO shared_workspace_projects
               (id, workspace_id, name, goal, deadline, workflow_status, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'offered', ?, ?, ?)""",
            (project_id, workspace_id, name, goal, deadline, user["id"], now, now),
        )
        conn.execute("UPDATE shared_workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
        conn.commit()
        details = _workspace_details(workspace_id, user["id"])
        project = next((item for item in details["projects"] if item["id"] == project_id), None)
        return {"workspace": details["workspace"], "project": project}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not create shared workspace project")
        raise HTTPException(status_code=500, detail="ODDI could not create that project. Please try again.")
    finally:
        conn.close()


def _project_access(conn, project_id: str, user_id: int):
    project = _fetchone(conn, "SELECT * FROM shared_workspace_projects WHERE id = ?", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="That project is not available to your account.")
    workspace_id = str(project["workspace_id"])
    membership = _require_membership(conn, workspace_id, user_id)
    return _dict(project) or {}, membership


def _project_snapshot(project_id: str, user_id: int):
    conn = _connection()
    try:
        project = _fetchone(conn, "SELECT workspace_id FROM shared_workspace_projects WHERE id = ?", (project_id,))
        if not project:
            raise HTTPException(status_code=404, detail="That project is no longer available.")
        workspace_id = str(project["workspace_id"])
    finally:
        conn.close()
    details = _workspace_details(workspace_id, user_id)
    item = next((entry for entry in details["projects"] if entry["id"] == project_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="That project is no longer available.")
    return {"workspace": details["workspace"], "project": item, "members": details["members"]}


def _create_project_task(user: dict[str, Any], project_id: str, payload: dict[str, Any]):
    title = str(payload.get("title") or "").strip()
    details = str(payload.get("details") or "").strip()
    if not title or len(title) > MAX_TASK_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Enter a task title of 1 to {MAX_TASK_TITLE_LENGTH} characters.")
    if len(details) > 2000:
        raise HTTPException(status_code=400, detail="Task details can be up to 2,000 characters.")
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        project, membership = _project_access(conn, project_id, user["id"])
        if str(membership["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can add project tasks.")
        order = _fetchone(
            conn,
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_position FROM shared_workspace_project_tasks WHERE project_id = ?",
            (project_id,),
        )
        now = _timestamp()
        conn.execute(
            """INSERT INTO shared_workspace_project_tasks
               (id, workspace_id, project_id, title, details, status, sort_order, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?)""",
            (str(uuid.uuid4()), project["workspace_id"], project_id, title, details,
             int(order["next_position"] or 0), user["id"], now, now),
        )
        conn.execute("UPDATE shared_workspace_projects SET updated_at = ? WHERE id = ?", (now, project_id))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not add a task to shared project %s", project_id)
        raise HTTPException(status_code=500, detail="ODDI could not add that task.")
    finally:
        conn.close()
    return _project_snapshot(project_id, user["id"])


def _update_project_task(user: dict[str, Any], project_id: str, task_id: str, payload: dict[str, Any]):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        project, membership = _project_access(conn, project_id, user["id"])
        task = _fetchone(
            conn,
            "SELECT * FROM shared_workspace_project_tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if not task:
            raise HTTPException(status_code=404, detail="That task is no longer available.")
        is_admin = str(membership["my_role"]) == "owner"
        updates: dict[str, Any] = {}
        if "status" in payload:
            status = str(payload.get("status") or "").strip().casefold()
            if status not in {"todo", "done"}:
                raise HTTPException(status_code=400, detail="Choose a valid task status.")
            updates["status"] = status
        if "assigned_user_id" in payload:
            if not is_admin:
                raise HTTPException(status_code=403, detail="Only the group admin can assign project tasks.")
            assignee = payload.get("assigned_user_id")
            if assignee in (None, ""):
                updates["assigned_user_id"] = None
            else:
                try:
                    assignee = int(assignee)
                except (TypeError, ValueError, OverflowError) as error:
                    raise HTTPException(status_code=400, detail="Choose a current group member.") from error
                member = _fetchone(
                    conn,
                    "SELECT user_id FROM shared_workspace_members WHERE workspace_id = ? AND user_id = ?",
                    (project["workspace_id"], assignee),
                )
                if not member:
                    raise HTTPException(status_code=400, detail="Tasks can only be assigned to current group members.")
                updates["assigned_user_id"] = assignee
        if "title" in payload or "details" in payload:
            if not is_admin:
                raise HTTPException(status_code=403, detail="Only the group admin can edit project tasks.")
            if "title" in payload:
                title = str(payload.get("title") or "").strip()
                if not title or len(title) > MAX_TASK_TITLE_LENGTH:
                    raise HTTPException(status_code=400, detail=f"Enter a task title of 1 to {MAX_TASK_TITLE_LENGTH} characters.")
                updates["title"] = title
            if "details" in payload:
                details = str(payload.get("details") or "").strip()
                if len(details) > 2000:
                    raise HTTPException(status_code=400, detail="Task details can be up to 2,000 characters.")
                updates["details"] = details
        if not updates:
            raise HTTPException(status_code=400, detail="Choose a task update.")
        updates["updated_at"] = _timestamp()
        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(
            f"UPDATE shared_workspace_project_tasks SET {assignments} WHERE id = ? AND project_id = ?",
            (*updates.values(), task_id, project_id),
        )
        conn.execute("UPDATE shared_workspace_projects SET updated_at = ? WHERE id = ?", (updates["updated_at"], project_id))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not update project task %s", task_id)
        raise HTTPException(status_code=500, detail="ODDI could not update that task.")
    finally:
        conn.close()
    return _project_snapshot(project_id, user["id"])


def _delete_project_task(user: dict[str, Any], project_id: str, task_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        project, membership = _project_access(conn, project_id, user["id"])
        if str(membership["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can remove project tasks.")
        deleted = conn.execute(
            "DELETE FROM shared_workspace_project_tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if not deleted.rowcount:
            raise HTTPException(status_code=404, detail="That task is no longer available.")
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not remove project task %s", task_id)
        raise HTTPException(status_code=500, detail="ODDI could not remove that task.")
    finally:
        conn.close()
    return _project_snapshot(project_id, user["id"])


def _claim_project_workflow(user: dict[str, Any], project_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        project, _membership = _project_access(conn, project_id, user["id"])
        status = str(project.get("workflow_status") or "offered")
        if status == "ready":
            conn.rollback()
            return {"ready": True, **_project_snapshot(project_id, user["id"])}
        updated_at = str(project.get("updated_at") or "")
        if status == "generating" and updated_at:
            try:
                started = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                if _now() - started < timedelta(minutes=30):
                    raise HTTPException(status_code=409, detail="ODDI is already creating this project's workflow.")
            except ValueError:
                pass
        now = _timestamp()
        conn.execute(
            "DELETE FROM shared_workspace_user_leases WHERE workspace_id = ? AND message_id = ?",
            (project["workspace_id"], project_id),
        )
        lease = conn.execute(
            """INSERT INTO shared_workspace_user_leases (user_id, workspace_id, message_id, created_at)
               VALUES (?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING""",
            (user["id"], project["workspace_id"], project_id, now),
        )
        if not lease.rowcount:
            raise HTTPException(status_code=429, detail="Finish your current ODDI request before creating a project workflow.")
        conn.execute(
            "UPDATE shared_workspace_projects SET workflow_status = 'generating', updated_at = ? WHERE id = ?",
            (now, project_id),
        )
        conn.commit()
        project["workflow_status"] = "generating"
        project["updated_at"] = now
        return {"ready": False, "project": project}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not start a project workflow for %s", project_id)
        raise HTTPException(status_code=500, detail="ODDI could not start that workflow.")
    finally:
        conn.close()


def _parse_workflow_tasks(response: str) -> list[dict[str, str]]:
    raw = str(response or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.IGNORECASE | re.DOTALL)
    candidates = [fenced.group(1).strip()] if fenced else [raw]
    if not fenced:
        left, right = raw.find("{"), raw.rfind("}")
        if left >= 0 and right > left:
            candidates.append(raw[left:right + 1])
        left, right = raw.find("["), raw.rfind("]")
        if left >= 0 and right > left:
            candidates.append(raw[left:right + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict):
            data = data.get("tasks") or data.get("checklist") or []
        if not isinstance(data, list):
            continue
        tasks = []
        for item in data[:20]:
            if isinstance(item, str):
                title, details = item.strip(), ""
            elif isinstance(item, dict):
                title = str(item.get("title") or item.get("task") or item.get("name") or "").strip()
                details = str(item.get("details") or item.get("description") or "").strip()
            else:
                continue
            if title:
                tasks.append({"title": title[:MAX_TASK_TITLE_LENGTH], "details": details[:2000]})
        if tasks:
            return tasks
    # Accept a plain numbered/bulleted checklist if the model ignored JSON mode.
    tasks = []
    for line in raw.splitlines():
        match = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$", line)
        if match:
            title = re.sub(r"\*\*|__|`", "", match.group(1)).strip()
            if title:
                tasks.append({"title": title[:MAX_TASK_TITLE_LENGTH], "details": ""})
    return tasks[:20]


def _save_project_workflow(user: dict[str, Any], project_id: str, tasks: list[dict[str, str]]):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        project, _membership = _project_access(conn, project_id, user["id"])
        if str(project.get("workflow_status") or "") == "ready":
            conn.execute(
                "DELETE FROM shared_workspace_user_leases WHERE user_id = ? AND message_id = ?",
                (user["id"], project_id),
            )
            conn.commit()
            return _project_snapshot(project_id, user["id"])
        now = _timestamp()
        for position, task in enumerate(tasks):
            conn.execute(
                """INSERT INTO shared_workspace_project_tasks
                   (id, workspace_id, project_id, title, details, status, sort_order, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?)""",
                (str(uuid.uuid4()), project["workspace_id"], project_id, task["title"], task["details"],
                 position, user["id"], now, now),
            )
        conn.execute(
            "UPDATE shared_workspace_projects SET workflow_status = 'ready', updated_at = ? WHERE id = ?",
            (now, project_id),
        )
        conn.execute(
            "DELETE FROM shared_workspace_user_leases WHERE user_id = ? AND message_id = ?",
            (user["id"], project_id),
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not save workflow tasks for project %s", project_id)
        raise HTTPException(status_code=500, detail="ODDI could not save the generated checklist.")
    finally:
        conn.close()
    return _project_snapshot(project_id, user["id"])


def _fail_project_workflow(project_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        conn.execute(
            "UPDATE shared_workspace_projects SET workflow_status = 'failed', updated_at = ? WHERE id = ? AND workflow_status = 'generating'",
            (_timestamp(), project_id),
        )
        conn.execute("DELETE FROM shared_workspace_user_leases WHERE message_id = ?", (project_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Could not reset failed project workflow %s", project_id)
    finally:
        conn.close()


async def _generate_project_workflow(user: dict[str, Any], project: dict[str, Any]):
    project_id = str(project.get("id") or "")
    identity = _shared_workspace_identity(user["id"], user["email"])
    prompt = (
        "Create a practical, ordered project workflow checklist from the project details below. "
        "Return JSON only, with this exact shape: {\"tasks\":[{\"title\":\"Short actionable task\",\"details\":\"One concise sentence\"}]}. "
        "Provide 5 to 12 useful tasks, unless the goal clearly needs fewer. Do not assign people, invent facts, or add commentary outside the JSON. "
        "Make the steps realistic for the deadline and suitable for a small group working together.\n\n"
        f"Project: {project.get('name') or ''}\n"
        f"Goal: {project.get('goal') or ''}\n"
        f"Deadline: {project.get('deadline') or 'No deadline'}"
    )
    try:
        response = await run_in_threadpool(
            process_message,
            prompt,
            [],
            [],
            user_id=user["id"],
            identity=identity,
            long_term_memory_enabled=False,
            allow_user_knowledge=False,
            allow_account_actions=False,
        )
        tasks = _parse_workflow_tasks(str(response or ""))
        if not tasks:
            logger.warning("ODDI returned no structured workflow tasks for project %s", project_id)
            await run_in_threadpool(_fail_project_workflow, project_id)
            return
        await run_in_threadpool(_save_project_workflow, user, project_id, tasks)
    except Exception:
        logger.exception("Could not generate checklist for shared project %s", project_id)
        await run_in_threadpool(_fail_project_workflow, project_id)


def _invite_member(user: dict[str, Any], workspace_id: str, email: str):
    email = _validate_email(email)
    if email == user["email"]:
        raise HTTPException(status_code=400, detail="You are already a member of this group.")
    try:
        account = get_user_by_email(email)
    except Exception as error:
        logger.warning("Invite account lookup failed: %s", type(error).__name__)
        account = None
    invitee_id = None
    if account:
        try:
            invitee_id = int(account["id"])
        except (TypeError, ValueError, KeyError):
            invitee_id = None

    conn = _connection()
    try:
        _begin_write(conn, "shared")
        workspace = _require_membership(conn, workspace_id, user["id"])
        if str(workspace["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can invite members.")
        if _use_postgres("shared"):
            _fetchone(conn, "SELECT id FROM shared_workspaces WHERE id = ? FOR UPDATE", (workspace_id,))
        now = _timestamp()
        if invitee_id is not None and _fetchone(
            conn,
            "SELECT 1 FROM shared_workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, invitee_id),
        ):
            raise HTTPException(status_code=409, detail="That account is already in this group.")
        existing = _fetchone(
            conn,
            """SELECT id FROM shared_workspace_invitations
               WHERE workspace_id = ? AND lower(invitee_email) = ? AND status = 'pending' AND expires_at > ?""",
            (workspace_id, email, now),
        )
        if existing:
            raise HTTPException(status_code=409, detail="There is already a pending invitation for that email.")
        invitation_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO shared_workspace_invitations
               (id, workspace_id, inviter_user_id, inviter_name, inviter_email,
                invitee_user_id, invitee_email, status, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (
                invitation_id,
                workspace_id,
                user["id"],
                user["name"],
                user["email"],
                invitee_id,
                email,
                now,
                _timestamp(_now() + INVITE_LIFETIME),
            ),
        )
        conn.execute("UPDATE shared_workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
        conn.commit()
        return {"success": True, "invitation_id": invitation_id, "email": email, "expires_at": _timestamp(_now() + INVITE_LIFETIME)}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not invite member to shared workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not send that invitation. Please try again.")
    finally:
        conn.close()


def _respond_to_invitation(user: dict[str, Any], invitation_id: str, action: str):
    action = str(action or "").strip().casefold()
    if action not in {"accept", "reject"}:
        raise HTTPException(status_code=400, detail="Choose accept or reject.")
    now = _timestamp()
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        invite = _fetchone(
            conn,
            """SELECT * FROM shared_workspace_invitations
               WHERE id = ? AND lower(invitee_email) = ?""",
            (invitation_id, user["email"]),
        )
        if not invite:
            raise HTTPException(status_code=404, detail="That invitation was not found for this account.")
        if str(invite["status"]) != "pending":
            raise HTTPException(status_code=409, detail="This invitation has already been answered.")
        if str(invite["expires_at"]) <= now:
            conn.execute(
                "UPDATE shared_workspace_invitations SET status = 'expired', responded_at = ? WHERE id = ?",
                (now, invitation_id),
            )
            conn.commit()
            raise HTTPException(status_code=410, detail="This invitation has expired.")

        workspace_id = str(invite["workspace_id"])
        if action == "accept":
            if _use_postgres("shared"):
                _fetchone(conn, "SELECT id FROM shared_workspaces WHERE id = ? FOR UPDATE", (workspace_id,))
            already_member = _fetchone(
                conn,
                "SELECT 1 FROM shared_workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user["id"]),
            )
            if not already_member:
                conn.execute(
                    """INSERT INTO shared_workspace_members
                       (workspace_id, user_id, role, display_name, email, joined_at)
                       VALUES (?, ?, 'member', ?, ?, ?)""",
                    (workspace_id, user["id"], user["name"], user["email"], now),
                )
                _store_workspace_read_marker(conn, workspace_id, user["id"])
            status = "accepted"
        else:
            status = "rejected"

        conn.execute(
            """UPDATE shared_workspace_invitations
               SET status = ?, invitee_user_id = ?, responded_at = ? WHERE id = ? AND status = 'pending'""",
            (status, user["id"], now, invitation_id),
        )
        conn.execute("UPDATE shared_workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
        conn.commit()
        return {"success": True, "status": status, "workspace_id": workspace_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not respond to shared workspace invitation %s", invitation_id)
        raise HTTPException(status_code=500, detail="ODDI could not update that invitation. Please try again.")
    finally:
        conn.close()


def _rename_workspace(user: dict[str, Any], workspace_id: str, name: str):
    name = str(name or "").strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise HTTPException(status_code=400, detail=f"Choose a group name of 1 to {MAX_NAME_LENGTH} characters.")
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        workspace = _require_membership(conn, workspace_id, user["id"])
        if str(workspace["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can rename this group.")
        conn.execute("UPDATE shared_workspaces SET name = ?, updated_at = ? WHERE id = ?", (name, _timestamp(), workspace_id))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not rename shared workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not rename this group.")
    finally:
        conn.close()
    return _workspace_details(workspace_id, user["id"])


def _remove_member(user: dict[str, Any], workspace_id: str, member_id: int):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        workspace = _require_membership(conn, workspace_id, user["id"])
        if str(workspace["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can remove members.")
        if member_id == int(workspace["owner_user_id"]):
            raise HTTPException(status_code=400, detail="The group admin cannot remove themself. Delete the group to close it.")
        conn.execute(
            "UPDATE shared_workspace_project_tasks SET assigned_user_id = NULL, updated_at = ? WHERE workspace_id = ? AND assigned_user_id = ?",
            (_timestamp(), workspace_id, member_id),
        )
        deleted = conn.execute(
            "DELETE FROM shared_workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, member_id),
        ).rowcount
        if not deleted:
            raise HTTPException(status_code=404, detail="That person is no longer in this group.")
        conn.execute("DELETE FROM shared_workspace_reads WHERE workspace_id = ? AND user_id = ?", (workspace_id, member_id))
        conn.execute("UPDATE shared_workspaces SET updated_at = ? WHERE id = ?", (_timestamp(), workspace_id))
        conn.commit()
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not remove member from shared workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not remove that member.")
    finally:
        conn.close()


def _leave_workspace(user: dict[str, Any], workspace_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        workspace = _require_membership(conn, workspace_id, user["id"])
        if str(workspace["my_role"]) == "owner":
            raise HTTPException(status_code=409, detail="The group admin needs to delete the group before leaving it.")
        conn.execute(
            "UPDATE shared_workspace_project_tasks SET assigned_user_id = NULL, updated_at = ? WHERE workspace_id = ? AND assigned_user_id = ?",
            (_timestamp(), workspace_id, user["id"]),
        )
        conn.execute(
            "DELETE FROM shared_workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user["id"]),
        )
        conn.execute("DELETE FROM shared_workspace_reads WHERE workspace_id = ? AND user_id = ?", (workspace_id, user["id"]))
        conn.execute("UPDATE shared_workspaces SET updated_at = ? WHERE id = ?", (_timestamp(), workspace_id))
        conn.commit()
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not leave shared workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not leave this group.")
    finally:
        conn.close()


def _delete_workspace(user: dict[str, Any], workspace_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        workspace = _require_membership(conn, workspace_id, user["id"])
        if str(workspace["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can delete this group.")
        conn.execute("DELETE FROM shared_workspaces WHERE id = ?", (workspace_id,))
        conn.commit()
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not delete shared workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not delete this group.")
    finally:
        conn.close()


def _revoke_invitation(user: dict[str, Any], workspace_id: str, invitation_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        workspace = _require_membership(conn, workspace_id, user["id"])
        if str(workspace["my_role"]) != "owner":
            raise HTTPException(status_code=403, detail="Only the group admin can cancel invitations.")
        result = conn.execute(
            """UPDATE shared_workspace_invitations SET status = 'revoked', responded_at = ?
               WHERE id = ? AND workspace_id = ? AND status = 'pending'""",
            (_timestamp(), invitation_id, workspace_id),
        )
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="That pending invitation was not found.")
        conn.commit()
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Could not cancel shared workspace invitation %s", invitation_id)
        raise HTTPException(status_code=500, detail="ODDI could not cancel that invitation.")
    finally:
        conn.close()


def _insert_user_message(user: dict[str, Any], workspace_id: str, body: str, client_id: str, ai_request: str | None):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        _require_membership(conn, workspace_id, user["id"])
        previous = _fetchone(
            conn,
            "SELECT * FROM shared_workspace_messages WHERE workspace_id = ? AND client_message_id = ?",
            (workspace_id, client_id),
        )
        if previous:
            if previous["sender_user_id"] is None or int(previous["sender_user_id"]) != user["id"]:
                raise HTTPException(status_code=409, detail="That message ID has already been used.")
            conn.commit()
            return _public_message(previous, user["id"])

        message_id = str(uuid.uuid4())
        now = _timestamp()
        conn.execute(
            """INSERT INTO shared_workspace_messages
               (id, workspace_id, sender_user_id, sender_name, sender_email, kind,
                body, created_at, client_message_id, ai_status)
               VALUES (?, ?, ?, ?, ?, 'user', ?, ?, ?, ?)""",
            (message_id, workspace_id, user["id"], user["name"], user["email"], body, now, client_id, "queued" if ai_request is not None else None),
        )
        saved = _fetchone(conn, "SELECT * FROM shared_workspace_messages WHERE id = ?", (message_id,))
        conn.execute("UPDATE shared_workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
        conn.commit()
        return _public_message(saved, user["id"])
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        # A duplicate request can race across web workers. The unique key
        # makes the winning message canonical; return it instead of creating
        # a second group turn or charging a second AI request.
        try:
            previous = _fetchone(
                conn,
                "SELECT * FROM shared_workspace_messages WHERE workspace_id = ? AND client_message_id = ?",
                (workspace_id, client_id),
            )
            if previous and previous["sender_user_id"] is not None and int(previous["sender_user_id"]) == user["id"]:
                return _public_message(previous, user["id"])
            if previous:
                raise HTTPException(status_code=409, detail="That message ID has already been used.")
        except HTTPException:
            raise
        except Exception:
            pass
        logger.exception("Could not save shared workspace message in %s", workspace_id)
        raise HTTPException(status_code=500, detail="ODDI could not send that message. Please try again.")
    finally:
        conn.close()


def _list_queued_workspaces():
    conn = _connection()
    try:
        rows = _fetchall(
            conn,
            """SELECT DISTINCT w.id FROM shared_workspaces w
               JOIN shared_workspace_messages m ON m.workspace_id = w.id
               WHERE w.ai_active_message_id IS NULL AND m.ai_status = 'queued'
               ORDER BY w.id LIMIT 60""",
        )
        return [str(row["id"]) for row in rows]
    finally:
        conn.close()


def _claim_next_job(workspace_id: str):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        active = _fetchone(conn, "SELECT ai_active_message_id FROM shared_workspaces WHERE id = ?", (workspace_id,))
        if not active or active["ai_active_message_id"]:
            conn.rollback()
            return None
        message = _fetchone(
            conn,
            """SELECT * FROM shared_workspace_messages
               WHERE workspace_id = ? AND ai_status = 'queued' ORDER BY seq ASC LIMIT 1""",
            (workspace_id,),
        )
        if not message:
            conn.rollback()
            return None
        now = _timestamp()
        message_id = str(message["id"])
        lock_result = conn.execute(
            "UPDATE shared_workspaces SET ai_active_message_id = ? WHERE id = ? AND ai_active_message_id IS NULL",
            (message_id, workspace_id),
        )
        if not lock_result.rowcount:
            conn.rollback()
            return None
        lease = conn.execute(
            """INSERT INTO shared_workspace_user_leases (user_id, workspace_id, message_id, created_at)
               VALUES (?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING""",
            (message["sender_user_id"], workspace_id, message_id, now),
        )
        if not lease.rowcount:
            conn.execute("UPDATE shared_workspaces SET ai_active_message_id = NULL WHERE id = ? AND ai_active_message_id = ?", (workspace_id, message_id))
            conn.commit()
            return None
        conn.execute(
            "UPDATE shared_workspace_messages SET ai_status = 'processing', ai_started_at = ?, ai_error = NULL WHERE id = ? AND ai_status = 'queued'",
            (now, message_id),
        )
        conn.commit()
        return _dict(message)
    except Exception:
        conn.rollback()
        logger.exception("Could not claim a shared workspace AI request in %s", workspace_id)
        return None
    finally:
        conn.close()


def _job_context(job: dict[str, Any]):
    conn = _connection()
    try:
        rows = _fetchall(
            conn,
            """SELECT seq, sender_name, kind, body FROM shared_workspace_messages
               WHERE workspace_id = ? AND seq < ? ORDER BY seq DESC LIMIT 40""",
            (job["workspace_id"], job["seq"]),
        )
        return list(reversed([_dict(row) or {} for row in rows]))
    finally:
        conn.close()


def _job_project_context(workspace_id: str) -> str:
    conn = _connection()
    try:
        projects = _workspace_projects(conn, workspace_id, include_tasks=True)
        if not projects:
            return ""
        lines = ["Project context shared with this group:"]
        for project in projects[:12]:
            lines.append(f"- Project: {project.get('name') or 'Untitled'}")
            lines.append(f"  Goal: {project.get('goal') or 'Not specified'}")
            lines.append(f"  Deadline: {project.get('deadline') or 'No deadline'}")
            tasks = project.get("tasks") or []
            if tasks:
                task_summary = "; ".join(
                    f"{'[done] ' if task.get('status') == 'done' else ''}{task.get('title', '')}"
                    for task in tasks[:20]
                )
                lines.append(f"  Checklist: {task_summary}")
        lines.append("Use the relevant project's goal, deadline, and checklist when answering. If the request could refer to multiple projects, ask which one.")
        return "\n".join(lines)
    except Exception:
        logger.exception("Could not load project context for shared group %s", workspace_id)
        return ""
    finally:
        conn.close()


def _save_ai_result(job: dict[str, Any], result: str, failed: bool = False):
    conn = _connection()
    try:
        _begin_write(conn, "shared")
        now = _timestamp()
        if failed:
            text = "I couldn't complete that reply because of a temporary issue. Please try your `@ODDI` request again."
            conn.execute(
                "UPDATE shared_workspace_messages SET ai_status = 'failed', ai_error = ? WHERE id = ?",
                ("ODDI could not complete this response.", job["id"]),
            )
        else:
            text = str(result or "").strip() or "I couldn't produce a reply for that message. Please try again."
            conn.execute(
                "UPDATE shared_workspace_messages SET ai_status = 'completed', ai_error = NULL WHERE id = ?",
                (job["id"],),
            )
        conn.execute(
            """INSERT INTO shared_workspace_messages
               (id, workspace_id, sender_name, kind, body, created_at, client_message_id)
               VALUES (?, ?, 'ODDI', 'assistant', ?, ?, ?)""",
            (str(uuid.uuid4()), job["workspace_id"], text[:60000], now, str(uuid.uuid4())),
        )
        conn.execute(
            "UPDATE shared_workspaces SET ai_active_message_id = NULL, updated_at = ? WHERE id = ? AND ai_active_message_id = ?",
            (now, job["workspace_id"], job["id"]),
        )
        conn.execute(
            "DELETE FROM shared_workspace_user_leases WHERE user_id = ? AND message_id = ?",
            (job["sender_user_id"], job["id"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Could not persist shared ODDI response for request %s", job.get("id"))
        raise
    finally:
        conn.close()


async def _run_claimed_job(job: dict[str, Any]):
    try:
        context_rows = await run_in_threadpool(_job_context, job)
        project_context = await run_in_threadpool(_job_project_context, str(job["workspace_id"]))
        history = []
        for item in context_rows:
            kind = str(item.get("kind") or "user")
            if kind not in {"user", "assistant"}:
                continue
            speaker = str(item.get("sender_name") or "ODDI" if kind == "assistant" else item.get("sender_name") or "Member")
            content = str(item.get("body") or "")
            if kind == "user":
                match = _AI_PREFIX.match(content)
                if match:
                    content = match.group(1).strip()
                content = f"{speaker}: {content}"
            history.append({"role": kind, "content": content})

        request_match = _AI_PREFIX.match(str(job.get("body") or ""))
        question = request_match.group(1).strip() if request_match else str(job.get("body") or "").strip()
        group_prompt = (
            "This is a shared ODDI group workspace. Answer the current request for the whole group, "
            "using only the messages in this shared conversation. Do not use or reveal any member's "
            "private chats, saved memories, or personal files.\n\n"
            f"{project_context}\n\n"
            f"{job.get('sender_name') or 'A group member'} asks: {question}"
        )
        identity = _shared_workspace_identity(
            job["sender_user_id"],
            str(job.get("sender_email") or ""),
        )
        response = await run_in_threadpool(
            process_message,
            group_prompt,
            [],
            history,
            user_id=job["sender_user_id"],
            identity=identity,
            long_term_memory_enabled=False,
            allow_user_knowledge=False,
            allow_account_actions=False,
        )
        await run_in_threadpool(_save_ai_result, job, str(response or ""), False)
    except Exception:
        logger.exception("Shared workspace AI generation failed workspace=%s request=%s", job.get("workspace_id"), job.get("id"))
        try:
            await run_in_threadpool(_save_ai_result, job, "", True)
        except Exception:
            pass


async def shared_workspace_queue_worker():
    """Claim queued group requests from SQL, so restarts do not lose messages."""
    running: set[asyncio.Task] = set()
    last_recovery = 0.0
    while True:
        try:
            if time.monotonic() - last_recovery >= 30:
                await run_in_threadpool(_recover_stale_jobs)
                last_recovery = time.monotonic()
            workspace_ids = await run_in_threadpool(_list_queued_workspaces)
            for workspace_id in workspace_ids:
                job = await run_in_threadpool(_claim_next_job, workspace_id)
                if not job:
                    continue
                task = asyncio.create_task(_run_claimed_job(job))
                running.add(task)
                task.add_done_callback(running.discard)
        except asyncio.CancelledError:
            for task in list(running):
                task.cancel()
            raise
        except Exception as error:
            logger.warning("Shared workspace queue scan failed: %s", type(error).__name__)
        await asyncio.sleep(0.65)


def _recover_stale_jobs():
    """Release abandoned claims after a process restart without regenerating."""
    cutoff = _timestamp(_now() - timedelta(minutes=30))
    stale_jobs = []
    conn = _connection()
    try:
        stale = _fetchall(
            conn,
            """SELECT * FROM shared_workspace_messages
               WHERE ai_status = 'processing' AND ai_started_at < ? ORDER BY seq ASC LIMIT 100""",
            (cutoff,),
        )
        stale_jobs = [_dict(row) or {} for row in stale]
        _begin_write(conn, "shared")
        stale_projects = _fetchall(
            conn,
            """SELECT id, workspace_id FROM shared_workspace_projects
               WHERE workflow_status = 'generating' AND updated_at < ? LIMIT 100""",
            (cutoff,),
        )
        for project in stale_projects:
            conn.execute(
                "UPDATE shared_workspace_projects SET workflow_status = 'failed', updated_at = ? WHERE id = ? AND workflow_status = 'generating'",
                (_timestamp(), project["id"]),
            )
            conn.execute(
                "DELETE FROM shared_workspace_user_leases WHERE workspace_id = ? AND message_id = ?",
                (project["workspace_id"], project["id"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Could not recover abandoned shared project workflow claims")
    finally:
        conn.close()
    for job in stale_jobs:
        try:
            _save_ai_result(job, "", True)
        except Exception:
            logger.warning("Could not release stale shared AI request %s", job.get("id"))


def cleanup_deleted_account(user_id: int):
    """Remove deleted accounts from groups and close groups they owned."""
    try:
        conn = _connection()
    except Exception:
        return
    try:
        _begin_write(conn, "shared")
        owned = _fetchall(conn, "SELECT id FROM shared_workspaces WHERE owner_user_id = ?", (user_id,))
        for row in owned:
            conn.execute("DELETE FROM shared_workspaces WHERE id = ?", (row["id"],))
        conn.execute(
            "UPDATE shared_workspace_project_tasks SET assigned_user_id = NULL, updated_at = ? WHERE assigned_user_id = ?",
            (_timestamp(), user_id),
        )
        conn.execute("DELETE FROM shared_workspace_members WHERE user_id = ?", (user_id,))
        conn.execute(
            """UPDATE shared_workspace_invitations SET status = 'revoked', responded_at = ?
               WHERE invitee_user_id = ? AND status = 'pending'""",
            (_timestamp(), user_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Could not clean up shared workspaces for deleted account %s", user_id)
    finally:
        conn.close()


@router.get("")
async def api_shared_workspaces(request: Request):
    account = await _account(request)
    workspaces = await run_in_threadpool(_workspace_list, account["id"])
    invitations = await run_in_threadpool(_invitations_for_email, account["email"])
    return {"account_id": account["id"], "workspaces": workspaces, "invitations": invitations, "member_limit": None}


@router.post("")
async def api_create_shared_workspace(request: Request):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    result = await run_in_threadpool(_create_workspace, account, payload.get("name"))
    return result


@router.post("/projects")
async def api_create_shared_workspace_project(request: Request):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return await run_in_threadpool(_create_project, account, payload)


@router.post("/projects/{project_id}/workflow")
async def api_generate_shared_project_workflow(request: Request, project_id: str, background_tasks: BackgroundTasks):
    account = await _account(request)
    claim = await run_in_threadpool(_claim_project_workflow, account, project_id)
    if claim.get("ready"):
        return {"workspace": claim["workspace"], "project": claim["project"], "members": claim["members"]}
    background_tasks.add_task(_generate_project_workflow, account, claim["project"])
    return await run_in_threadpool(_project_snapshot, project_id, account["id"])


@router.post("/projects/{project_id}/tasks")
async def api_create_shared_project_task(request: Request, project_id: str):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return await run_in_threadpool(_create_project_task, account, project_id, payload if isinstance(payload, dict) else {})


@router.patch("/projects/{project_id}/tasks/{task_id}")
async def api_update_shared_project_task(request: Request, project_id: str, task_id: str):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return await run_in_threadpool(_update_project_task, account, project_id, task_id, payload if isinstance(payload, dict) else {})


@router.delete("/projects/{project_id}/tasks/{task_id}")
async def api_delete_shared_project_task(request: Request, project_id: str, task_id: str):
    account = await _account(request)
    return await run_in_threadpool(_delete_project_task, account, project_id, task_id)


@router.get("/invitations")
async def api_shared_workspace_invitations(request: Request):
    account = await _account(request)
    invitations = await run_in_threadpool(_invitations_for_email, account["email"])
    return {"account_id": account["id"], "invitations": invitations}


@router.get("/notifications")
async def api_shared_workspace_notifications(request: Request):
    account = await _account(request)
    notifications = await run_in_threadpool(_unread_invitation_responses, account["id"])
    return {"account_id": account["id"], "notifications": notifications}


@router.post("/notifications/ack")
async def api_ack_shared_workspace_notifications(request: Request):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return await run_in_threadpool(_ack_invitation_responses, account["id"], payload.get("ids"))


@router.post("/invitations/{invitation_id}/respond")
async def api_respond_shared_workspace_invitation(request: Request, invitation_id: str):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return await run_in_threadpool(_respond_to_invitation, account, invitation_id, payload.get("action"))


@router.get("/{workspace_id}")
async def api_shared_workspace_details(request: Request, workspace_id: str):
    account = await _account(request)
    return await run_in_threadpool(_workspace_details, workspace_id, account["id"])


@router.patch("/{workspace_id}")
async def api_rename_shared_workspace(request: Request, workspace_id: str):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return await run_in_threadpool(_rename_workspace, account, workspace_id, payload.get("name"))


@router.post("/{workspace_id}/invitations")
async def api_invite_to_shared_workspace(request: Request, workspace_id: str):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return await run_in_threadpool(_invite_member, account, workspace_id, payload.get("email"))


@router.delete("/{workspace_id}/invitations/{invitation_id}")
async def api_revoke_shared_workspace_invitation(request: Request, workspace_id: str, invitation_id: str):
    account = await _account(request)
    return await run_in_threadpool(_revoke_invitation, account, workspace_id, invitation_id)


@router.delete("/{workspace_id}/members/{member_id}")
async def api_remove_shared_workspace_member(request: Request, workspace_id: str, member_id: int):
    account = await _account(request)
    return await run_in_threadpool(_remove_member, account, workspace_id, member_id)


@router.post("/{workspace_id}/leave")
async def api_leave_shared_workspace(request: Request, workspace_id: str):
    account = await _account(request)
    return await run_in_threadpool(_leave_workspace, account, workspace_id)


@router.delete("/{workspace_id}")
async def api_delete_shared_workspace(request: Request, workspace_id: str):
    account = await _account(request)
    return await run_in_threadpool(_delete_workspace, account, workspace_id)


@router.post("/{workspace_id}/read")
async def api_mark_shared_workspace_read(request: Request, workspace_id: str):
    account = await _account(request)
    return await run_in_threadpool(_mark_workspace_read, workspace_id, account["id"])


@router.get("/{workspace_id}/messages")
async def api_shared_workspace_messages(request: Request, workspace_id: str, after_seq: int = 0, limit: int = 100):
    account = await _account(request)
    after_seq = max(0, int(after_seq or 0))
    limit = min(200, max(1, int(limit or 100)))
    messages = await run_in_threadpool(_get_messages, workspace_id, account["id"], after_seq, limit)
    return {"messages": messages}


@router.post("/{workspace_id}/messages")
async def api_send_shared_workspace_message(request: Request, workspace_id: str):
    account = await _account(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    body = str(payload.get("text") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Write a message before sending.")
    if len(body) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=413, detail=f"Messages are limited to {MAX_MESSAGE_LENGTH} characters.")
    match = _AI_PREFIX.match(body)
    ai_request = match.group(1).strip() if match else None
    if match and not ai_request:
        raise HTTPException(status_code=400, detail="Add a question after `@ODDI`.")
    client_id = str(payload.get("client_message_id") or "").strip()
    try:
        client_id = str(uuid.UUID(client_id))
    except (ValueError, AttributeError, TypeError):
        client_id = str(uuid.uuid4())
    message = await run_in_threadpool(_insert_user_message, account, workspace_id, body, client_id, ai_request)
    return {"message": message}
