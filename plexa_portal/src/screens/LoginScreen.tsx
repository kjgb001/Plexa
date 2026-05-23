import { useState } from "react"
import type { AuthMode } from "../auth/types"

type PortalChoice = "student" | "instructor"

const portalOptions: Array<{
  id: PortalChoice
  label: string
  eyebrow: string
  summary: string
}> = [
  {
    id: "student",
    label: "Student portal",
    eyebrow: "Learn",
    summary: "Open course workspaces, lessons, sessions, and reflection prompts.",
  },
  {
    id: "instructor",
    label: "Instructor portal",
    eyebrow: "Guide",
    summary: "Manage courses, author lessons, review logs, and monitor classroom flow.",
  },
]

export default function LoginScreen({
  mode,
  onLogin,
}: {
  mode: AuthMode
  onLogin: (options: { userId?: string; portal: PortalChoice }) => Promise<void>
}) {
  const [selectedPortal, setSelectedPortal] = useState<PortalChoice>("student")
  const [devUserId, setDevUserId] = useState("")
  const [submitting, setSubmitting] = useState(false)

  async function handleLogin() {
    if (mode === "dev" && devUserId.trim() === "") {
      return
    }

    setSubmitting(true)
    try {
      await onLogin({
        portal: selectedPortal,
        userId: mode === "dev" ? devUserId.trim() : undefined,
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-stage" aria-labelledby="login-title">
      <section className="login-hero">
        <p className="eyebrow">Plexa Portal</p>
        <h1 id="login-title">A focused workspace for AI lessons.</h1>
        <p className="login-hero__summary">
          Move between classroom sessions, reflection checkpoints, and instructor tooling from one calm entry point.
        </p>
        <div className="login-hero__signals" aria-label="Portal capabilities">
          <span>Guided sessions</span>
          <span>Reflection capture</span>
          <span>Course operations</span>
        </div>
      </section>

      <section className="login-card" aria-label="Portal login">
        <header className="login-card__header">
          <p className="eyebrow">Choose Access</p>
          <h2>Where are you headed?</h2>
          <p>
            Select the portal for this session, then continue with
            {mode === "dev" ? " a dev identity." : " your identity provider."}
          </p>
        </header>

        <div className="login-portal-grid" role="list">
          {portalOptions.map((option) => {
            const isSelected = selectedPortal === option.id
            return (
              <button
                className={`login-portal-option${isSelected ? " login-portal-option--selected" : ""}`}
                type="button"
                key={option.id}
                aria-pressed={isSelected}
                onClick={() => setSelectedPortal(option.id)}
              >
                <span className="login-portal-option__eyebrow">{option.eyebrow}</span>
                <strong>{option.label}</strong>
                <span>{option.summary}</span>
              </button>
            )
          })}
        </div>

        <form
          className="login-form"
          onSubmit={(event) => {
            event.preventDefault()
            void handleLogin()
          }}
        >
          {mode === "dev" ? (
            <label className="login-form__field">
              <span>User-name</span>
              <input
                value={devUserId}
                onChange={(event) => setDevUserId(event.target.value)}
                placeholder="e.g. agi001"
                autoComplete="username"
              />
            </label>
          ) : (
            <p className="login-form__notice">
              You will be redirected to the configured identity provider.
            </p>
          )}

          <button
            className="primary-button login-form__submit"
            type="submit"
            disabled={submitting || (mode === "dev" && devUserId.trim() === "")}
          >
            {submitting ? "Opening..." : `Continue to ${selectedPortal}`}
          </button>
        </form>
      </section>
    </main>
  )
}
