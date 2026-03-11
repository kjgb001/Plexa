import { HttpClient } from "./http"
import type { Course, Lesson } from "./interfaces"

export class CourseApi {
  private http: HttpClient
  constructor(http: HttpClient) {this.http = http}

  listDiscoverable(): Promise<{ courses: Course[] }> {
    return this.http.request("/courses")
  }

  get(courseId: string): Promise<Course> {
    return this.http.request(`/courses/${courseId}`)
  }

  requestEnrollment(courseId: string) {
    return this.http.request(`/courses/${courseId}/enroll`, {
      method: "POST"
    })
  }

async listLessons(courseId: string): Promise<{ lessons: Lesson[] }> {
  const result = await this.http.request<any>(
    `courses/${courseId}/lessons`, {
      method: "GET"
    }
  )

  return {
    lessons: result.map((lesson: any) => ({
      lesson_id: lesson.identity.lesson_id,
      version: lesson.identity.version,
      title: lesson.identity.title,
      author: lesson.identity.author,
      difficulty: lesson.intent?.difficulty,
      approximate_time: lesson.intent?.approximate_time,
      tags: lesson.identity?.tags
    }))
  }
}
}