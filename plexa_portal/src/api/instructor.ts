import { HttpClient } from "./http"
import type {
  ApiCourse,
  ApiCourseListResponse,
  ApiCourseLessonTimelineResponse,
  ApiCourseInstructorsResponse,
  ApiCourseLessonsResponse,
  ApiCourseRequestsResponse,
  ApiEncryptedLogListResponse,
  ApiStatusResponse,
} from "./dto"
import type {
  Course,
  CourseLessonWindow,
  CourseInstructors,
  CourseRequestsResult,
  EncryptedLogMetadata,
  EncryptedLogPayload,
  Lesson,
} from "./interfaces"
import {
  mapCourse,
  mapCourseLessonTimeline,
  mapCourseInstructors,
  mapCourseRequests,
  mapEncryptedLogList,
  mapLessonSummary,
} from "./mappers"

/** Instructor workspace operations for courses, rosters, timelines, and logs. */
export class InstructorApi {
  private http: HttpClient

  constructor(http: HttpClient) {
    this.http = http
  }

  /** List courses the current instructor can manage, including archived courses. */
  async listCourses(): Promise<Course[]> {
    const result = await this.http.request<ApiCourseListResponse>(
      "/courses?include_archived=true",
    )
    return result.courses.map(mapCourse)
  }

  /** Load one instructor-visible course. */
  async getCourse(courseId: string): Promise<Course> {
    const result = await this.http.request<ApiCourse>(`/courses/${courseId}`)
    return mapCourse(result)
  }

  /** List bound lessons and identify the currently pinned lesson. */
  async listLessons(courseId: string): Promise<Lesson[]> {
    const result = await this.http.request<ApiCourseLessonsResponse>(`/courses/${courseId}/lessons`)
    const pinnedKey = `${result.pinned_lesson_id ?? ""}:${result.pinned_lesson_version ?? ""}`
    return result.lessons.map((lesson) => {
      const mapped = mapLessonSummary(lesson)
      return {
        ...mapped,
        is_pinned_now: `${mapped.lesson_id}:${mapped.version}` === pinnedKey,
      }
    })
  }

  /** Load scheduled lesson availability windows. */
  async getLessonTimeline(courseId: string): Promise<CourseLessonWindow[]> {
    const result = await this.http.request<ApiCourseLessonTimelineResponse>(`/courses/${courseId}/lesson-timeline`)
    return mapCourseLessonTimeline(result)
  }

  /** Replace the course lesson timeline. */
  async updateLessonTimeline(
    courseId: string,
    lessonTimeline: CourseLessonWindow[],
  ): Promise<CourseLessonWindow[]> {
    const result = await this.http.request<ApiCourseLessonTimelineResponse>(`/courses/${courseId}/lesson-timeline`, {
      method: "PUT",
      body: JSON.stringify({ lesson_timeline: lessonTimeline }),
    })
    return mapCourseLessonTimeline(result)
  }

  /** List course ownership and delegated instructors. */
  async listInstructors(courseId: string): Promise<CourseInstructors> {
    const result = await this.http.request<ApiCourseInstructorsResponse>(`/courses/${courseId}/instructors`)
    return mapCourseInstructors(result)
  }

  /** Delegate instructor access to another user. */
  async addInstructor(courseId: string, userId: string): Promise<CourseInstructors> {
    const result = await this.http.request<ApiCourseInstructorsResponse>(`/courses/${courseId}/instructors`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    })
    return mapCourseInstructors(result)
  }

  /** Revoke delegated instructor access. */
  async removeInstructor(courseId: string, userId: string): Promise<CourseInstructors> {
    const result = await this.http.request<ApiCourseInstructorsResponse>(`/courses/${courseId}/instructors/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    })
    return mapCourseInstructors(result)
  }

  /** List pending student enrollment requests. */
  async listRequests(courseId: string): Promise<CourseRequestsResult> {
    const result = await this.http.request<ApiCourseRequestsResponse>(`/courses/${courseId}/requests`)
    return mapCourseRequests(result)
  }

  /** Approve a pending enrollment request. */
  async approveRequest(courseId: string, userId: string): Promise<{ status: string }> {
    return this.http.request<ApiStatusResponse>(`/courses/${courseId}/approve`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    })
  }

  /** Remove a student and revoke access to their existing course sessions. */
  async removeStudent(courseId: string, userId: string): Promise<{ status: string }> {
    return this.http.request<ApiStatusResponse>(`/courses/${courseId}/remove`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    })
  }

  /** List encrypted session-log metadata with optional lesson and user filters. */
  async listLogs(
    courseId: string,
    filters?: {
      lessonId?: string
      lessonVersion?: string
      userId?: string
    },
  ): Promise<EncryptedLogMetadata[]> {
    const params = new URLSearchParams()
    if (filters?.lessonId) {
      params.set("lesson_id", filters.lessonId)
    }
    if (filters?.lessonVersion) {
      params.set("lesson_version", filters.lessonVersion)
    }
    if (filters?.userId) {
      params.set("user_id", filters.userId)
    }
    const suffix = params.size ? `?${params.toString()}` : ""
    const result = await this.http.request<ApiEncryptedLogListResponse>(`/courses/${courseId}/logs${suffix}`)
    return mapEncryptedLogList(result)
  }

  /** Decrypt and load one authorized session log. */
  async getLog(courseId: string, sessionId: string): Promise<EncryptedLogPayload> {
    return this.http.request<EncryptedLogPayload>(`/courses/${courseId}/logs/${encodeURIComponent(sessionId)}`)
  }
}
