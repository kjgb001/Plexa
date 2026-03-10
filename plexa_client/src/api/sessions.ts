import { HttpClient } from "./http"
import type { Session, Message } from "./types"
import { getCurrentCourse, setCurrentCourse, clearCurrentCourse } from "../state/courseState"
import { getCurrentSession, setCurrentSession, clearCurrentSession } from "../state/sessionState"
import { getCurrentLesson, setCurrentLesson, clearCurrentLesson } from "../state/lessonState"

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
      `courses/${courseId}/${lessonId}/${lessonVersion}/sessions`,
      {
        method: "POST",
      }
    )
    
    setCurrentSession(result.session.session_id)
    setCurrentLesson(lessonId, lessonVersion)

    return result
  }

  async sendMessage(sessionId: string = String(null), content: string) {
    const courseId = getCurrentCourse()
    const lessonDict = getCurrentLesson()
    const lessonId = lessonDict.lessonId
    const lessonVersion = lessonDict.lessonVersion

    if (!sessionId) {
      sessionId = getCurrentSession()
    } else {
      /*this.createSession(courseId, )*/
      null
    } /* finish once lessons are in url paths */
    

    return this.http.request<{assistant_message: Message, session: Session}>(
      `courses/${courseId}/${lessonId}/${lessonVersion}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content })
      }
    )
  }

  async closeSession() {
    const courseId = getCurrentCourse()
    const sessionId = getCurrentSession()
    const lessonDict = getCurrentLesson()
    const lessonId = lessonDict.lessonId
    const lessonVersion = lessonDict.lessonVersion

    const result = await this.http.request(
      `courses/${courseId}/${lessonId}/${lessonVersion}/sessions/${sessionId}/close`,
      { method: "POST" }
    )

    clearCurrentSession()
    clearCurrentCourse()
    clearCurrentLesson()

    return result
  }

}