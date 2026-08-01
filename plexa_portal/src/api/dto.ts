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
  transcript_available: boolean
  transcript_unavailable_reason?: string | null
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
  postponed_at?: string | null
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
  owner_id?: string
  instructor_ids?: string[]
  discoverable: boolean
  archived_at?: string | null
  enrolled_users?: string[]
  pending_requests?: string[]
  viewer_is_owner: boolean
  viewer_is_instructor: boolean
  viewer_is_enrolled: boolean
  viewer_has_pending_request: boolean
  revision?: number
  created_at: string
  lessons: Record<string, string>
  lesson_timeline: ApiCourseLessonWindow[]
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

export interface ApiLessonArtifactResponse {
  lesson: ApiLessonFullDocument
  artifact_revision: number
}

export interface ApiCourseLessonsResponse {
  lessons: ApiLessonDocument[]
  lesson_timeline: ApiCourseLessonWindow[]
  pinned_lesson_id?: string | null
  pinned_lesson_version?: string | null
}

export interface ApiCourseLessonWindow {
  lesson_id: string
  lesson_version: string
  starts_at: string
  ends_at?: string | null
}

export interface ApiCourseLessonTimelineResponse {
  lesson_timeline: ApiCourseLessonWindow[]
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
  artifact_revision: number
}
