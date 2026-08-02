import { HttpClient } from "./http"
import type {
  ApiCourse,
  ApiCourseLessonsResponse,
  ApiCourseListResponse,
} from "./dto"
import type { Course, Lesson } from "./interfaces"
import { mapCourse, mapLessonSummary } from "./mappers"

/** Student-facing course and lesson discovery operations. */
export class CourseApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  /** List courses visible to the authenticated student. */
  async listDiscoverable(): Promise<{ courses: Course[] }> {
    const result = await this.http.request<ApiCourseListResponse>("/courses")

    return {
      courses: result.courses.map(mapCourse),
    }
  }

  /** Load one visible course and the caller's relationship to it. */
  async get(courseId: string): Promise<Course> {
    const result = await this.http.request<ApiCourse>(`/courses/${courseId}`)
    return mapCourse(result)
  }

  /** Request enrollment in a discoverable course. */
  requestEnrollment(courseId: string): Promise<{ status: string }> {
    return this.http.request<{ status: string }>(`/courses/${courseId}/enroll`, {
      method: "POST"
    })
  }

  /** List lessons currently available in a course. */
  async listLessons(courseId: string): Promise<{ lessons: Lesson[] }> {
    const result = await this.http.request<ApiCourseLessonsResponse>(
      `courses/${courseId}/lessons`, {
      method: "GET"
      }
    )

    const pinnedKey = `${result.pinned_lesson_id ?? ""}:${result.pinned_lesson_version ?? ""}`
    return {
      lessons: result.lessons.map((lesson) => {
        const mapped = mapLessonSummary(lesson)
        return {
          ...mapped,
          is_pinned_now: `${mapped.lesson_id}:${mapped.version}` === pinnedKey,
        }
      }),
    }
  }
}
