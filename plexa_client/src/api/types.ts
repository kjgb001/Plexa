export type Message = {
  role: "user" | "assistant" | "system"
  content: string
}

export type Session = {
  session_id: string
  lesson_id: string
  lesson_version: string
  course_id: string
  messages: Message[]
  turn_count: number
  is_active: boolean
}

export type Course = {
  course_id: string
  title: string
  description?: string
  discoverable: boolean
  lessons: Record<string, string>
  enrolled_users: string[]
}