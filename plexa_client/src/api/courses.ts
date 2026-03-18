import { HttpClient } from "./http"
import type {
  ApiCourse,
  ApiCourseLessonsResponse,
  ApiCourseListResponse,
} from "./dto"
import type { Course, Lesson } from "./interfaces"
import { mapCourse, mapLessonSummary } from "./mappers"

export class CourseApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  async listDiscoverable(): Promise<{ courses: Course[] }> {
    const result = await this.http.request<ApiCourseListResponse>("/courses")

    return {
      courses: result.courses.map(mapCourse),
    }
  }

  async get(courseId: string): Promise<Course> {
    const result = await this.http.request<ApiCourse>(`/courses/${courseId}`)
    return mapCourse(result)
  }

  requestEnrollment(courseId: string) {
    return this.http.request(`/courses/${courseId}/enroll`, {
      method: "POST"
    })
  }

  async listLessons(courseId: string): Promise<{ lessons: Lesson[] }> {
    const result = await this.http.request<ApiCourseLessonsResponse>(
      `courses/${courseId}/lessons`, {
      method: "GET"
      }
    )

    return {
      lessons: result.lessons.map(mapLessonSummary),
    }
  }
}
