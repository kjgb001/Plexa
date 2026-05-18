export class ClientConfigurationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ClientConfigurationError"
  }
}

export const APP_ENV = import.meta.env.VITE_APP_ENV ?? "development"

export function isProductionAppEnv(): boolean {
  return APP_ENV.trim().toLowerCase() === "production"
}
