import { HttpClient } from "./http"
import { ApiError } from "./errors"
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

/** Student session lifecycle, messaging, reflection, and submission operations. */
export class SessionApi {
  private http: HttpClient

  constructor(http: HttpClient) {
    this.http = http
  }

  /** List the caller's sessions for one lesson version. */
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

  /** Load one session and its available transcript. */
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

  /** Start a new session for a course-bound lesson. */
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

  /** Send a message through the non-streaming fallback endpoint. */
  async sendMessage(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
    content: string,
    messageId?: string,
  ): Promise<SendMessageResult> {
    const result = await this.http.request<ApiSendMessageResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content, message_id: messageId }),
      },
    )

    return mapSendMessageResult(result)
  }

  /**
   * Stream an assistant response over server-sent events.
   *
   * Delta callbacks are provisional. The returned result is the canonical
   * committed message and session state. A {@link MessageStreamError} states
   * whether retrying the same message ID through `sendMessage` is safe.
   */
  async streamMessage(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
    content: string,
    messageId: string,
    onDelta: (content: string) => void,
    signal?: AbortSignal,
  ): Promise<SendMessageResult> {
    let response: Response
    try {
      response = await this.http.stream(
        `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/messages/stream`,
        {
          method: "POST",
          headers: { Accept: "text/event-stream" },
          body: JSON.stringify({ content, message_id: messageId }),
          signal,
        },
      )
    } catch (error) {
      if (error instanceof ApiError) {
        const streamEndpointUnavailable = [404, 405, 501].includes(error.status)
        if (!streamEndpointUnavailable && error.status < 500) {
          throw error
        }
      }
      throw new MessageStreamError(
        error instanceof Error ? error.message : "Streaming request failed.",
        true,
      )
    }

    const contentType = response.headers.get("content-type") ?? ""
    if (!contentType.includes("text/event-stream") || response.body === null) {
      throw new MessageStreamError("Streaming response was unavailable.", true)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let eventName = "message"
    let dataLines: string[] = []
    let completedResult: SendMessageResult | null = null

    const dispatchEvent = () => {
      if (dataLines.length === 0) {
        eventName = "message"
        return
      }
      const rawData = dataLines.join("\n")
      dataLines = []
      const currentEvent = eventName
      eventName = "message"

      let payload: unknown
      try {
        payload = JSON.parse(rawData)
      } catch {
        throw new MessageStreamError("Streaming response contained invalid JSON.", true)
      }

      if (currentEvent === "delta") {
        if (
          !payload ||
          typeof payload !== "object" ||
          !("content" in payload) ||
          typeof payload.content !== "string"
        ) {
          throw new MessageStreamError("Streaming delta was malformed.", true)
        }
        onDelta(payload.content)
        return
      }

      if (currentEvent === "complete") {
        completedResult = mapSendMessageResult(payload as ApiSendMessageResponse)
        return
      }

      if (currentEvent === "error") {
        const detail = (
          payload &&
          typeof payload === "object" &&
          "detail" in payload &&
          typeof payload.detail === "string"
        ) ? payload.detail : "Message streaming failed."
        const fallbackAllowed = Boolean(
          payload &&
          typeof payload === "object" &&
          "fallback_allowed" in payload &&
          payload.fallback_allowed,
        )
        throw new MessageStreamError(detail, fallbackAllowed)
      }
    }

    const processBuffer = (flush: boolean) => {
      let newlineIndex = buffer.indexOf("\n")
      while (newlineIndex >= 0) {
        let line = buffer.slice(0, newlineIndex)
        buffer = buffer.slice(newlineIndex + 1)
        if (line.endsWith("\r")) {
          line = line.slice(0, -1)
        }
        if (line === "") {
          dispatchEvent()
        } else if (!line.startsWith(":")) {
          const separatorIndex = line.indexOf(":")
          const field = separatorIndex < 0 ? line : line.slice(0, separatorIndex)
          let value = separatorIndex < 0 ? "" : line.slice(separatorIndex + 1)
          if (value.startsWith(" ")) {
            value = value.slice(1)
          }
          if (field === "event") {
            eventName = value
          } else if (field === "data") {
            dataLines.push(value)
          }
        }
        newlineIndex = buffer.indexOf("\n")
      }

      if (flush && buffer.length > 0) {
        const finalLine = buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer
        buffer = ""
        if (finalLine.startsWith("data:")) {
          dataLines.push(finalLine.slice(5).trimStart())
        } else if (finalLine.startsWith("event:")) {
          eventName = finalLine.slice(6).trimStart()
        }
      }
      if (flush) {
        dispatchEvent()
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          buffer += decoder.decode()
          processBuffer(true)
          break
        }
        buffer += decoder.decode(value, { stream: true })
        processBuffer(false)
      }
    } catch (error) {
      if (error instanceof MessageStreamError) {
        throw error
      }
      if (error instanceof DOMException && error.name === "AbortError") {
        throw error
      }
      throw new MessageStreamError(
        error instanceof Error ? error.message : "Streaming connection was interrupted.",
        true,
      )
    } finally {
      reader.releaseLock()
    }

    if (completedResult === null) {
      throw new MessageStreamError("Streaming connection ended before completion.", true)
    }
    return completedResult
  }

  /** Close an active session and activate its post-session reflections. */
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

  /** Delete a session owned by the current user. */
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

  /** Enter completion mode before turning work in. */
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

  /** Resume conversation from an unsubmitted completion state. */
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

  /** Save one reflection response. */
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

  /** Defer an active mid-session reflection until later. */
  async postponeReflection(
    courseId: string,
    lessonId: string,
    lessonVersion: string,
    sessionId: string,
    hookId: string,
  ): Promise<UpdateSessionResult> {
    const result = await this.http.request<ApiSessionResponse>(
      `courses/${courseId}/lessons/${lessonId}/${lessonVersion}/sessions/${sessionId}/reflections/${hookId}/postpone`,
      { method: "POST" },
    )
    return { session: mapSession(result) }
  }

  /** Permanently lock and submit a completed session. */
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

/** Streaming failure that indicates whether the non-streaming retry is safe. */
export class MessageStreamError extends Error {
  fallbackAllowed: boolean

  constructor(message: string, fallbackAllowed: boolean) {
    super(message)
    this.name = "MessageStreamError"
    this.fallbackAllowed = fallbackAllowed
  }
}
