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

const EDITABLE_PARAMETER_KEYS = new Set([
  "temperature",
  "top_p",
  "max_tokens",
  "timeout_s",
  "seed",
])

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  return Number(trimmed)
}

function buildDraftFromEditor(
  draft: LessonDocument,
  fields: {
    tagsText: string
    disciplineText: string
    prerequisitesText: string
    reflectionPromptsText: string
    allowedActionsText: string
    temperatureText: string
    topPText: string
    maxTokensText: string
    timeoutSecondsText: string
    seedText: string
    attachedMetadataText: string
  },
): LessonDocument {
  const preservedParameters = Object.fromEntries(
    Object.entries(draft.execution.parameters ?? {}).filter(([key]) => !EDITABLE_PARAMETER_KEYS.has(key)),
  )
  const temperature = parseOptionalNumber(fields.temperatureText)
  const topP = parseOptionalNumber(fields.topPText)
  const maxTokens = parseOptionalNumber(fields.maxTokensText)
  const timeoutSeconds = parseOptionalNumber(fields.timeoutSecondsText)
  const seed = parseOptionalNumber(fields.seedText)
  const parameters: Record<string, unknown> = { ...preservedParameters }

  if (temperature !== null) {
    parameters.temperature = temperature
  }
  if (topP !== null) {
    parameters.top_p = topP
  }
  if (maxTokens !== null) {
    parameters.max_tokens = maxTokens
  }
  if (timeoutSeconds !== null) {
    parameters.timeout_s = timeoutSeconds
  }
  if (seed !== null) {
    parameters.seed = seed
  }

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
      parameters: Object.keys(parameters).length > 0 ? parameters : undefined,
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
  const [temperatureText, setTemperatureText] = useState("0.2")
  const [topPText, setTopPText] = useState("1")
  const [maxTokensText, setMaxTokensText] = useState("800")
  const [timeoutSecondsText, setTimeoutSecondsText] = useState("")
  const [seedText, setSeedText] = useState("")
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
    setTemperatureText(
      next.execution.parameters?.temperature !== undefined
        ? String(next.execution.parameters.temperature)
        : "",
    )
    setTopPText(
      next.execution.parameters?.top_p !== undefined
        ? String(next.execution.parameters.top_p)
        : "",
    )
    setMaxTokensText(
      next.execution.parameters?.max_tokens !== undefined
        ? String(next.execution.parameters.max_tokens)
        : "",
    )
    setTimeoutSecondsText(
      next.execution.parameters?.timeout_s !== undefined
        ? String(next.execution.parameters.timeout_s)
        : "",
    )
    setSeedText(
      next.execution.parameters?.seed !== undefined
        ? String(next.execution.parameters.seed)
        : "",
    )
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
        temperatureText,
        topPText,
        maxTokensText,
        timeoutSecondsText,
        seedText,
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
    temperatureText,
    topPText,
    maxTokensText,
    timeoutSecondsText,
    seedText,
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
          This builder mirrors the current server-side lesson document contract while keeping the editing surface focused on instructor-facing controls rather than raw runtime internals.
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
              <label><span>Difficulty</span><select value={draft.intent.difficulty ?? "introductory"} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, difficulty: event.target.value } }))}><option value="introductory">Introductory</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label>
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
            </div>
            <details className="portal-advanced">
              <summary>Advanced options</summary>
              <div className="portal-form-grid portal-advanced__grid">
                <label><span>Temperature</span><input type="number" step="0.01" value={temperatureText} onChange={(event) => setTemperatureText(event.target.value)} /></label>
                <label><span>Top p</span><input type="number" step="0.01" value={topPText} onChange={(event) => setTopPText(event.target.value)} /></label>
                <label><span>Max tokens</span><input type="number" step="1" value={maxTokensText} onChange={(event) => setMaxTokensText(event.target.value)} /></label>
                <label><span>Timeout (seconds)</span><input type="number" step="0.1" value={timeoutSecondsText} onChange={(event) => setTimeoutSecondsText(event.target.value)} /></label>
                <label><span>Seed</span><input type="number" step="1" value={seedText} onChange={(event) => setSeedText(event.target.value)} /></label>
              </div>
            </details>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Constraints</h2></header>
            <div className="portal-form-grid">
              <label><span>Turn limit</span><input type="number" value={draft.constraints.turn_limit ?? ""} onChange={(event) => setDraft((current) => ({ ...current, constraints: { ...current.constraints, turn_limit: event.target.value ? Number(event.target.value) : null } }))} /></label>
              <label className="portal-form-grid__span-2"><span>Student use rules</span><textarea value={allowedActionsText} onChange={(event) => setAllowedActionsText(event.target.value)} rows={4} placeholder="One rule per line" /></label>
            </div>
            <p className="portal-note">
              These rules are stored with the lesson as guidance for how students are expected to use the AI during this activity.
            </p>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Reflection</h2></header>
            <div className="portal-form-grid">
              <label className="portal-form-grid__span-2"><span>Reflection prompts</span><textarea value={reflectionPromptsText} onChange={(event) => setReflectionPromptsText(event.target.value)} rows={4} placeholder="One per line" /></label>
              <label><span>Reflection timing</span><select value={draft.reflection.reflection_timing ?? "post"} onChange={(event) => setDraft((current) => ({ ...current, reflection: { ...current.reflection, reflection_timing: event.target.value } }))}><option value="post">After the lesson</option><option value="mid">During the lesson</option><option value="mixed">During and after</option></select></label>
              <label><span>Logging policy</span><select value={draft.reflection.logging_policy ?? "default"} onChange={(event) => setDraft((current) => ({ ...current, reflection: { ...current.reflection, logging_policy: event.target.value } }))}><option value="default">Default logging</option><option value="metadata_only">Metadata only</option><option value="disabled">Disabled</option></select></label>
              <label className="portal-form-grid__span-2"><span>Attached metadata JSON</span><textarea value={attachedMetadataText} onChange={(event) => setAttachedMetadataText(event.target.value)} rows={5} /></label>
            </div>
            <p className="portal-note">
              Reflection timing is lesson metadata for authoring and review. Logging policy is curated at the lesson level and stored explicitly in the lesson document.
            </p>
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
