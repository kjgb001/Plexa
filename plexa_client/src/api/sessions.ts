import { HttpClient } from "./http"
import type {
  ApiCreateSessionResponse,
  ApiSendMessageResponse,
  ApiSessionResponse,
} from "./dto"
import type { CreateSessionResult, SendMessageResult, Session } from "./interfaces"
import { getCurrentCourse, setCurrentCourse, clearCurrentCourse } from "../state/courseState"
import { getCurrentSession, setCurrentSession, clearCurrentSession } from "../state/sessionState"
import { getCurrentLesson, setCurrentLesson, clearCurrentLesson } from "../state/lessonState"
import { mapCreateSessionResult, mapSendMessageResult, mapSession } from "./mappers"

export class SessionApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  async createSession(
    courseId: string | null = null,
    lessonId: string,
    lessonVersion: string,
  ): Promise<CreateSessionResult> {
    if (courseId === null) {
      courseId = getCurrentCourse()
    } else {
      setCurrentCourse(courseId)
    }

    const result = await this.http.request<ApiCreateSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions`,
      {
        method: "POST",
      }
    )

    const mapped = mapCreateSessionResult(result)
    
    setCurrentSession(mapped.session.session_id)
    setCurrentLesson(lessonId, lessonVersion)

    return mapped
  }

  async sendMessage(
    content: string,
    sessionId: string | null = null,
  ): Promise<SendMessageResult> {
    const courseId = getCurrentCourse()
    const lessonDict = getCurrentLesson()
    const lessonId = lessonDict.lessonId
    const lessonVersion = lessonDict.lessonVersion

    if (sessionId === null) {
      try {
        sessionId = getCurrentSession()
      } catch {
        const createdSession = await this.createSession(courseId, lessonId, lessonVersion)
        sessionId = createdSession.session.session_id
      }
    }

    const result = await this.http.request<ApiSendMessageResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content })
      }
    )

    return mapSendMessageResult(result)
  }

  async closeSession(): Promise<Session> {
    const courseId = getCurrentCourse()
    const sessionId = getCurrentSession()
    const lessonDict = getCurrentLesson()
    const lessonId = lessonDict.lessonId
    const lessonVersion = lessonDict.lessonVersion

    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/close`,
      { method: "POST" }
    )

    clearCurrentSession()
    clearCurrentCourse()
    clearCurrentLesson()

    return mapSession(result)
  }

}
