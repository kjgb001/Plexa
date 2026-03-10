import { HttpClient } from "./http"
import type { Session, Message } from "./types"
import { getCurrentCourse, setCurrentCourse } from "../state/courseState"
import { getCurrentSession, setCurrentSession, clearSession } from "../state/sessionState"

export class SessionApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  async createSession(courseId: string = String(null), lessonId: string, lessonVersion: string) {
    if (!courseId) {
      courseId = getCurrentCourse()
    } else {
      setCurrentCourse(courseId)
    }

    const result = await this.http.request<{session: Session}>(
      `courses/${courseId}/sessions`,
      {
        method: "POST",
        body: JSON.stringify({
          lesson_id: lessonId,
          lesson_version: lessonVersion
        })
      }
    )
    
    setCurrentSession(result.session.session_id)

    return result
  }

  async sendMessage(sessionId: string = String(null), content: string) {
    const courseId = getCurrentCourse()
    if (!sessionId) {
      sessionId = getCurrentSession()
    } else {
      /*this.createSession(courseId, )*/
      null
    } /* finish once lessons are in url paths */
    

    return this.http.request<{assistant_message: Message, session: Session}>(
      `courses/${courseId}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content })
      }
    )
  }

  async closeSession() {
    const courseId = getCurrentCourse()
    const sessionId = getCurrentSession()

    const result = await this.http.request(
      `courses/${courseId}/sessions/${sessionId}/close`,
      { method: "POST" }
    )

    clearSession()

    return result
  }

}