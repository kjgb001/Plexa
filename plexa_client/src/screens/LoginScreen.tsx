import { useState } from "react"

export default function LoginScreen({ onLogin }: { onLogin: (userId: string) => Promise<void> }) {
  const [userId, setUserId] = useState("")

  async function handleLogin() {
    if (!userId.trim()) return
    await onLogin(userId.trim())
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa</h1>
      <p>Enter a dev user ID:</p>

      <input
        value={userId}
        onChange={e => setUserId(e.target.value)}
        placeholder="student1"
      />

      <button onClick={() => void handleLogin()}>Login</button>
    </div>
  )
}
