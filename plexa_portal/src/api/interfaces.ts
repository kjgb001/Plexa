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
}

export interface Course {
  course_id: string
  title: string
  description?: string
  owner_id?: string
  discoverable: boolean
  lessons: Record<string, string>
  enrolled_users: string[]
  pending_requests?: string[]
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
