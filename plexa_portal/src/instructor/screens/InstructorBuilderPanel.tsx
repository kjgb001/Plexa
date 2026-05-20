import { useMemo, useState } from "react"
import { useApis } from "../../api"
import { ApiError } from "../../api/errors"
import type { Lesson, LessonDocument } from "../../api/interfaces"
import {
  createDefaultLessonDraft,
  csvToList,
  duplicateLessonDraft,
  jsonToText,
  listToCsv,
  listToMultiline,
  multilineToList,
  serializeLessonDraft,
  textToJsonObject,
} from "../lessonBuilder"

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.payload && typeof error.payload === "object") {
      return JSON.stringify(error.payload, null, 2)
    }
    return error.detail ?? `Request failed with status ${error.status}.`
  }

  if (error instanceof Error) {
    return error.message
  }

  return "Unknown error."
}

function buildDraftFromEditor(
  draft: LessonDocument,
  fields: {
    tagsText: string
    disciplineText: string
    prerequisitesText: string
    reflectionPromptsText: string
    allowedActionsText: string
    parametersText: string
    attachedMetadataText: string
  },
): LessonDocument {
  return {
    ...duplicateLessonDraft(draft),
    identity: {
      ...draft.identity,
      tags: csvToList(fields.tagsText),
    },
    intent: {
      ...draft.intent,
      discipline: multilineToList(fields.disciplineText),
      prerequisites: multilineToList(fields.prerequisitesText),
    },
    execution: {
      ...draft.execution,
      parameters: textToJsonObject(fields.parametersText),
    },
    constraints: {
      ...draft.constraints,
      allowed_actions: multilineToList(fields.allowedActionsText),
    },
    reflection: {
      ...draft.reflection,
      reflection_prompts: multilineToList(fields.reflectionPromptsText),
      attached_metadata: textToJsonObject(fields.attachedMetadataText),
    },
  }
}

export function InstructorBuilderPanel({
  courseId,
  lessons,
  onLessonBound,
}: {
  courseId: string
  lessons: Lesson[]
  onLessonBound(): Promise<void>
}) {
  const { adminApi } = useApis()
  const [selectedLessonKey, setSelectedLessonKey] = useState("")
  const [draft, setDraft] = useState<LessonDocument>(() => createDefaultLessonDraft(courseId))
  const [tagsText, setTagsText] = useState("")
  const [disciplineText, setDisciplineText] = useState("")
  const [prerequisitesText, setPrerequisitesText] = useState("")
  const [reflectionPromptsText, setReflectionPromptsText] = useState("")
  const [allowedActionsText, setAllowedActionsText] = useState("")
  const [parametersText, setParametersText] = useState("{\n  \"temperature\": 0.2,\n  \"top_p\": 1\n}")
  const [attachedMetadataText, setAttachedMetadataText] = useState("{}")
  const [busy, setBusy] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  function applyDocument(next: LessonDocument) {
    setDraft(duplicateLessonDraft(next))
    setTagsText(listToCsv(next.identity.tags))
    setDisciplineText(listToMultiline(next.intent.discipline))
    setPrerequisitesText(listToMultiline(next.intent.prerequisites))
    setReflectionPromptsText(listToMultiline(next.reflection.reflection_prompts))
    setAllowedActionsText(listToMultiline(next.constraints.allowed_actions))
    setParametersText(jsonToText(next.execution.parameters ?? {}))
    setAttachedMetadataText(jsonToText(next.reflection.attached_metadata ?? {}))
    setStatusMessage(null)
    setErrorMessage(null)
  }

  async function handleLoadSelectedLesson() {
    if (!selectedLessonKey) {
      return
    }

    const [lessonId, version] = selectedLessonKey.split(":")
    setBusy(true)
    setErrorMessage(null)
    setStatusMessage(null)

    try {
      const result = await adminApi.getLesson(lessonId, version)
      applyDocument(result)
      setStatusMessage(`Loaded ${lessonId}@${version} into the builder.`)
    } catch (error) {
      setErrorMessage(formatError(error))
    } finally {
      setBusy(false)
    }
  }

  function handleReset() {
    applyDocument(createDefaultLessonDraft(courseId))
    setSelectedLessonKey("")
    setStatusMessage("Reset builder to a fresh lesson template.")
  }

  function compileDraft(): { document: LessonDocument | null; error: string | null } {
    try {
      const compiled = buildDraftFromEditor(draft, {
        tagsText,
        disciplineText,
        prerequisitesText,
        reflectionPromptsText,
        allowedActionsText,
        parametersText,
        attachedMetadataText,
      })
      return { document: compiled, error: null }
    } catch (error) {
      return {
        document: null,
        error: error instanceof Error ? error.message : "Failed to compile lesson draft.",
      }
    }
  }

  async function handleSave(bindAfterSave: boolean) {
    const compiled = compileDraft()
    if (!compiled.document) {
      setErrorMessage(compiled.error)
      setStatusMessage(null)
      return
    }

    setBusy(true)
    setErrorMessage(null)
    setStatusMessage(null)

    try {
      const uploaded = await adminApi.uploadLesson(compiled.document)

      if (bindAfterSave) {
        await adminApi.bindLessonToCourse(courseId, uploaded.lesson_id, uploaded.version)
        await onLessonBound()
      }

      setStatusMessage(
        bindAfterSave
          ? `Saved and bound ${uploaded.lesson_id}@${uploaded.version} to ${courseId}.`
          : `Saved ${uploaded.lesson_id}@${uploaded.version}.`,
      )
    } catch (error) {
      setErrorMessage(formatError(error))
    } finally {
      setBusy(false)
    }
  }

  const preview = useMemo(() => compileDraft(), [
    draft,
    tagsText,
    disciplineText,
    prerequisitesText,
    reflectionPromptsText,
    allowedActionsText,
    parametersText,
    attachedMetadataText,
  ])

  return (
    <section className="portal-builder">
      <article className="portal-card">
        <header className="portal-card__header">
          <h2>Lesson builder</h2>
          <span className="section-chip">Admin-backed</span>
        </header>
        <p className="portal-note">
          This builder mirrors the actual Plexa lesson document categories used by the runtime and `plexa_author`.
        </p>

        <div className="portal-builder__toolbar">
          <select
            value={selectedLessonKey}
            onChange={(event) => setSelectedLessonKey(event.target.value)}
            disabled={busy}
          >
            <option value="">Load a bound lesson</option>
            {lessons.map((lesson) => (
              <option key={`${lesson.lesson_id}:${lesson.version}`} value={`${lesson.lesson_id}:${lesson.version}`}>
                {lesson.title} ({lesson.version})
              </option>
            ))}
          </select>
          <button className="ghost-button" onClick={() => void handleLoadSelectedLesson()} disabled={busy || !selectedLessonKey}>
            Load lesson
          </button>
          <button className="ghost-button" onClick={handleReset} disabled={busy}>
            New template
          </button>
          <button className="primary-button" onClick={() => void handleSave(false)} disabled={busy}>
            Save lesson
          </button>
          <button className="primary-button" onClick={() => void handleSave(true)} disabled={busy}>
            Save and bind
          </button>
        </div>

        {statusMessage ? <p className="portal-status portal-status--ok">{statusMessage}</p> : null}
        {errorMessage ? <pre className="portal-status portal-status--error">{errorMessage}</pre> : null}
      </article>

      <div className="portal-builder__layout">
        <div className="portal-builder__form">
          <article className="portal-card">
            <header className="portal-card__header"><h2>Identity</h2></header>
            <div className="portal-form-grid">
              <label><span>Lesson ID</span><input value={draft.identity.lesson_id} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, lesson_id: event.target.value } }))} /></label>
              <label><span>Version</span><input value={draft.identity.version} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, version: event.target.value } }))} /></label>
              <label><span>Title</span><input value={draft.identity.title} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, title: event.target.value } }))} /></label>
              <label><span>Author</span><input value={draft.identity.author} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, author: event.target.value } }))} /></label>
              <label><span>Course</span><input value={draft.identity.course ?? ""} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, course: event.target.value } }))} /></label>
              <label><span>Unit</span><input value={draft.identity.unit ?? ""} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, unit: event.target.value } }))} /></label>
              <label><span>License</span><input value={draft.identity.license} onChange={(event) => setDraft((current) => ({ ...current, identity: { ...current.identity, license: event.target.value } }))} /></label>
              <label className="portal-form-grid__span-2"><span>Tags</span><input value={tagsText} onChange={(event) => setTagsText(event.target.value)} placeholder="comma, separated, tags" /></label>
            </div>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Pedagogical intent</h2></header>
            <div className="portal-form-grid">
              <label className="portal-form-grid__span-2"><span>Learning objective</span><textarea value={draft.intent.learning_objective} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, learning_objective: event.target.value } }))} rows={4} /></label>
              <label><span>Behavioral focus</span><input value={draft.intent.behavioral_focus} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, behavioral_focus: event.target.value } }))} /></label>
              <label><span>Difficulty</span><select value={draft.intent.difficulty ?? ""} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, difficulty: event.target.value } }))}><option value="introductory">Introductory</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label>
              <label><span>Approximate time</span><input value={draft.intent.approximate_time ?? ""} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, approximate_time: event.target.value } }))} /></label>
              <label className="portal-form-grid__span-2"><span>Discipline</span><textarea value={disciplineText} onChange={(event) => setDisciplineText(event.target.value)} rows={3} placeholder="One per line" /></label>
              <label className="portal-form-grid__span-2"><span>Prerequisites</span><textarea value={prerequisitesText} onChange={(event) => setPrerequisitesText(event.target.value)} rows={3} placeholder="One per line" /></label>
            </div>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Execution</h2></header>
            <div className="portal-form-grid">
              <label><span>Profile</span><input value={draft.execution.profile} onChange={(event) => setDraft((current) => ({ ...current, execution: { ...current.execution, profile: event.target.value } }))} /></label>
              <label className="portal-form-grid__span-2"><span>System prompt</span><textarea value={draft.execution.system_prompt} onChange={(event) => setDraft((current) => ({ ...current, execution: { ...current.execution, system_prompt: event.target.value } }))} rows={8} /></label>
              <label className="portal-form-grid__span-2"><span>Initial assistant message</span><textarea value={draft.execution.initial_assistant_message ?? ""} onChange={(event) => setDraft((current) => ({ ...current, execution: { ...current.execution, initial_assistant_message: event.target.value } }))} rows={4} /></label>
              <label className="portal-form-grid__span-2"><span>Parameters JSON</span><textarea value={parametersText} onChange={(event) => setParametersText(event.target.value)} rows={6} /></label>
            </div>
            <div className="portal-check-row">
              <label><input type="checkbox" checked={draft.execution.capabilities?.tools_enabled ?? false} onChange={(event) => setDraft((current) => ({ ...current, execution: { ...current.execution, capabilities: { ...(current.execution.capabilities ?? {}), tools_enabled: event.target.checked } } }))} /> Tools enabled</label>
              <label><input type="checkbox" checked={draft.execution.capabilities?.browsing_enabled ?? false} onChange={(event) => setDraft((current) => ({ ...current, execution: { ...current.execution, capabilities: { ...(current.execution.capabilities ?? {}), browsing_enabled: event.target.checked } } }))} /> Browsing enabled</label>
            </div>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Constraints</h2></header>
            <div className="portal-form-grid">
              <label><span>Input mode</span><select value={draft.constraints.input_mode} onChange={(event) => setDraft((current) => ({ ...current, constraints: { ...current.constraints, input_mode: event.target.value } }))}><option value="free">Free</option><option value="guided">Guided</option><option value="fixed">Fixed</option></select></label>
              <label><span>Turn limit</span><input type="number" value={draft.constraints.turn_limit ?? ""} onChange={(event) => setDraft((current) => ({ ...current, constraints: { ...current.constraints, turn_limit: event.target.value ? Number(event.target.value) : null } }))} /></label>
              <label className="portal-form-grid__span-2"><span>Allowed actions</span><textarea value={allowedActionsText} onChange={(event) => setAllowedActionsText(event.target.value)} rows={3} placeholder="One per line" /></label>
              <label className="portal-form-grid__span-2"><span>Termination condition</span><textarea value={draft.constraints.termination_condition ?? ""} onChange={(event) => setDraft((current) => ({ ...current, constraints: { ...current.constraints, termination_condition: event.target.value } }))} rows={3} /></label>
            </div>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Reflection</h2></header>
            <div className="portal-form-grid">
              <label className="portal-form-grid__span-2"><span>Reflection prompts</span><textarea value={reflectionPromptsText} onChange={(event) => setReflectionPromptsText(event.target.value)} rows={4} placeholder="One per line" /></label>
              <label><span>Reflection timing</span><select value={draft.reflection.reflection_timing ?? "post"} onChange={(event) => setDraft((current) => ({ ...current, reflection: { ...current.reflection, reflection_timing: event.target.value } }))}><option value="post">Post</option><option value="mid">Mid</option><option value="mixed">Mixed</option></select></label>
              <label><span>Logging policy</span><input value={draft.reflection.logging_policy ?? ""} onChange={(event) => setDraft((current) => ({ ...current, reflection: { ...current.reflection, logging_policy: event.target.value } }))} /></label>
              <label className="portal-form-grid__span-2"><span>Attached metadata JSON</span><textarea value={attachedMetadataText} onChange={(event) => setAttachedMetadataText(event.target.value)} rows={5} /></label>
            </div>
          </article>
        </div>

        <article className="portal-card portal-builder__preview">
          <header className="portal-card__header">
            <h2>JSON preview</h2>
          </header>
          {preview.error ? (
            <pre className="portal-status portal-status--error">{preview.error}</pre>
          ) : (
            <pre className="portal-log-preview">{serializeLessonDraft(preview.document as LessonDocument)}</pre>
          )}
        </article>
      </div>
    </section>
  )
}
