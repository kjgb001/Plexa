import { HttpClient } from "./http"
import type {
  ApiLessonFullDocument,
  ApiStatusResponse,
  ApiUploadLessonResponse,
} from "./dto"
import type {
  LessonDocument,
  UploadLessonResult,
} from "./interfaces"
import { mapLessonDocument, mapUploadLessonResult } from "./mappers"

export class AdminApi {
  private http: HttpClient

  constructor(http: HttpClient) {
    this.http = http
  }

  async getLesson(lessonId: string, version: string): Promise<LessonDocument> {
    const result = await this.http.request<ApiLessonFullDocument>(
      `/admin/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(version)}`,
    )
    return mapLessonDocument(result)
  }

  async uploadLesson(payload: LessonDocument): Promise<UploadLessonResult> {
    const result = await this.http.request<ApiUploadLessonResponse>("/admin/lessons", {
      method: "POST",
      body: JSON.stringify(payload),
    })
    return mapUploadLessonResult(result)
  }

  async bindLessonToCourse(courseId: string, lessonId: string, version: string): Promise<{ status: string }> {
    return this.http.request<ApiStatusResponse>(`/admin/courses/${encodeURIComponent(courseId)}/lessons`, {
      method: "POST",
      body: JSON.stringify({
        lesson_id: lessonId,
        version,
      }),
    })
  }
}
