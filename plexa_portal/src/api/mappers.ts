import type {
  ApiCourse,
  ApiCourseInstructorsResponse,
  ApiCourseRequestsResponse,
  ApiCreateSessionResponse,
  ApiEncryptedLogListResponse,
  ApiEncryptedLogMetadata,
  ApiDeleteSessionResponse,
  ApiLessonDocument,
  ApiListSessionsResponse,
  ApiMessage,
  ApiSendMessageResponse,
  ApiSessionResponse,
} from "./dto"
import type {
  Course,
  CourseInstructors,
  CourseRequestsResult,
  CreateSessionResult,
  DeleteSessionResult,
  EncryptedLogMetadata,
  Lesson,
  ListSessionsResult,
  Message,
  SendMessageResult,
  Session,
} from "./interfaces"

export function mapMessage(message: ApiMessage): Message {
  return {
    role: message.role,
    content: message.content,
  }
}

export function mapSession(session: ApiSessionResponse): Session {
  return {
    session_id: session.session_id,
    title: session.title,
    user_id: session.user_id,
    course_id: session.course_id,
    lesson_id: session.lesson_id,
    lesson_version: session.lesson_version,
    created_at: session.created_at,
    updated_at: session.updated_at,
    turn_count: session.turn_count,
    max_turns: session.max_turns,
    is_active: session.is_active,
  }
}

export function mapCourse(course: ApiCourse): Course {
  return {
    course_id: course.course_id,
    title: course.title,
    description: course.description,
    owner_id: course.owner_id,
    discoverable: course.discoverable,
    lessons: course.lessons,
    enrolled_users: course.enrolled_users,
    pending_requests: course.pending_requests,
  }
}

export function mapLessonSummary(lesson: ApiLessonDocument): Lesson {
  return {
    lesson_id: lesson.identity.lesson_id,
    version: lesson.identity.version,
    title: lesson.identity.title,
    author: lesson.identity.author,
    learning_objective: lesson.intent.learning_objective,
    behavioral_focus: lesson.intent.behavioral_focus,
    difficulty: lesson.intent.difficulty ?? undefined,
    approximate_time: lesson.intent.approximate_time ?? undefined,
    tags: lesson.identity.tags ?? undefined,
  }
}

export function mapCreateSessionResult(
  result: ApiCreateSessionResponse,
): CreateSessionResult {
  return {
    session: mapSession(result.session),
    messages: result.messages.map(mapMessage),
  }
}

export function mapListSessionsResult(
  result: ApiListSessionsResponse,
): ListSessionsResult {
  return {
    sessions: result.sessions.map(mapSession),
  }
}

export function mapDeleteSessionResult(
  result: ApiDeleteSessionResponse,
): DeleteSessionResult {
  return {
    status: result.status,
    sessionId: result.session_id,
  }
}

export function mapSendMessageResult(
  result: ApiSendMessageResponse,
): SendMessageResult {
  return {
    assistantMessage: mapMessage(result.assistant_message),
    session: mapSession(result.session),
  }
}

export function mapCourseInstructors(
  result: ApiCourseInstructorsResponse,
): CourseInstructors {
  return {
    owner_id: result.owner_id,
    instructor_ids: result.instructor_ids,
  }
}

export function mapEncryptedLogMetadata(
  metadata: ApiEncryptedLogMetadata,
): EncryptedLogMetadata {
  return { ...metadata }
}

export function mapEncryptedLogList(
  result: ApiEncryptedLogListResponse,
): EncryptedLogMetadata[] {
  return result.logs.map(mapEncryptedLogMetadata)
}

export function mapCourseRequests(
  result: ApiCourseRequestsResponse,
): CourseRequestsResult {
  return {
    pending_requests: result.pending_requests,
  }
}
