export interface ApiMessage {
  message_id: string
  session_id: string
  role: "user" | "assistant" | "system" | "instructor"
  content: string
  created_at: string
  metadata?: Record<string, unknown> | null
}

export interface ApiSessionResponse {
  session_id: string
  title: string
  user_id: string
  course_id: string
  lesson_id: string
  lesson_version: string
  created_at: string
  updated_at: string
  is_active: boolean
  turn_count: number
  max_turns: number
  is_completion_started: boolean
  completed_at?: string | null
  is_finalized: boolean
  turned_in_at?: string | null
  logging_policy: string
  reflection_hooks: ApiSessionReflectionHook[]
}

export interface ApiSessionReflectionHook {
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

export interface ApiCreateSessionResponse {
  session: ApiSessionResponse
  messages: ApiMessage[]
}

export interface ApiListSessionsResponse {
  sessions: ApiSessionResponse[]
}

export interface ApiDeleteSessionResponse {
  status: string
  session_id: string
}

export interface ApiSendMessageResponse {
  assistant_message: ApiMessage
  session: ApiSessionResponse
}

export interface ApiCourse {
  course_id: string
  title: string
  description?: string
  instructor?: string
  term?: string
  owner_id: string
  discoverable: boolean
  enrolled_users: string[]
  pending_requests: string[]
  created_at: string
  lessons: Record<string, string>
}

export interface ApiCourseListResponse {
  courses: ApiCourse[]
}

export interface ApiLessonIdentity {
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

export interface ApiLessonIntent {
  learning_objective: string
  behavioral_focus: string
  discipline?: string[] | null
  difficulty?: string | null
  prerequisites?: string[] | null
  approximate_time?: string | null
}

export interface ApiLessonDocument {
  identity: ApiLessonIdentity
  intent: ApiLessonIntent
}

export interface ApiLessonCapabilities {
  tools_enabled?: boolean | null
  browsing_enabled?: boolean | null
}

export interface ApiLessonExecution {
  system_prompt: string
  initial_assistant_message?: string | null
  profile: string
  parameters?: Record<string, unknown> | null
  capabilities?: ApiLessonCapabilities | null
}

export interface ApiLessonConstraints {
  input_mode: string
  turn_limit?: number | null
  allowed_actions?: string[] | null
  termination_condition?: string | null
}

export interface ApiLessonReflection {
  hooks: ApiLessonReflectionHook[]
  logging_policy?: string | null
}

export interface ApiLessonReflectionHook {
  hook_id: string
  prompt: string
  phase: "mid" | "post"
  order_index: number
  trigger_turn?: number | null
  carry_to_post: boolean
}

export interface ApiLessonFullDocument {
  schema_version: string
  identity: ApiLessonIdentity
  intent: ApiLessonIntent
  execution: ApiLessonExecution
  constraints: ApiLessonConstraints
  reflection: ApiLessonReflection
}

export interface ApiCourseLessonsResponse {
  lessons: ApiLessonDocument[]
  pinned_lesson_id?: string | null
  pinned_lesson_version?: string | null
}

export interface ApiStatusResponse {
  status: string
}

export interface ApiCourseInstructorsResponse {
  owner_id: string
  instructor_ids: string[]
}

export interface ApiEncryptedLogMetadata {
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

export interface ApiEncryptedLogListResponse {
  logs: ApiEncryptedLogMetadata[]
}

export interface ApiCourseRequestsResponse {
  pending_requests: string[]
}

export interface ApiUploadLessonResponse {
  status: string
  lesson_id: string
  version: string
  overwritten: boolean
}
