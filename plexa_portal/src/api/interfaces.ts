/** Chat message visible in a session transcript. */
export interface Message {
  role: "user" | "assistant" | "system" | "instructor"
  content: string
}

/** Canonical student session state returned by the server. */
export interface Session {
  session_id: string
  title: string
  user_id: string
  course_id: string
  lesson_id: string
  lesson_version: string
  created_at: string
  updated_at: string
  turn_count: number
  max_turns: number
  is_active: boolean
  is_completion_started: boolean
  completed_at?: string | null
  is_finalized: boolean
  turned_in_at?: string | null
  logging_policy: string
  transcript_available: boolean
  transcript_unavailable_reason?: string | null
  reflection_hooks: SessionReflectionHook[]
}

/** Runtime state for one configured reflection hook. */
export interface SessionReflectionHook {
  hook_id: string
  prompt: string
  phase: "mid" | "post"
  order_index: number
  trigger_turn?: number | null
  carry_to_post: boolean
  carried_to_post: boolean
  triggered_at?: string | null
  trigger_source?: "mid_turn" | "soft_complete" | "carry_to_post" | null
  postponed_at?: string | null
  response_text?: string | null
  first_answered_at?: string | null
  last_updated_at?: string | null
}

/** Course metadata and the current viewer's relationship to the course. */
export interface Course {
  course_id: string
  title: string
  description?: string
  owner_id?: string
  discoverable: boolean
  archived_at?: string | null
  lessons: Record<string, string>
  lesson_timeline: CourseLessonWindow[]
  enrolled_users: string[]
  pending_requests?: string[]
  viewer_is_owner: boolean
  viewer_is_instructor: boolean
  viewer_is_enrolled: boolean
  viewer_has_pending_request: boolean
  revision?: number
}

/** Scheduled availability window for a bound lesson version. */
export interface CourseLessonWindow {
  lesson_id: string
  lesson_version: string
  starts_at: string
  ends_at?: string | null
}

/** Lesson summary shown in course navigation. */
export interface Lesson {
  lesson_id: string
  version: string
  title: string
  is_pinned_now?: boolean
  author?: string
  learning_objective?: string
  behavioral_focus?: string
  difficulty?: string
  approximate_time?: string
  tags?: string[]
}

/** Stable lesson identity and attribution fields. */
export interface LessonIdentity {
  lesson_id: string
  version: string
  title: string
  author: string
  course?: string | null
  unit?: string | null
  license: string
  created_at?: string | null
  tags?: string[] | null
}

/** Learning goals and expected student behavior for a lesson. */
export interface LessonIntent {
  learning_objective: string
  behavioral_focus: string
  discipline?: string[] | null
  difficulty?: string | null
  prerequisites?: string[] | null
  approximate_time?: string | null
}

/** Optional model capabilities available during lesson execution. */
export interface LessonCapabilities {
  tools_enabled?: boolean
  browsing_enabled?: boolean
}

/** Model instructions and inference profile for a lesson. */
export interface LessonExecution {
  system_prompt: string
  initial_assistant_message?: string | null
  profile: string
  parameters?: Record<string, unknown> | null
  capabilities?: LessonCapabilities | null
}

/** Conversation limits and allowed interaction modes. */
export interface LessonConstraints {
  input_mode: string
  turn_limit?: number | null
  allowed_actions?: string[] | null
  termination_condition?: string | null
}

/** Reflection hooks and transcript logging policy for a lesson. */
export interface LessonReflection {
  hooks: LessonReflectionHook[]
  logging_policy?: string | null
}

/** Author-defined reflection prompt and trigger behavior. */
export interface LessonReflectionHook {
  hook_id: string
  prompt: string
  phase: "mid" | "post"
  order_index: number
  trigger_turn?: number | null
  carry_to_post: boolean
}

/** Complete versioned lesson-authoring document. */
export interface LessonDocument {
  schema_version: string
  identity: LessonIdentity
  intent: LessonIntent
  execution: LessonExecution
  constraints: LessonConstraints
  reflection: LessonReflection
}

/** Newly created or loaded session with its available transcript. */
export interface CreateSessionResult {
  session: Session
  messages: Message[]
}

/** Collection of sessions associated with one lesson version. */
export interface ListSessionsResult {
  sessions: Session[]
}

/** Confirmation that a session was deleted. */
export interface DeleteSessionResult {
  status: string
  sessionId: string
}

/** Canonical result after an assistant message is committed. */
export interface SendMessageResult {
  assistantMessage: Message
  session: Session
}

/** Updated session state after a lifecycle operation. */
export interface UpdateSessionResult {
  session: Session
}

/** Course owner and delegated instructor identities. */
export interface CourseInstructors {
  owner_id: string
  instructor_ids: string[]
}

/** Searchable metadata for an encrypted session log. */
export interface EncryptedLogMetadata {
  instance_id: string
  user_id: string
  course_id: string
  lesson_id: string
  lesson_version: string
  course_owner_id: string
  authorized_instructor_ids: string[]
  created_at: string
  updated_at: string
  closed_at: string | null
  turned_in_at?: string | null
  turn_count: number
  is_active: boolean
  log_version: number
  artifact_sha256: string
  last_event_type: string
  last_event_at: string
  key_id: string
  content_available: boolean
}

/** Pending course-enrollment requests. */
export interface CourseRequestsResult {
  pending_requests: string[]
}

/** Decrypted structured session log visible to an authorized instructor. */
export interface EncryptedLogPayload {
  [key: string]: unknown
}

/** Result of creating or replacing a lesson artifact. */
export interface UploadLessonResult {
  status: string
  lesson_id: string
  version: string
  overwritten: boolean
  artifact_revision: number
}

/** Editable lesson artifact paired with its optimistic revision. */
export interface LessonArtifactResult {
  lesson: LessonDocument
  artifactRevision: number
}
