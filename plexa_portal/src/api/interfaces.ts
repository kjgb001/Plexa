export interface Message {
  role: "user" | "assistant" | "system" | "instructor"
  content: string
}

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
  reflection_hooks: SessionReflectionHook[]
}

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
  response_text?: string | null
  first_answered_at?: string | null
  last_updated_at?: string | null
}

export interface Course {
  course_id: string
  title: string
  description?: string
  owner_id?: string
  discoverable: boolean
  lessons: Record<string, string>
  lesson_timeline: CourseLessonWindow[]
  enrolled_users: string[]
  pending_requests?: string[]
}

export interface CourseLessonWindow {
  lesson_id: string
  lesson_version: string
  starts_at: string
  ends_at?: string | null
}

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

export interface LessonIntent {
  learning_objective: string
  behavioral_focus: string
  discipline?: string[] | null
  difficulty?: string | null
  prerequisites?: string[] | null
  approximate_time?: string | null
}

export interface LessonCapabilities {
  tools_enabled?: boolean
  browsing_enabled?: boolean
}

export interface LessonExecution {
  system_prompt: string
  initial_assistant_message?: string | null
  profile: string
  parameters?: Record<string, unknown> | null
  capabilities?: LessonCapabilities | null
}

export interface LessonConstraints {
  input_mode: string
  turn_limit?: number | null
  allowed_actions?: string[] | null
  termination_condition?: string | null
}

export interface LessonReflection {
  hooks: LessonReflectionHook[]
  logging_policy?: string | null
}

export interface LessonReflectionHook {
  hook_id: string
  prompt: string
  phase: "mid" | "post"
  order_index: number
  trigger_turn?: number | null
  carry_to_post: boolean
}

export interface LessonDocument {
  schema_version: string
  identity: LessonIdentity
  intent: LessonIntent
  execution: LessonExecution
  constraints: LessonConstraints
  reflection: LessonReflection
}

export interface CreateSessionResult {
  session: Session
  messages: Message[]
}

export interface ListSessionsResult {
  sessions: Session[]
}

export interface DeleteSessionResult {
  status: string
  sessionId: string
}

export interface SendMessageResult {
  assistantMessage: Message
  session: Session
}

export interface UpdateSessionResult {
  session: Session
}

export interface CourseInstructors {
  owner_id: string
  instructor_ids: string[]
}

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
  turn_count: number
  is_active: boolean
  log_version: number
  artifact_sha256: string
  last_event_type: string
  last_event_at: string
  key_id: string
}

export interface CourseRequestsResult {
  pending_requests: string[]
}

export interface EncryptedLogPayload {
  [key: string]: unknown
}

export interface UploadLessonResult {
  status: string
  lesson_id: string
  version: string
  overwritten: boolean
}
