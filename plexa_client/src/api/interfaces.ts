export interface Message {
  role: "user" | "assistant" | "system"
  content: string
}

export interface Session {
  session_id: string
  lesson_id: string
  lesson_version: string
  course_id: string
  messages: Message[]
  turn_count: number
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
  difficulty?: string
  approximate_time?: string
  tags?: string[]
}