import { HttpClient } from "./http"
import type {
  ApiLessonArtifactResponse,
  ApiStatusResponse,
  ApiUploadLessonResponse,
} from "./dto"
import type {
  LessonDocument,
  LessonArtifactResult,
  UploadLessonResult,
} from "./interfaces"
import { mapLessonDocument, mapUploadLessonResult } from "./mappers"

/** Course-owner lesson authoring and binding operations. */
export class AdminApi {
  private http: HttpClient

  constructor(http: HttpClient) {
    this.http = http
  }

  /** Load an editable lesson artifact and its optimistic revision. */
  async getLesson(courseId: string, lessonId: string, version: string): Promise<LessonArtifactResult> {
    const result = await this.http.request<ApiLessonArtifactResponse>(
      `/courses/${encodeURIComponent(courseId)}/lesson-artifacts/${encodeURIComponent(lessonId)}/${encodeURIComponent(version)}`,
    )
    return {
      lesson: mapLessonDocument(result.lesson),
      artifactRevision: result.artifact_revision,
    }
  }

  /** Create or replace a lesson artifact using optimistic concurrency. */
  async uploadLesson(
    courseId: string,
    payload: LessonDocument,
    expectedRevision: number | null,
  ): Promise<UploadLessonResult> {
    const revisionQuery = expectedRevision === null
      ? ""
      : `?expected_revision=${encodeURIComponent(String(expectedRevision))}`
    const result = await this.http.request<ApiUploadLessonResponse>(`/courses/${encodeURIComponent(courseId)}/lesson-artifacts${revisionQuery}`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
    return mapUploadLessonResult(result)
  }

  /** Make an authored lesson version available in a course. */
  async bindLessonToCourse(courseId: string, lessonId: string, version: string): Promise<{ status: string }> {
    return this.http.request<ApiStatusResponse>(`/courses/${encodeURIComponent(courseId)}/lessons`, {
      method: "POST",
      body: JSON.stringify({
        lesson_id: lessonId,
        version,
      }),
    })
  }
}
