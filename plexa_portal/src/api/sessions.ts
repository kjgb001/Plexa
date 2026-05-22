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
  UpdateSessionResult,
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

  async beginCompletion(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
  ): Promise<UpdateSessionResult> {
    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/complete`,
      { method: "POST" },
    )
    return { session: mapSession(result) }
  }

  async resumeAfterCompletion(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
  ): Promise<UpdateSessionResult> {
    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/resume`,
      { method: "POST" },
    )
    return { session: mapSession(result) }
  }

  async saveReflectionResponse(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
    hookId: string,
    responseText: string,
  ): Promise<UpdateSessionResult> {
    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/reflections/${hookId}`,
      {
        method: "POST",
        body: JSON.stringify({ response_text: responseText }),
      },
    )
    return { session: mapSession(result) }
  }

  async turnInSession(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
  ): Promise<UpdateSessionResult> {
    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/turn-in`,
      { method: "POST" },
    )
    return { session: mapSession(result) }
  }
}
