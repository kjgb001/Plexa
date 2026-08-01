import { useState } from "react"
import { useApis } from "../../api"
import { ApiError } from "../../api/errors"
import type { Lesson, LessonDocument } from "../../api/interfaces"
import {
  createDefaultLessonDraft,
  csvToList,
  duplicateLessonDraft,
  listToCsv,
  listToMultiline,
  multilineToList,
  newReflectionHook,
  renumberReflectionHooks,
  serializeLessonDraft,
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
    allowedActionsText: string
    temperatureText: string
    topPText: string
    maxTokensText: string
    timeoutSecondsText: string
    seedText: string
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
  const [loadedArtifact, setLoadedArtifact] = useState<{ key: string; revision: number } | null>(null)
  const [draft, setDraft] = useState<LessonDocument>(() => createDefaultLessonDraft(courseId))
  const [tagsText, setTagsText] = useState("")
  const [disciplineText, setDisciplineText] = useState("")
  const [prerequisitesText, setPrerequisitesText] = useState("")
  const [allowedActionsText, setAllowedActionsText] = useState("")
  const [temperatureText, setTemperatureText] = useState("0.2")
  const [topPText, setTopPText] = useState("1")
  const [maxTokensText, setMaxTokensText] = useState("800")
  const [timeoutSecondsText, setTimeoutSecondsText] = useState("")
  const [seedText, setSeedText] = useState("")
  const [busy, setBusy] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  function applyDocument(
    next: LessonDocument,
    artifact: { key: string; revision: number } | null = null,
  ) {
    setDraft(duplicateLessonDraft(next))
    setTagsText(listToCsv(next.identity.tags))
    setDisciplineText(listToMultiline(next.intent.discipline))
    setPrerequisitesText(listToMultiline(next.intent.prerequisites))
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
    setLoadedArtifact(artifact)
    setStatusMessage(null)
    setErrorMessage(null)
  }

  function updateReflectionHooks(
    updater: (current: LessonDocument["reflection"]["hooks"]) => LessonDocument["reflection"]["hooks"],
  ) {
    setDraft((current) =>
      renumberReflectionHooks({
        ...current,
        reflection: {
          ...current.reflection,
          hooks: updater(current.reflection.hooks),
        },
      }),
    )
  }

  function addReflectionHook() {
    updateReflectionHooks((current) => [...current, newReflectionHook(current.length)])
  }

  function updateReflectionHook(index: number, updates: Partial<LessonDocument["reflection"]["hooks"][number]>) {
    updateReflectionHooks((current) =>
      current.map((hook, hookIndex) => {
        if (hookIndex !== index) {
          return hook
        }
        const next = { ...hook, ...updates }
        if (next.phase === "post") {
          next.trigger_turn = null
          next.carry_to_post = false
        }
        return next
      }),
    )
  }

  function moveReflectionHook(index: number, direction: -1 | 1) {
    updateReflectionHooks((current) => {
      const target = index + direction
      if (target < 0 || target >= current.length) {
        return current
      }
      const next = [...current]
      const [moved] = next.splice(index, 1)
      next.splice(target, 0, moved)
      return next
    })
  }

  function removeReflectionHook(index: number) {
    updateReflectionHooks((current) => current.filter((_, hookIndex) => hookIndex !== index))
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
      const result = await adminApi.getLesson(courseId, lessonId, version)
      applyDocument(result.lesson, {
        key: `${lessonId}:${version}`,
        revision: result.artifactRevision,
      })
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
        allowedActionsText,
        temperatureText,
        topPText,
        maxTokensText,
        timeoutSecondsText,
        seedText,
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
      const artifactKey = `${compiled.document.identity.lesson_id}:${compiled.document.identity.version}`
      const expectedRevision = loadedArtifact?.key === artifactKey
        ? loadedArtifact.revision
        : null
      const uploaded = await adminApi.uploadLesson(
        courseId,
        compiled.document,
        expectedRevision,
      )
      setLoadedArtifact({ key: artifactKey, revision: uploaded.artifact_revision })

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

  const preview = compileDraft()

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
              <label><span>Difficulty</span><select value={draft.intent.difficulty ?? ""} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, difficulty: event.target.value || undefined } }))}><option value="">Not specified</option><option value="introductory">Introductory</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label>
              <label><span>Approximate time</span><input value={draft.intent.approximate_time ?? ""} onChange={(event) => setDraft((current) => ({ ...current, intent: { ...current.intent, approximate_time: event.target.value } }))} /></label>
              <label className="portal-form-grid__span-2"><span>Discipline</span><textarea value={disciplineText} onChange={(event) => setDisciplineText(event.target.value)} rows={3} placeholder="One per line" /></label>
              <label className="portal-form-grid__span-2"><span>Prerequisites</span><textarea value={prerequisitesText} onChange={(event) => setPrerequisitesText(event.target.value)} rows={3} placeholder="One per line" /></label>
            </div>
          </article>

          <article className="portal-card">
            <header className="portal-card__header"><h2>Execution</h2></header>
            <p className="portal-note">Saving an existing lesson version affects new sessions only. Active and submitted sessions keep their private execution snapshot.</p>
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
              <label><span>Logging policy</span><select value={draft.reflection.logging_policy ?? "default"} onChange={(event) => setDraft((current) => ({ ...current, reflection: { ...current.reflection, logging_policy: event.target.value } }))}><option value="default">Durable transcript + instructor log</option><option value="metadata_only">Durable transcript; metadata-only instructor log</option><option value="disabled">No transcript persistence</option></select></label>
            </div>
            <div className="portal-list">
              {draft.reflection.hooks.map((hook, index) => (
                <article key={hook.hook_id} className="portal-list__item portal-list__item--stack">
                  <div className="portal-card__header">
                    <h2>Hook {index + 1}</h2>
                    <div className="portal-inline-actions">
                      <button className="ghost-button" type="button" onClick={() => moveReflectionHook(index, -1)} disabled={index === 0}>Up</button>
                      <button className="ghost-button" type="button" onClick={() => moveReflectionHook(index, 1)} disabled={index === draft.reflection.hooks.length - 1}>Down</button>
                      <button className="ghost-button ghost-button--danger" type="button" onClick={() => removeReflectionHook(index)} disabled={draft.reflection.hooks.length <= 1}>Remove</button>
                    </div>
                  </div>
                  <div className="portal-form-grid">
                    <label className="portal-form-grid__span-2"><span>Prompt</span><textarea value={hook.prompt} onChange={(event) => updateReflectionHook(index, { prompt: event.target.value })} rows={4} /></label>
                    <label><span>Timing</span><select value={hook.phase} onChange={(event) => updateReflectionHook(index, { phase: event.target.value as "mid" | "post" })}><option value="post">Post-completion</option><option value="mid">Mid-session</option></select></label>
                    {hook.phase === "mid" ? (
                      <>
                        <label><span>Trigger turn</span><input type="number" min="1" value={hook.trigger_turn ?? ""} onChange={(event) => updateReflectionHook(index, { trigger_turn: event.target.value ? Number(event.target.value) : null })} placeholder="Defaults to halfway point" /></label>
                        <label className="portal-form-grid__span-2 portal-checkbox-row"><input type="checkbox" checked={hook.carry_to_post} onChange={(event) => updateReflectionHook(index, { carry_to_post: event.target.checked })} /> Carry this reflection into post-completion if it was never triggered during the session</label>
                      </>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
            <button className="ghost-button" type="button" onClick={addReflectionHook}>
              Add reflection hook
            </button>
            <p className="portal-note">
              Reflection hooks run in the order shown here. Mid-session hooks may trigger during the chat flow; post-completion hooks are shown when the student enters completion mode.
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
