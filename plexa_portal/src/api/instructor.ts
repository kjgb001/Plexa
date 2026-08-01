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

export class InstructorApi {
  private http: HttpClient

  constructor(http: HttpClient) {
    this.http = http
  }

  async listCourses(): Promise<Course[]> {
    const result = await this.http.request<ApiCourseListResponse>(
      "/courses?include_archived=true",
    )
    return result.courses.map(mapCourse)
  }

  async getCourse(courseId: string): Promise<Course> {
    const result = await this.http.request<ApiCourse>(`/courses/${courseId}`)
    return mapCourse(result)
  }

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

  async getLessonTimeline(courseId: string): Promise<CourseLessonWindow[]> {
    const result = await this.http.request<ApiCourseLessonTimelineResponse>(`/courses/${courseId}/lesson-timeline`)
    return mapCourseLessonTimeline(result)
  }

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

  async listInstructors(courseId: string): Promise<CourseInstructors> {
    const result = await this.http.request<ApiCourseInstructorsResponse>(`/courses/${courseId}/instructors`)
    return mapCourseInstructors(result)
  }

  async addInstructor(courseId: string, userId: string): Promise<CourseInstructors> {
    const result = await this.http.request<ApiCourseInstructorsResponse>(`/courses/${courseId}/instructors`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    })
    return mapCourseInstructors(result)
  }

  async removeInstructor(courseId: string, userId: string): Promise<CourseInstructors> {
    const result = await this.http.request<ApiCourseInstructorsResponse>(`/courses/${courseId}/instructors/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    })
    return mapCourseInstructors(result)
  }

  async listRequests(courseId: string): Promise<CourseRequestsResult> {
    const result = await this.http.request<ApiCourseRequestsResponse>(`/courses/${courseId}/requests`)
    return mapCourseRequests(result)
  }

  async approveRequest(courseId: string, userId: string): Promise<{ status: string }> {
    return this.http.request<ApiStatusResponse>(`/courses/${courseId}/approve`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    })
  }

  async removeStudent(courseId: string, userId: string): Promise<{ status: string }> {
    return this.http.request<ApiStatusResponse>(`/courses/${courseId}/remove`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    })
  }

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

  async getLog(courseId: string, sessionId: string): Promise<EncryptedLogPayload> {
    return this.http.request<EncryptedLogPayload>(`/courses/${courseId}/logs/${encodeURIComponent(sessionId)}`)
  }
}
