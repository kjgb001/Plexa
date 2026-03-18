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
  user_id: string
  course_id: string
  lesson_id: string
  lesson_version: string
  created_at: string
  is_active: boolean
  turn_count: number
  max_turns: number
}

export interface ApiCreateSessionResponse {
  session: ApiSessionResponse
  messages: ApiMessage[]
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

export interface ApiCourseLessonsResponse {
  lessons: ApiLessonDocument[]
}

export interface ApiStatusResponse {
  status: string
}
