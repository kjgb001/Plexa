import { HttpClient } from "./http"
import type {
  ApiCreateSessionResponse,
  ApiDeleteSessionResponse,
  ApiListSessionsResponse,
  ApiSendMessageResponse,
  ApiSessionResponse,
} from "./dto"
import type {
  CreateSessionResult,
  DeleteSessionResult,
  ListSessionsResult,
  SendMessageResult,
  Session,
} from "./interfaces"
import {
  mapCreateSessionResult,
  mapDeleteSessionResult,
  mapListSessionsResult,
  mapSendMessageResult,
  mapSession,
} from "./mappers"

export class SessionApi {
  private http: HttpClient

  constructor(http: HttpClient) {
    this.http = http
  }

  async listSessions(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
  ): Promise<ListSessionsResult> {
    const result = await this.http.request<ApiListSessionsResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions`,
      {
        method: "GET",
      },
    )

    return mapListSessionsResult(result)
  }

  async getSession(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
  ): Promise<CreateSessionResult> {
    const result = await this.http.request<ApiCreateSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}`,
      {
        method: "GET",
      },
    )

    return mapCreateSessionResult(result)
  }

  async createSession(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
  ): Promise<CreateSessionResult> {
    const result = await this.http.request<ApiCreateSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions`,
      {
        method: "POST",
      },
    )

    return mapCreateSessionResult(result)
  }

  async sendMessage(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
    content: string,
  ): Promise<SendMessageResult> {
    const result = await this.http.request<ApiSendMessageResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content }),
      },
    )

    return mapSendMessageResult(result)
  }

  async closeSession(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
  ): Promise<Session> {
    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/close`,
      { method: "POST" },
    )

    return mapSession(result)
  }

  async deleteSession(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
  ): Promise<DeleteSessionResult> {
    const result = await this.http.request<ApiDeleteSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/delete`,
      { method: "POST" },
    )

    return mapDeleteSessionResult(result)
  }
}
