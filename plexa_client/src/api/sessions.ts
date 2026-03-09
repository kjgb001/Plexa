import { HttpClient } from "./http"
import type { Session, Message } from "./types"

export class SessionApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  createSession(courseId: string, lessonId: string, lessonVersion: string) {
    return this.http.request<{ session: Session }>("/sessions", {
      method: "POST",
      body: JSON.stringify({
        course_id: courseId,
        lesson_id: lessonId,
        lesson_version: lessonVersion
      })
    })
  }

  sendMessage(sessionId: string, content: string) {
    return this.http.request<{ assistant_message: Message; session: Session }>(
      `/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content })
      }
    )
  }
}