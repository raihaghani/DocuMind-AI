# DocuMind AI - Database Schema Documentation

Verified on 2026-10-29 against the local checkout at commit `9e94795386b976d4203f50f080b0a0e393bb2f3a`, installed Django 5.2.18 sources, migrations, and the existing SQLite database. The local checkout and database are authoritative; GitHub could not be fetched during this audit. No application schema or data was changed.

## 1. Database overview

Effective backend: `django.db.backends.sqlite3`. Local database: `db.sqlite3`. `config/settings.py` selects SQLite unless `DATABASE_URL` is set to a supported PostgreSQL URL. No PostgreSQL database was inspected. Effective user model: `auth.User` (Django default; no AUTH_USER_MODEL override). Effective timezone: `UTC`.

Scope: **15 tables**: six core entities, five additional concrete Django support models, three automatic many-to-many through tables, and the migration recorder. SQLite internal `sqlite_sequence` is engine bookkeeping and is excluded. `accounts` has no models; `messages` and `staticfiles` add no tables. There are five custom models, not six custom models.

The diagram uses actual table and database column names. FK columns have `_id` suffixes; the field tables also identify their Django names. PK = Primary Key, FK = Foreign Key, UK = Unique Key. Composite UK markers denote membership in a joint key, not independent uniqueness. Every relationship is non-identifying because each child has its own surrogate primary key.

Types shown are actual SQLite declarations. Custom model IDs are Django BigAutoField but SQLite represents them as INTEGER PRIMARY KEY; built-in auth/admin/content-type IDs are AutoField. FK types to custom IDs are bigint. SQLite type affinity and varchar length declarations do not provide PostgreSQL-style strict type/length enforcement.

## 2. Entity descriptions and fields

All defaults below are Python/Django defaults, not SQL DEFAULT clauses. `blank=True` permits empty input in Django validation; it does not imply SQL NULL. Only fields explicitly marked NULL are nullable. Properties such as absolute_path, is_ready, source_label and answer_preview are not columns.

### auth.User

**Table:** `auth_user`. Django built-in identity, authentication flags and account profile. No custom accounts.User exists.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `password` | CharField; `varchar(128)` | NOT NULL | Encoded password hash. |
| `last_login` | DateTimeField; `datetime` | NULL; blank=True | Last login timestamp, if any. |
| `is_superuser` | BooleanField; `bool` | NOT NULL; default=False | Global permission flag. |
| `username` | CharField; `varchar(150)` | NOT NULL; UK | Unique username. |
| `first_name` | CharField; `varchar(150)` | NOT NULL; blank=True | Optional given name, stored as non-null string. |
| `last_name` | CharField; `varchar(150)` | NOT NULL; blank=True | Optional family name, stored as non-null string. |
| `email` | CharField; `varchar(254)` | NOT NULL; blank=True | Email string; no database uniqueness constraint. |
| `is_staff` | BooleanField; `bool` | NOT NULL; default=False | Admin access flag. |
| `is_active` | BooleanField; `bool` | NOT NULL; default=True | Account active flag. |
| `date_joined` | DateTimeField; `datetime` | NOT NULL; default=now() | Account creation timestamp. |

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `sqlite_autoindex_auth_user_1` | `username` | Yes |

### workspace.Workspace

**Table:** `workspace_workspace`. Private single-owner workspace; created by the user post_save signal or lazily on access.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `owner_id` (Django `owner`) | OneToOneField; `INTEGER` | NOT NULL; UK; FK → auth_user.id; Django CASCADE | Required owning user. |
| `name` | CharField; `varchar(120)` | NOT NULL; default='My Workspace' | Display name. |
| `created_at` | DateTimeField; `datetime` | NOT NULL; blank=True; auto_now_add | Creation timestamp. |

Default ORM ordering: `['-created_at']` (ordering is not itself an index).

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `sqlite_autoindex_workspace_workspace_1` | `owner_id` | Yes |

### documents.Document

**Table:** `documents_document`. Uploaded-file metadata, private storage path, processing state and cached extraction counts.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `owner_id` (Django `owner`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Required owning user. |
| `workspace_id` (Django `workspace`) | ForeignKey; `bigint` | NOT NULL; FK → workspace_workspace.id; Django CASCADE | Containing workspace. |
| `original_filename` | CharField; `varchar(255)` | NOT NULL | Client filename, sanitized by upload service. |
| `stored_filename` | CharField; `varchar(255)` | NOT NULL | Server-generated UUID filename; not database-unique. |
| `storage_path` | CharField; `varchar(512)` | NOT NULL | Relative path under PRIVATE_STORAGE_ROOT; not database-unique. |
| `file_type` | CharField; `varchar(8)` | NOT NULL | Allowed application values: pdf, txt. |
| `file_size` | PositiveIntegerField; `integer unsigned` | NOT NULL; CHECK >= 0; default=0 | Uploaded size in bytes. |
| `uploaded_at` | DateTimeField; `datetime` | NOT NULL; blank=True; auto_now_add | Upload timestamp. |
| `status` | CharField; `varchar(16)` | NOT NULL; default=Document.Status.PROCESSING | Application processing/result state; choices listed below. |
| `char_count` | PositiveIntegerField; `integer unsigned` | NOT NULL; CHECK >= 0; default=0 | Cached extracted character count. |
| `page_count` | PositiveIntegerField; `integer unsigned` | NOT NULL; CHECK >= 0; default=0 | Cached extracted page count. |
| `chunk_count` | PositiveIntegerField; `integer unsigned` | NOT NULL; CHECK >= 0; default=0 | Cached extracted chunk count; not a database-maintained aggregate. |
| `error_message` | TextField; `TEXT` | NOT NULL; blank=True; default='' | User-facing processing failure detail. |

Application choices for `file_type`: `pdf`, `txt`. No SQL enum/check enforces these choice lists.

Application choices for `status`: `processing`, `ready`, `failed`. No SQL enum/check enforces these choice lists.

Default ORM ordering: `['-uploaded_at']` (ordering is not itself an index).

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `documents_document_workspace_id_75c69096` | `workspace_id` | No |
| `documents_document_owner_id_04d2b723` | `owner_id` | No |
| `documents_d_status_07369e_idx` | `status` | No |
| `documents_d_owner_i_8b696e_idx` | `owner_id, uploaded_at DESC` | No |

### documents.DocumentChunk

**Table:** `documents_documentchunk`. Extracted searchable text segments, with sequence and source-reference information. Owner is denormalized.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `document_id` (Django `document`) | ForeignKey; `bigint` | NOT NULL; FK → documents_document.id; Django CASCADE | Source/parent document. |
| `owner_id` (Django `owner`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Required owning user. |
| `seq` | PositiveIntegerField; `integer unsigned` | NOT NULL; CHECK >= 0 | Zero-based chunk sequence within a document. |
| `text` | TextField; `TEXT` | NOT NULL | Extracted chunk text. |
| `page_number` | PositiveIntegerField; `integer unsigned` | NULL; CHECK >= 0; blank=True | Optional PDF page number. |
| `reference` | CharField; `varchar(120)` | NOT NULL; blank=True; default='' | TXT line-range or other citation label. |

Composite unique keys: `(document_id, seq)`.

Default ORM ordering: `['document_id', 'seq']` (ordering is not itself an index).

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `documents_documentchunk_owner_id_9099842d` | `owner_id` | No |
| `documents_documentchunk_document_id_13a40b60` | `document_id` | No |
| `documents_documentchunk_document_id_seq_da9b449a_uniq` | `document_id, seq` | Yes |
| `documents_d_owner_i_a4ddd5_idx` | `owner_id` | No |
| `documents_d_documen_41ba45_idx` | `document_id, seq` | No |

### ai_assistant.AIRequest

**Table:** `ai_assistant_airequest`. Persistent question/answer interaction and citation snapshots, including failed and unsupported results.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `user_id` (Django `user`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Associated user. |
| `document_id` (Django `document`) | ForeignKey; `bigint` | NULL; FK → documents_document.id; Django SET_NULL; blank=True | Source/parent document. |
| `document_name` | CharField; `varchar(255)` | NOT NULL | Filename snapshot retained after document deletion. |
| `question` | TextField; `TEXT` | NOT NULL | Submitted question. |
| `answer` | TextField; `TEXT` | NOT NULL; blank=True; default='' | Generated answer; may be empty. |
| `status` | CharField; `varchar(16)` | NOT NULL | Application processing/result state; choices listed below. |
| `provider_mode` | CharField; `varchar(16)` | NOT NULL | Provider used: mock or openai. |
| `sources` | JSONField; `TEXT` | NOT NULL; JSON_VALID check; blank=True; default=list() | JSON citation snapshots, not foreign keys to chunks. |
| `error_detail` | CharField; `varchar(255)` | NOT NULL; blank=True; default='' | Request/provider failure detail. |
| `created_at` | DateTimeField; `datetime` | NOT NULL; blank=True; auto_now_add | Creation timestamp. |

Application choices for `status`: `success`, `unsupported`, `failed`. No SQL enum/check enforces these choice lists.

Application choices for `provider_mode`: `mock`, `openai`. No SQL enum/check enforces these choice lists.

Default ORM ordering: `['-created_at']` (ordering is not itself an index).

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `ai_assistan_status_091e23_idx` | `status` | No |
| `ai_assistan_user_id_50fadd_idx` | `user_id, created_at DESC` | No |
| `ai_assistant_airequest_user_id_bac2f56c` | `user_id` | No |
| `ai_assistant_airequest_document_id_5d44cf20` | `document_id` | No |

### ai_assistant.UsageRecord

**Table:** `ai_assistant_usagerecord`. Per-user, per-calendar-day consumed-question counter.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `user_id` (Django `user`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Associated user. |
| `date` | DateField; `date` | NOT NULL | Usage day in configured Django timezone. |
| `count` | PositiveIntegerField; `integer unsigned` | NOT NULL; CHECK >= 0; default=0 | Consumed questions for this user/day. |

Composite unique keys: `(user_id, date)`.

Named model constraints: `unique_usage_per_user_per_day`.

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `ai_assistan_user_id_c11525_idx` | `user_id, date` | No |
| `ai_assistant_usagerecord_user_id_b7312d5a` | `user_id` | No |
| `sqlite_autoindex_ai_assistant_usagerecord_1` | `user_id, date` | Yes |

### auth.Group

**Table:** `auth_group`. Built-in permission group; not a collaborative workspace or tenant membership.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `name` | CharField; `varchar(150)` | NOT NULL; UK | Display name. |

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `sqlite_autoindex_auth_group_1` | `name` | Yes |

### auth.Group_permissions

**Table:** `auth_group_permissions`. Automatic through model for Group.permissions.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `group_id` (Django `group`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_group.id; Django CASCADE | Associated permission group. |
| `permission_id` (Django `permission`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_permission.id; Django CASCADE | Associated permission. |

Composite unique keys: `(group_id, permission_id)`.

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `auth_group_permissions_permission_id_84c5c92e` | `permission_id` | No |
| `auth_group_permissions_group_id_b120cbf9` | `group_id` | No |
| `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` | `group_id, permission_id` | Yes |

### auth.Permission

**Table:** `auth_permission`. Built-in permission for a content type.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `name` | CharField; `varchar(255)` | NOT NULL | Display name. |
| `content_type_id` (Django `content_type`) | ForeignKey; `INTEGER` | NOT NULL; FK → django_content_type.id; Django CASCADE | Associated model type. |
| `codename` | CharField; `varchar(100)` | NOT NULL | Permission code within a content type. |

Composite unique keys: `(content_type_id, codename)`.

Default ORM ordering: `['content_type__app_label', 'content_type__model', 'codename']` (ordering is not itself an index).

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `auth_permission_content_type_id_2f476e4b` | `content_type_id` | No |
| `auth_permission_content_type_id_codename_01ab375a_uniq` | `content_type_id, codename` | Yes |

### auth.User_groups

**Table:** `auth_user_groups`. Automatic through model for User.groups.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `user_id` (Django `user`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Associated user. |
| `group_id` (Django `group`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_group.id; Django CASCADE | Associated permission group. |

Composite unique keys: `(user_id, group_id)`.

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `auth_user_groups_group_id_97559544` | `group_id` | No |
| `auth_user_groups_user_id_6a12ed8b` | `user_id` | No |
| `auth_user_groups_user_id_group_id_94350c0c_uniq` | `user_id, group_id` | Yes |

### auth.User_user_permissions

**Table:** `auth_user_user_permissions`. Automatic through model for User.user_permissions.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `user_id` (Django `user`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Associated user. |
| `permission_id` (Django `permission`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_permission.id; Django CASCADE | Associated permission. |

Composite unique keys: `(user_id, permission_id)`.

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `auth_user_user_permissions_permission_id_1fbb5f2c` | `permission_id` | No |
| `auth_user_user_permissions_user_id_a95ead1b` | `user_id` | No |
| `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` | `user_id, permission_id` | Yes |

### admin.LogEntry

**Table:** `django_admin_log`. Django admin audit entries; object_id is descriptive and is not a foreign key to the target object.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `action_time` | DateTimeField; `datetime` | NOT NULL; default=now() | Admin action timestamp. |
| `user_id` (Django `user`) | ForeignKey; `INTEGER` | NOT NULL; FK → auth_user.id; Django CASCADE | Associated user. |
| `content_type_id` (Django `content_type`) | ForeignKey; `INTEGER` | NULL; FK → django_content_type.id; Django SET_NULL; blank=True | Associated model type. |
| `object_id` | TextField; `TEXT` | NULL; blank=True | Text identifier of audited object; not a FK. |
| `object_repr` | CharField; `varchar(200)` | NOT NULL | Audited-object display snapshot. |
| `action_flag` | PositiveSmallIntegerField; `smallint unsigned` | NOT NULL; CHECK >= 0 | Admin action: 1 add, 2 change, 3 delete. |
| `change_message` | TextField; `TEXT` | NOT NULL; blank=True | Change description, potentially serialized JSON. |

Application choices for `action_flag`: `1`, `2`, `3`. No SQL enum/check enforces these choice lists.

Default ORM ordering: `['-action_time']` (ordering is not itself an index).

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `django_admin_log_user_id_c564eba6` | `user_id` | No |
| `django_admin_log_content_type_id_c4bce8eb` | `content_type_id` | No |

### contenttypes.ContentType

**Table:** `django_content_type`. Registry of installed model types used by permissions and admin logging.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `app_label` | CharField; `varchar(100)` | NOT NULL | Django application label. |
| `model` | CharField; `varchar(100)` | NOT NULL | Model identifier. |

Composite unique keys: `(app_label, model)`.

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `django_content_type_app_label_model_76bd3d3b_uniq` | `app_label, model` | Yes |

### migrations.Migration

**Table:** `django_migrations`. Django internal MigrationRecorder bookkeeping. Not a business entity; no foreign keys or unique app/name constraint.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField; `INTEGER` | NOT NULL; PK; blank=True | Surrogate auto-increment identifier. |
| `app` | CharField; `varchar(255)` | NOT NULL | Migration application label. |
| `name` | CharField; `varchar(255)` | NOT NULL | Display name. |
| `applied` | DateTimeField; `datetime` | NOT NULL; default=now() | Migration application timestamp. |

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| None beyond INTEGER primary-key storage | - | - |

### sessions.Session

**Table:** `django_session`. Database-backed sessions. User identity, when present, is encoded in session_data, not stored as a user foreign key.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `session_key` | CharField; `varchar(40)` | NOT NULL; PK | Session identifier. |
| `session_data` | TextField; `TEXT` | NOT NULL | Encoded session payload. |
| `expire_date` | DateTimeField; `datetime` | NOT NULL | Session expiration timestamp. |

Actual indexes (including implicit unique/FK indexes):

| Index | Columns | Unique |
|---|---|---|
| `django_session_expire_date_a5c62663` | `expire_date` | No |
| `sqlite_autoindex_django_session_1` | `session_key` | Yes |

## 3. Relationships

Cardinality reads from parent to child. Every non-null child FK requires exactly one parent; optional FKs permit zero or one parent. No FK guarantees a parent has children.

| Parent | Child column | Children per parent | Parents per child | Django deletion | Reverse name |
|---|---|---|---|---|---|
| `auth_user` | `workspace_workspace.owner_id` | 0..1 | 1 | CASCADE | `workspace` |
| `auth_user` | `documents_document.owner_id` | 0..many | 1 | CASCADE | `documents` |
| `workspace_workspace` | `documents_document.workspace_id` | 0..many | 1 | CASCADE | `documents` |
| `documents_document` | `documents_documentchunk.document_id` | 0..many | 1 | CASCADE | `chunks` |
| `auth_user` | `documents_documentchunk.owner_id` | 0..many | 1 | CASCADE | `document_chunks` |
| `auth_user` | `ai_assistant_airequest.user_id` | 0..many | 1 | CASCADE | `ai_requests` |
| `documents_document` | `ai_assistant_airequest.document_id` | 0..many | 0..1 | SET_NULL | `ai_requests` |
| `auth_user` | `ai_assistant_usagerecord.user_id` | 0..many | 1 | CASCADE | `usage_records` |
| `auth_group` | `auth_group_permissions.group_id` | 0..many | 1 | CASCADE | `Group_permissions+` |
| `auth_permission` | `auth_group_permissions.permission_id` | 0..many | 1 | CASCADE | `Group_permissions+` |
| `django_content_type` | `auth_permission.content_type_id` | 0..many | 1 | CASCADE | `Django default accessor` |
| `auth_user` | `auth_user_groups.user_id` | 0..many | 1 | CASCADE | `User_groups+` |
| `auth_group` | `auth_user_groups.group_id` | 0..many | 1 | CASCADE | `User_groups+` |
| `auth_user` | `auth_user_user_permissions.user_id` | 0..many | 1 | CASCADE | `User_user_permissions+` |
| `auth_permission` | `auth_user_user_permissions.permission_id` | 0..many | 1 | CASCADE | `User_user_permissions+` |
| `auth_user` | `django_admin_log.user_id` | 0..many | 1 | CASCADE | `Django default accessor` |
| `django_content_type` | `django_admin_log.content_type_id` | 0..many | 0..1 | SET_NULL | `Django default accessor` |

The three auth join tables implement optional many-to-many membership/permission relations. Their FK pairs are unique. There is no Workspace → AIRequest FK, User → Session FK, AIRequest → DocumentChunk FK, or UsageRecord → AIRequest FK. A workspace can be associated with requests indirectly through documents, but that path can disappear when a document is deleted.

## 4. Data integrity

- `Workspace.owner_id` is unique: a user can have at most one workspace at database level. The signup signal normally creates one, but the database does not require every user to have one.
- `DocumentChunk(document_id, seq)` is jointly unique. Sequence continuity, chunk totals, and matching chunk/document owners are not database constraints.
- `UsageRecord(user_id, date)` has named constraint `unique_usage_per_user_per_day`. `count >= 0` is checked; the configured daily upper quota is not a database check.
- User.username and Group.name are unique. User.email is not unique in the database; registration performs a case-insensitive availability query. Case-insensitive username checking is also application logic.
- Positive integer fields carry non-negative checks. AIRequest.sources is TEXT with JSON_VALID validation in SQLite; citation object shape is not checked.
- No database constraint requires Document.owner to equal Workspace.owner, DocumentChunk.owner to equal Document.owner, or AIRequest.user to equal Document.owner.
- Django CASCADE/SET_NULL labels describe the ORM deletion collector. Inspected SQLite FKs are DEFERRABLE INITIALLY DEFERRED with SQL NO ACTION on deletion/update. Raw SQL deletion does not automatically perform Django cascades or nulling; referential checks require FK enforcement on the connection. Django enables it for SQLite.
- Deleting a document through Django deletes chunks and nulls AIRequest.document_id, preserving request text and document_name. Deleting a user cascades their owned workspace, documents, chunks, requests and usage. Deleting a workspace cascades its documents, with request document links nulled; it does not directly delete user-owned request history.
- Explicit owner index on DocumentChunk duplicates its automatic FK index. Composite indexes on DocumentChunk(document_id, seq) and UsageRecord(user_id, date) overlap their unique indexes. They are represented as implemented; no index/schema changes were made.

## 5. Data isolation

Document views use login checks and queries filtered by owner=request.user. Upload obtains the current user's workspace and writes both document owner and workspace. Chunks copy that owner during processing. API questions first retrieve an owned, ready document, then retrieve its chunks with document.chunks.all(); that query does not independently filter the chunk owner. Request history is filtered by user=request.user. Uploads live under PRIVATE_STORAGE_ROOT/user_<id> and downloads are ownership-checked. These are application controls, not database row-level security. Direct ORM/SQL writes can create inconsistent ownership because cross-table ownership equality is not constrained. Auth groups are permissions infrastructure, not workspace teams.

## 6. Request history

AIRequest links each question and answer to a required user and an optional document. The normal ask flow supplies the owned document. document_name is a snapshot, and sources is JSON containing document/page/label/snippet snapshots. Neither creates an additional entity or FK. status distinguishes success, unsupported and failed. provider_mode records mock/openai. Deleting a document preserves the request with document_id=NULL; deleting its user removes the request.

## 7. Usage tracking

UsageRecord stores user, date and count, with one row per user/day. services/usage.py computes the day with timezone.localdate(), then uses transaction.atomic(), select_for_update().get_or_create() and F("count") + 1. Accepted processing consumes quota, including handled provider failures and unsupported answers. Invalid, unauthorized and quota-rejected submissions do not consume it. PostgreSQL supports row locking; SQLite does not implement SELECT FOR UPDATE, so this inspection does not establish equivalent concurrency guarantees. Usage and history are not linked by FK or committed as a single transaction; count is not a guaranteed count of AIRequest rows. The service provides refund(), but the normal ask flow does not call it.

## 8. Verification and provenance

- Read every local models.py: accounts, workspace, documents, ai_assistant. Reviewed installed Django auth, admin, contenttypes and sessions model definitions and inherited fields; automatic join models are included.
- Reviewed all three local initial migrations and all 18 contrib migrations. All 21 disk migrations are recorded as applied.
- Django migration state compared to runtime model state: no changes detected.
- Read-only SQLite inspection cross-checked all 15 table column sets, SQL types, PKs, nullability, FK targets, model unique keys and explicitly declared indexes. PRAGMA foreign_key_check returned no violations. No user/document row contents were exported.
- Database SHA-256 unchanged after inspection. No migrations were executed.
- Diagram and documentation are generated from the same verified runtime/model and SQLite metadata. Final rendering checks are recorded below.

### Source files

- `config/settings.py`, `requirements.txt`
- `accounts/models.py`, `accounts/forms.py`, `accounts/views.py`
- `workspace/models.py`, `workspace/signals.py`, `workspace/apps.py`, `workspace/migrations/0001_initial.py`
- `documents/models.py`, `documents/views.py`, `documents/services.py`, `documents/migrations/0001_initial.py`
- `ai_assistant/models.py`, `ai_assistant/views.py`, `ai_assistant/services/usage.py`, `ai_assistant/migrations/0001_initial.py`
- Installed `.venv/Lib/site-packages/django/contrib/{auth,admin,contenttypes,sessions}/` models and migrations; `django/db/migrations/recorder.py`
- `db.sqlite3`: schema and migration metadata only.

### Final artifact validation

Mermaid source parsed successfully with the installed Mermaid parser. PDF contains two landscape sheets, all 15 table names and all 84 column names; both pages were rendered with Poppler and visually inspected. PNG decoded successfully at 4367 x 4236 pixels and contains both sheets. Rendered labels, cardinality symbols, boxes and margins were reviewed. The PDF is a large-format vector diagram intended for zooming or poster printing, rather than shrinking to A4. The MMD contains the full schema in one graph; PDF/PNG split the same schema into two readable sheets and repeat the User primary key as a reference on sheet 2.
