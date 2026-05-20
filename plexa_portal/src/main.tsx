import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./styles.css"
import App from "./App.tsx"
import { AuthProvider } from "./auth/AuthProvider.tsx"
import { ClientConfigurationError } from "./config/runtime.ts"
import { validateClientConfiguration } from "./config/validate.ts"
import { ThemeProvider } from "./theme/ThemeProvider.tsx"

const root = createRoot(document.getElementById("root")!)

try {
  validateClientConfiguration()

  root.render(
    <StrictMode>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </StrictMode>,
  )
} catch (error) {
  const message = error instanceof ClientConfigurationError
    ? error.message
    : "Client startup failed."

  root.render(
    <StrictMode>
      <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <h1>Plexa Portal</h1>
        <p>Client configuration error.</p>
        <pre>{message}</pre>
      </div>
    </StrictMode>,
  )
}
