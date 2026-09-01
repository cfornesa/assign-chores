# Shared Household Chores — MVP Implementation Plan

## 1. Product goal

Build a lightweight web application for any shared household—roommates, couples, families, or other co-living groups—to answer three questions:

1. What chores need to be done?
2. Who is responsible for each chore?
3. What has been completed this week?

The MVP is intentionally limited to four features:

1. Household creation and approved access
2. Shared Kanban chore board
3. Chore assignment and completion
4. One-time and weekly chore scheduling

All functionality in this plan must directly support one of those four features. Do not add notifications, fairness scoring, rewards, chat, analytics, calendar integrations, or complex recurrence.

---

## 2. Scope and non-goals

### In scope

- Authenticated users create and join private households.
- Household owners approve membership requests made through a shareable invite link.
- Approved members collaborate on chores in a Kanban board.
- Approved members can create, edit, delete, claim, assign, accept, decline, unclaim, reassign, and complete chores.
- Chores may be one-time or weekly recurring.
- Weekly chore instances are available every Sunday and use a user-selected due weekday.
- The application highlights incomplete overdue chores.
- The application displays completed chores for the current Sunday–Saturday week.

### Explicit non-goals

Do not implement any of the following in the MVP:

- Email, push, SMS, or in-app notifications and reminders.
- Automatic rotation, workload balancing, fairness calculations, or assignment suggestions.
- Points, rewards, penalties, streaks, badges, or leaderboards.
- Monthly, biweekly, custom, conditional, or seasonal recurrence.
- Calendar views, calendar sync, or external calendar integrations.
- Comments, direct messages, @mentions, attachments, photos, proof of completion, or audit-log UI.
- Chore categories, rooms, tags, labels, subtasks, checklists, or preset chore libraries.
- Completion approval, disputes, undo/reopen, or deletion recovery.
- Detailed member roles or permissions beyond household owner and approved member.
- Invite expiration, invite revocation, invite-link rotation, email invitations, or household settings pages.
- Long-term history UI, reports, charts, exports, analytics, or member performance views.
- Native applications, offline mode, or multi-household management UI.

---

## 3. Feature 1 — Household creation and approved access

### Objective

Create a private household workspace in which only approved members can view and manage household chores.

### Roles

| Role | Capabilities |
|---|---|
| Household owner | Creates the household, receives the shareable invite link, approves or rejects membership requests, and has all approved-member capabilities |
| Approved member | Can view the board and fully manage chores as described in this plan |
| Pending requester | Can submit a request to join but cannot view household information or chores |

### Required flows

#### Create a household

1. A signed-in user enters a household name.
2. Create a household record.
3. Create an approved membership record for the creator.
4. Mark the creator as the household owner.
5. Generate one reusable, high-entropy invite token and present its shareable link.

#### Request to join

1. A user opens the household invite link.
2. If necessary, they authenticate first.
3. The user submits a request to join the household.
4. Create a membership record with status `pending`.
5. Do not expose household board content or member data to the requester.

#### Approve or reject a request

1. The owner opens a small pending-requests view or panel.
2. The owner approves or rejects an individual request.
3. Approval changes membership status to `approved` and records the approver and timestamp.
4. Rejection changes membership status to `rejected`.
5. An approved user can then open the board; a rejected or pending user cannot.

### Authorization rules

- Require authentication for all household and board routes.
- Enforce household membership checks on the server and database layer, not only in the UI.
- Only the household owner can approve or reject a membership request.
- Only approved household members can read or mutate chores in that household.
- A user must not request membership twice for the same household while an existing request is pending or approved.

### Done criteria

- A user can create a household and retrieve a working invite link.
- A second user can request access through that link.
- The owner can approve the request.
- The approved user can access the household board.
- A pending or rejected requester cannot access household chores.

---

## 4. Feature 2 — Shared Kanban chore board

### Objective

Give each household a clear, shared visual board that communicates what work is available, who currently owns it, what is overdue, and what was completed during the current week.

### Board structure

Render four Kanban lanes as filtered views of the same chore-instance data. Do not create duplicate chore records for each lane.

| Lane | Inclusion rule | Purpose |
|---|---|---|
| Open | Incomplete chores with assignment status `unassigned` or `pending` | Shows work without an accepted owner |
| Mine | Incomplete chores with assignment status `accepted` and `assigned_to_user_id` equal to the signed-in user | Shows the signed-in member’s accepted responsibilities |
| Overdue | Incomplete chores with a non-null due timestamp that has passed | Warns about late work; it is derived, not a separate status |
| Completed | Chores completed during the current Sunday–Saturday week | Shows work done this week only |

A chore may appear in multiple lanes. For example, an incomplete chore accepted by the signed-in user that is past due appears in both Mine and Overdue.

### Card requirements

Every active chore card must display:

- Title.
- Optional description when present.
- Deadline representation: one-time date or weekly due weekday.
- Assignment state:
  - `Unassigned`
  - `Pending: [member name]`
  - `Accepted: [member name]`
- Visible overdue treatment when the chore is overdue.
- Relevant actions based on state and permissions.

Completed cards must additionally display:

- `Completed by [member name]`.
- Completion timestamp.

### Board interactions

Support explicit buttons or menus before implementing drag-and-drop. Once the underlying mutations are reliable, add drag-and-drop as a convenience layer.

Required interactions:

- Drag an unassigned Open card to Mine to claim it for the signed-in user.
- Drag the signed-in user’s accepted Mine card to Open to unclaim it.
- Drag an incomplete card to Completed to complete it.
- Require a confirmation before completion if the chore is accepted by another member or is awaiting someone else’s acceptance.
- Do not allow drops into Overdue; that lane is derived automatically.

### Chore creation and editing

Every approved member may:

- Create a chore.
- Edit a chore.
- Delete a chore.

Use a modal or compact form with only fields needed by Feature 4:

- Title: required.
- Description: optional.
- Schedule type: one-time or weekly.
- One-time due date: optional.
- Weekly due weekday: required for weekly chores.

### Done criteria

- The board renders Open, Mine, Overdue, and Completed lanes.
- Lane membership is computed from a single source of chore-instance truth.
- Cards visibly communicate deadline, assignment state, and overdue state.
- All approved members can create, edit, and delete chores.
- The Completed lane only shows completions from the current Sunday–Saturday week.

---

## 5. Feature 3 — Chore assignment and completion

### Objective

Allow household members to coordinate responsibility without silently assigning work to someone, while preserving who actually completed each chore.

### Assignment state model

Use the following assignment states for incomplete chore instances:

| Assignment state | Meaning | Primary board location |
|---|---|---|
| `unassigned` | No member has been proposed or accepted as owner | Open |
| `pending` | A member has been proposed as assignee but has not accepted | Open |
| `accepted` | A member accepted responsibility | Assignee’s Mine |

Completion is stored separately as the chore-instance status, not as an assignment state.

### Self-claim

Any approved member can claim an unassigned chore for themselves.

- Set `assignment_status` to `accepted`.
- Set `assigned_to_user_id` to the current user.
- Record `assigned_by_user_id` as the current user.
- Record `assigned_at` and `accepted_at`.
- Move the card out of Open and into that member’s Mine view.
- Allow unlimited active claims per member.

### Assign another member

Any approved member can propose an unassigned chore to any other approved member.

1. Select `Assign to…` on an unassigned chore.
2. Select one approved household member.
3. Set `assignment_status` to `pending`.
4. Set `assigned_to_user_id` to the proposed member.
5. Set `assigned_by_user_id` to the assigning member.
6. Record `assigned_at`.
7. Keep the card in Open and label it `Pending: [member name]`.

A pending assignment is not active ownership.

### Accept and decline

Only the proposed assignee may respond to their pending assignment.

On acceptance:

- Change `assignment_status` from `pending` to `accepted`.
- Record `accepted_at`.
- The chore leaves Open and appears in the assignee’s Mine view.

On decline:

- Change `assignment_status` to `unassigned`.
- Clear the assignment fields needed to represent an active or pending assignee.
- Return the chore to Open as `Unassigned`.
- Do not add decline explanations, conversations, escalation, or negotiation.

### Unclaim

Only the currently accepted assignee can unclaim their own chore.

- Change `assignment_status` to `unassigned`.
- Clear active assignment fields.
- Return the chore to Open.

### Reassign

Any approved member can reassign an accepted chore to another approved member, but never silently.

1. Show a confirmation describing the current assignee and proposed new assignee.
2. On confirmation, set the proposed new assignee.
3. Set `assignment_status` to `pending`.
4. Keep the chore in Open with `Pending: [new member name]`.
5. Require the new assignee to accept before the chore becomes actively owned.

### Complete

Any approved member may mark any incomplete chore as complete, including chores that are:

- Unassigned.
- Pending acceptance.
- Accepted by themselves.
- Accepted by another member.
- Overdue.

On completion:

- Set chore `status` to `completed`.
- Set `completed_by_user_id` to the current user.
- Set `completed_at` to the current timestamp.
- Remove the card from Open, Mine, and Overdue.
- Display it in Completed through the end of the current week.

Keep assignee information intact where applicable. The assignee and completer are distinct facts.

### Done criteria

- Members can self-claim unassigned chores.
- Members can propose an assignment to another approved member.
- Proposed assignees must accept before a chore is actively assigned.
- Declining or unclaiming returns a chore to Open as unassigned.
- Reassignment asks for confirmation and requires new acceptance.
- Any approved member can complete any incomplete chore.
- Completion records both the actual completing member and timestamp.

---

## 6. Feature 4 — One-time and weekly scheduling

### Objective

Support straightforward deadlines and weekly recurring work using a fixed Sunday–Saturday household week.

### Scheduling types

Implement exactly two types.

| Type | Required fields | Instance behavior |
|---|---|---|
| One-time | Title; due date is optional | One active chore instance persists until completed or deleted |
| Weekly | Title; due weekday is required | One chore instance is generated each Sunday for the new household week |

### One-time chores

A one-time chore includes:

- Required title.
- Optional description.
- Optional due date.

Rules:

- If due date is null, the chore never becomes overdue.
- If a due date exists and the chore remains incomplete after its due point, display it as overdue.
- Once completed, display it only in the current week’s Completed lane.

### Weekly recurring chores

A weekly recurring chore is a durable template that includes:

- Required title.
- Optional description.
- Schedule type `weekly`.
- Required due weekday: Sunday through Saturday.

Rules:

1. The household week starts Sunday and ends Saturday.
2. At the start of each Sunday, create one chore instance for every active weekly template.
3. New weekly instances begin `unassigned`.
4. Calculate each instance’s due timestamp using the selected weekday in its Sunday–Saturday week.
5. An incomplete instance becomes overdue after that due timestamp.
6. Completing an instance does not create another instance immediately.
7. The next instance becomes available the following Sunday.

### Week and timezone policy

- Fix the week boundary to Sunday; do not build a configurable week-start setting.
- Use a consistent application timezone for all weekly generation and overdue calculations.
- If a household timezone is stored, set it once during household creation or default it from the creator; do not build timezone-management UI in this MVP.
- Document the chosen timezone behavior in the implementation README.

### Template and instance architecture

Use recurring templates plus individual chore instances.

A template stores the repeating rule. An instance stores actionable weekly work, assignment state, and completion state.

Example:

- Template: `Clean kitchen`; schedule: weekly; due weekday: Friday.
- Instance: `Clean kitchen`; week start: Sunday, August 30; due: Friday of that week; status: completed; completed by: a household member.

Create a database-level uniqueness rule so a weekly template cannot generate more than one instance per week, such as a unique constraint on `(template_id, week_start_date)`.

### Generation strategy

Use an idempotent generation operation:

- Run it when an approved member opens the household board and/or through a scheduled server job if available.
- Determine the current Sunday week-start date in the application timezone.
- Create missing instances for the current week only.
- Use the uniqueness constraint or upsert logic to prevent duplicates when multiple members open the board concurrently.

Do not backfill past weeks or generate future weeks in the MVP.

### Done criteria

- A member can create a one-time chore with or without a due date.
- A member can create a weekly chore only after choosing a due weekday.
- A new instance of each weekly template exists once per Sunday–Saturday week.
- New weekly instances are unassigned at the beginning of the week.
- Completing a weekly chore does not create another instance before the next Sunday.
- Incomplete dated chores are shown as overdue.
- Completed data persists, even though the UI displays only the current week’s completions.

---

## 7. Minimal data model

Use names appropriate for the chosen stack, but preserve these conceptual entities and constraints.

### Users

- `id`
- `name`
- `email`
- `created_at`

### Households

- `id`
- `name`
- `owner_user_id`
- `invite_token`
- `timezone` or an application-level timezone policy
- `created_at`

### Household memberships

- `id`
- `household_id`
- `user_id`
- `status`: `pending`, `approved`, `rejected`
- `requested_at`
- `approved_at` nullable
- `approved_by_user_id` nullable

Constraints:

- Unique membership relationship for `(household_id, user_id)`.
- Only the household owner may transition a request to approved or rejected.

### Chore templates

Use for weekly chores and optionally for a consistent one-time creation pipeline.

- `id`
- `household_id`
- `title`
- `description` nullable
- `schedule_type`: `one_time`, `weekly`
- `weekly_due_weekday` nullable
- `one_time_due_at` nullable
- `created_by_user_id`
- `created_at`
- `updated_at`

### Chore instances

- `id`
- `household_id`
- `template_id` nullable
- `week_start_date` nullable
- `title_snapshot`
- `description_snapshot` nullable
- `due_at` nullable
- `status`: `open`, `completed`
- `assignment_status`: `unassigned`, `pending`, `accepted`
- `assigned_to_user_id` nullable
- `assigned_by_user_id` nullable
- `assigned_at` nullable
- `accepted_at` nullable
- `completed_by_user_id` nullable
- `completed_at` nullable
- `created_at`
- `updated_at`

Constraints:

- For weekly templates, unique `(template_id, week_start_date)`.
- Instance household ID must match its template household ID where a template exists.
- Only approved members of the associated household may access an instance.

---

## 8. Implementation order

Build in this sequence to protect scope and validate the core workflow early.

1. Add authentication and user identity.
2. Build household creation, owner membership, invite link, join request, and approval flow.
3. Implement household-level authorization and test that unapproved users cannot read chore data.
4. Create the data model for chore templates and chore instances.
5. Implement one-time chore creation, edit, deletion, and a basic Open board list.
6. Add assignment state transitions: self-claim, assign, accept, decline, unclaim, and reassignment confirmation.
7. Add completion recording and the current-week Completed lane.
8. Add due-date calculation and the derived Overdue lane.
9. Add weekly templates, Sunday instance generation, and duplicate-prevention constraints.
10. Convert the working board actions into drag-and-drop interactions while retaining accessible button/menu alternatives.
11. Add focused tests for permissions, assignment transitions, week boundaries, overdue calculation, and duplicate weekly-instance prevention.

---

## 9. Definition of done

The MVP is ready for a small household to test when all of the following are true:

- A household owner can create a private household and approve a new member through an invite link.
- Approved members can create both one-time and weekly chores.
- The board makes unassigned, pending, accepted, overdue, and completed work understandable without explanation.
- Members can claim work, assign it to another member, accept or decline an assignment, unclaim work, and safely reassign work.
- Any approved member can complete any incomplete chore, with the actual completer and timestamp retained.
- Weekly chores create one new unassigned instance on Sunday and never duplicate within the same week.
- The board shows only the current week’s completed chores while preserving historical completion records in storage.
- No functionality outside the four defined features is required for launch.
