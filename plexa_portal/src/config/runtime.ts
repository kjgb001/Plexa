/** Invalid or unsafe portal runtime configuration. */
export class ClientConfigurationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ClientConfigurationError"
  }
}

export const APP_ENV = import.meta.env.VITE_APP_ENV ?? "development"

/** Return whether the portal is running with production safety checks enabled. */
export function isProductionAppEnv(): boolean {
  return APP_ENV.trim().toLowerCase() === "production"
}
