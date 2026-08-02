/** HTTP error with the response status and decoded server payload. */
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

/** API response indicating that the requested resource is not visible. */
export class NotFoundError extends ApiError {}
/** API response indicating that the request has no valid identity. */
export class UnauthorizedError extends ApiError {}
/** API response indicating that the requested state transition conflicts. */
export class ConflictError extends ApiError {}
