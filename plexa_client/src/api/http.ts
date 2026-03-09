import { API_BASE_URL } from "./config"
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

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw this.mapError(response.status, body.detail)
    }

    return response.json()
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
}