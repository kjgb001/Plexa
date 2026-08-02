import { API_BASE_URL, TARGET_API_VERSION } from "./config"
import {
  ApiError,
  NotFoundError,
  UnauthorizedError,
  ConflictError
} from "./errors"

/** Authenticated JSON transport shared by the portal's domain API clients. */
export class HttpClient {
  private getAuthHeaders: () => Promise<Record<string, string>>

  constructor(getAuthHeaders: () => Promise<Record<string, string>>) {
    this.getAuthHeaders = getAuthHeaders
  }

  private async fetchResponse(path: string, options: RequestInit = {}): Promise<Response> {
    const headers = {
      "Content-Type": "application/json",
      ...(await this.getAuthHeaders()),
      ...(options.headers ?? {})
    }

    const url = `${API_BASE_URL}${this.resolvePath(path)}`
    const response = await fetch(url, {
      ...options,
      headers
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw this.mapError(response.status, body)
    }

    return response
  }

  /** Decode a successful JSON response into the requested transport type. */
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await this.fetchResponse(path, options)

    const contentType = response.headers.get("content-type")
    if (contentType?.includes("application/json")) {
      return response.json()
    }

    return undefined as T
  }

  /** Return a successful raw response for server-sent event processing. */
  async stream(path: string, options: RequestInit = {}): Promise<Response> {
    return this.fetchResponse(path, options)
  }

  private mapError(status: number, body?: unknown): Error {
    const detail = this.extractDetail(body)
    switch (status) {
      case 401:
        return new UnauthorizedError(status, detail, body)
      case 404:
        return new NotFoundError(status, detail, body)
      case 409:
        return new ConflictError(status, detail, body)
      default:
        return new ApiError(status, detail, body)
    }
  }

  private extractDetail(body: unknown): string | undefined {
    if (typeof body === "string") {
      return body
    }

    if (!body || typeof body !== "object") {
      return undefined
    }

    if ("detail" in body && typeof body.detail === "string") {
      return body.detail
    }

    if ("message" in body && typeof body.message === "string") {
      return body.message
    }

    return undefined
  }

  UNVERSIONED_ENDPOINTS = new Set([
    "/health",
    "/ready"
  ])

  private resolvePath(path: string): string {
    const normalized = path.startsWith("/") ? path : `/${path}`

    if (this.UNVERSIONED_ENDPOINTS.has(normalized)) {
      return `${normalized}`
    }

    return `/${TARGET_API_VERSION}${normalized}`
  }
}
