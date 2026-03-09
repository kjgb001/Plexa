import { HttpClient } from "./http"
import type { Course } from "./types"

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
}