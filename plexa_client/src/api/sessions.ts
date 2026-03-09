import { HttpClient } from "./http"
import type { Session, Message } from "./types"

export class SessionApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  COURSE_ID = String(null)

  createSession(courseId: string, lessonId: string, lessonVersion: string) {
    this.COURSE_ID = courseId
    return this.http.request<{ session: Session }>(`courses/${courseId}/sessions`, {
      method: "POST",
      body: JSON.stringify({
        lesson_id: lessonId,
        lesson_version: lessonVersion
      })
    })
  }

  sendMessage(sessionId: string, content: string) {
    return this.http.request<{ assistant_message: Message; session: Session }>(
      `courses/${this.COURSE_ID}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content })
      }
    )
  }
}