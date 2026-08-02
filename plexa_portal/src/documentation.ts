/**
 * Public development contracts for the Plexa portal.
 *
 * This documentation-only entry point keeps generated API reference focused on
 * transport, authentication, domain data, and lesson authoring. React screens
 * and application wiring remain implementation details.
 *
 * @module portal-api
 */

export { AdminApi } from "./api/admin"
export { API_BASE_URL, TARGET_API_VERSION } from "./api/config"
export { CourseApi } from "./api/courses"
export {
  ApiError,
  ConflictError,
  NotFoundError,
  UnauthorizedError,
} from "./api/errors"
export { HttpClient } from "./api/http"
export { InstructorApi } from "./api/instructor"
export type * from "./api/interfaces"
export { MessageStreamError, SessionApi } from "./api/sessions"
export type { AuthMode, AuthService, AuthStatus, AuthUser } from "./auth/types"
export { APP_ENV, ClientConfigurationError, isProductionAppEnv } from "./config/runtime"
export {
  createDefaultLessonDraft,
  csvToList,
  duplicateLessonDraft,
  jsonToText,
  listToCsv,
  listToMultiline,
  multilineToList,
  newReflectionHook,
  renumberReflectionHooks,
  serializeLessonDraft,
  textToJsonObject,
} from "./instructor/lessonBuilder"
