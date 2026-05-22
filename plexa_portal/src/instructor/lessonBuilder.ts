import type { LessonDocument } from "../api/interfaces"

function cloneLessonDocument(document: LessonDocument): LessonDocument {
  return {
    schema_version: document.schema_version,
    identity: {
      ...document.identity,
      tags: document.identity.tags ? [...document.identity.tags] : undefined,
    },
    intent: {
      ...document.intent,
      discipline: document.intent.discipline ? [...document.intent.discipline] : undefined,
      prerequisites: document.intent.prerequisites ? [...document.intent.prerequisites] : undefined,
    },
    execution: {
      ...document.execution,
      parameters: document.execution.parameters ? { ...document.execution.parameters } : undefined,
      capabilities: document.execution.capabilities ? { ...document.execution.capabilities } : undefined,
    },
    constraints: {
      ...document.constraints,
      allowed_actions: document.constraints.allowed_actions ? [...document.constraints.allowed_actions] : undefined,
    },
    reflection: {
      ...document.reflection,
      hooks: document.reflection.hooks.map((hook) => ({ ...hook })),
    },
  }
}

function createReflectionHook(orderIndex: number) {
  return {
    hook_id: crypto.randomUUID(),
    prompt: "",
    phase: "post" as const,
    order_index: orderIndex,
    carry_to_post: false,
  }
}

export function createDefaultLessonDraft(courseId?: string): LessonDocument {
  return {
    schema_version: "1.0",
    identity: {
      lesson_id: "",
      version: "0.1.0",
      title: "",
      author: "",
      course: courseId ?? "",
      unit: "",
      license: "MIT",
      tags: [],
    },
    intent: {
      learning_objective: "",
      behavioral_focus: "",
      discipline: [],
      difficulty: "introductory",
      prerequisites: [],
      approximate_time: "",
    },
    execution: {
      system_prompt: "",
      initial_assistant_message: "",
      profile: "default",
      parameters: {
        temperature: 0.2,
        top_p: 1,
        max_tokens: 800,
      },
    },
    constraints: {
      input_mode: "text",
      turn_limit: null,
      allowed_actions: [],
    },
    reflection: {
      hooks: [createReflectionHook(0)],
      logging_policy: "default",
    },
  }
}

export function duplicateLessonDraft(document: LessonDocument): LessonDocument {
  return cloneLessonDocument(document)
}

export function listToMultiline(values?: string[] | null): string {
  return values?.join("\n") ?? ""
}

export function multilineToList(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function listToCsv(values?: string[] | null): string {
  return values?.join(", ") ?? ""
}

export function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function jsonToText(value: Record<string, unknown> | null | undefined): string {
  if (!value || Object.keys(value).length === 0) {
    return ""
  }
  return JSON.stringify(value, null, 2)
}

export function textToJsonObject(value: string): Record<string, unknown> {
  if (!value.trim()) {
    return {}
  }
  const parsed = JSON.parse(value) as unknown
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Expected a JSON object.")
  }
  return parsed as Record<string, unknown>
}

export function serializeLessonDraft(document: LessonDocument): string {
  return JSON.stringify(document, null, 2)
}

export function renumberReflectionHooks(document: LessonDocument): LessonDocument {
  return {
    ...document,
    reflection: {
      ...document.reflection,
      hooks: document.reflection.hooks.map((hook, index) => ({
        ...hook,
        order_index: index,
      })),
    },
  }
}

export function newReflectionHook(orderIndex: number) {
  return createReflectionHook(orderIndex)
}
