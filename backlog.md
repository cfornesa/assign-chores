# Assign Chores — Django MVP Backlog

This backlog is derived from [_docs/plan.md](_docs/plan.md). Items are ordered
by dependency and intentionally stop at the four planned MVP features:
household access, the shared Kanban board, chore assignment/completion, and
one-time or weekly scheduling.

## Backlog

### 1. Add user authentication and identity

**Priority:** P0  
**Depends on:** None

Set up the signed-in user flow using Django’s authentication foundation. Make
the current user available to household and chore views.

**Done when**

- Users can sign in, sign out, and access their identity.
- Household and board routes require authentication.
- User name and email are available for display and assignment decisions.

**Likely Django areas:** `assign_chores/settings.py`, `assign_chores/urls.py`,
`chores/`, templates, and migrations as needed.

### 2. Let owners create households and approve invite requests

**Priority:** P0  
**Depends on:** 1

Implement private household creation, reusable high-entropy invite links,
join requests, and owner approval or rejection.

**Done when**

- An authenticated user can create a household and becomes its owner and
  approved member.
- An invite link lets another authenticated user submit one pending request.
- The owner can approve or reject pending requests.
- Pending and rejected users cannot see household details or chores.
- Duplicate pending or approved membership requests are prevented.

### 3. Add the household and chore data model with server-side authorization

**Priority:** P0  
**Depends on:** 1 and 2

Create migrations for users, households, memberships, chore templates, and
chore instances. Enforce membership and ownership rules in server-side
views/services, not only in templates.

**Done when**

- The model supports one-time and weekly templates plus actionable instances.
- Weekly instances have a uniqueness constraint for
  `(template_id, week_start_date)`.
- Only approved members can read or mutate household chore data.
- Only the household owner can approve or reject membership requests.
- Unauthorized access tests cover pending, rejected, and unrelated users.

**Likely Django areas:** `chores/models.py`, migrations, query helpers,
permissions, and tests.

### 4. Create one-time chores and show the initial Open board

**Priority:** P0  
**Depends on:** 3

Build the first usable board view and one-time chore CRUD flow. Keep the board
backed by a single chore-instance source of truth.

**Done when**

- Approved members can create, edit, and delete one-time chores.
- Title is required; description and due date are optional.
- New incomplete, unassigned chores appear in the Open lane.
- Cards show title, optional description, due-date state, and assignment state.
- Deleting a chore removes it from the board for all approved members.

### 5. Add explicit assignment state transitions

**Priority:** P0  
**Depends on:** 4

Implement self-claim, assignment proposals, acceptance, decline, unclaim, and
confirmed reassignment before adding drag-and-drop.

**Done when**

- Any approved member can claim an unassigned chore for themselves.
- A member can propose another approved member; the chore remains pending
  until accepted.
- Only the proposed assignee can accept or decline.
- Declining or unclaiming returns the chore to Open as unassigned.
- Reassignment requires confirmation and a new acceptance.
- Assignment history fields preserve who assigned, accepted, or is assigned.

### 6. Record completion and derive the full board lanes

**Priority:** P0  
**Depends on:** 5

Add completion recording and the Open, Mine, Overdue, and Completed filtered
views.

**Done when**

- Any approved member can complete any incomplete chore.
- Completion records the actual completing member and timestamp separately from
  the assignee.
- Completed chores leave Open, Mine, and Overdue and appear in Completed.
- Completed shows only the current Sunday–Saturday week.
- Accepted chores appear in Mine only for their current assignee.
- Overdue is derived from an incomplete chore’s due timestamp and cannot be
  directly edited as a status.

### 7. Add weekly scheduling and idempotent Sunday generation

**Priority:** P0  
**Depends on:** 4 and 6

Support weekly templates with a required Sunday-through-Saturday due weekday
and generate the current week’s instances safely.

**Done when**

- Members can create and edit weekly chores only with a due weekday selected.
- A weekly instance is created once for the current Sunday–Saturday week.
- New weekly instances start unassigned.
- Concurrent board visits cannot create duplicate instances.
- Completing a weekly instance does not create another instance before Sunday.
- The chosen application timezone is documented and used consistently for week
  boundaries and overdue calculations.
- Past weeks are not backfilled and future weeks are not generated.

### 8. Make board actions accessible and protect the MVP with focused tests

**Priority:** P1  
**Depends on:** 6 and 7

Keep explicit buttons or menus as the reliable interaction layer, then add
drag-and-drop as an enhancement and finish the core regression coverage.

**Done when**

- Dragging an unassigned chore to Mine claims it.
- Dragging the current user’s accepted chore to Open unclaims it.
- Dragging an incomplete chore to Completed completes it with confirmation when
  another member is assigned or awaiting acceptance.
- Overdue rejects drops because it is a derived lane.
- Every drag action has an equivalent keyboard- and pointer-accessible control.
- Tests cover permissions, assignment transitions, week boundaries, overdue
  calculation, completion filtering, and duplicate weekly generation.

## MVP scope guardrails

Do not add functionality outside the plan’s four features during this
backlog. In particular, defer notifications and reminders, fairness scoring,
rewards, complex recurrence, calendar integrations, chat/comments, categories,
attachments, audit-log UI, reports, analytics, multi-household UI, offline
mode, and native applications.

## MVP release checklist

The MVP is ready for a small household test when an owner can create a private
household and approve a member, approved members can create one-time and
weekly chores, all assignment and completion transitions work safely, weekly
instances do not duplicate, and the board clearly communicates Open, Mine,
Overdue, and current-week Completed work.