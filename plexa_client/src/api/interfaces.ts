export interface Message {
  role: "user" | "assistant" | "system" | "instructor"
  content: string
}

export interface Session {
  session_id: string
  user_id: string
  course_id: string
  lesson_id: string
  lesson_version: string
  created_at: string
  turn_count: number
  max_turns: number
  is_active: boolean
}

export interface Course {
  course_id: string
  title: string
  description?: string
  discoverable: boolean
  lessons: Record<string, string>
  enrolled_users: string[]
}

export interface Lesson {
  lesson_id: string
  version: string
  title: string
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

export interface SendMessageResult {
  assistantMessage: Message
  session: Session
}
