let currentSessionId: string | null = null

export function setCurrentSession(sessionId: string) {
  currentSessionId = sessionId
}

export function getCurrentSession() {
  if (!currentSessionId) {
    throw new Error("No active session")
  }

  return currentSessionId
}

export function clearCurrentSession() {
  currentSessionId = null
}