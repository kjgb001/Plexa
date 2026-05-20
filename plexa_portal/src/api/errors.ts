export class ApiError extends Error {
  status: number
  detail?: string

  constructor(status: number, detail?: string) {
    super(detail ?? "API Error")
    this.status = status
    this.detail = detail
  }
}

export class NotFoundError extends ApiError {}
export class UnauthorizedError extends ApiError {}
export class ConflictError extends ApiError {}