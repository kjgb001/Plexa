export class ApiError extends Error {
  status: number
  detail?: string
  payload?: unknown

  constructor(status: number, detail?: string, payload?: unknown) {
    super(detail ?? "API Error")
    this.status = status
    this.detail = detail
    this.payload = payload
  }
}

export class NotFoundError extends ApiError {}
export class UnauthorizedError extends ApiError {}
export class ConflictError extends ApiError {}
