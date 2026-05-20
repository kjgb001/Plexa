import { API_BASE_URL, TARGET_API_VERSION } from "./config"
import {
  ApiError,
  NotFoundError,
  UnauthorizedError,
  ConflictError
} from "./errors"

export class HttpClient {
  private getAuthHeaders: () => Promise<Record<string, string>>

  constructor(getAuthHeaders: () => Promise<Record<string, string>>) {
    this.getAuthHeaders = getAuthHeaders
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
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
      throw this.mapError(response.status, body.detail)
    }

    const contentType = response.headers.get("content-type")
    if (contentType?.includes("application/json")) {
      return response.json()
    }

    return undefined as T
  }

  private mapError(status: number, detail?: string): Error {
    switch (status) {
      case 401:
        return new UnauthorizedError(status, detail)
      case 404:
        return new NotFoundError(status, detail)
      case 409:
        return new ConflictError(status, detail)
      default:
        return new ApiError(status, detail)
    }
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