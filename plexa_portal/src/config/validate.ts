import { API_BASE_URL } from "../api/config"
import {
  AUTH_AUTHORITY,
  AUTH_CLIENT_ID,
  AUTH_DISCOVERY_URL,
  AUTH_MODE,
  ENABLE_DEV_LOGIN,
} from "../auth/config"
import { ClientConfigurationError, isProductionAppEnv } from "./runtime"


export function validateClientConfiguration(): void {
  if (isProductionAppEnv()) {
    if (!import.meta.env.VITE_API_BASE_URL?.trim()) {
      raise("Production client configuration requires VITE_API_BASE_URL.")
    }
    if (!import.meta.env.VITE_AUTH_MODE?.trim()) {
      raise("Production client configuration requires VITE_AUTH_MODE.")
    }
    if (AUTH_MODE === "dev" && !ENABLE_DEV_LOGIN) {
      raise("Production dev login requires VITE_ENABLE_DEV_LOGIN=true.")
    }
  }

  if (AUTH_MODE === "oidc") {
    if (!AUTH_CLIENT_ID.trim()) {
      raise("OIDC mode requires VITE_AUTH_CLIENT_ID.")
    }
    if (!AUTH_AUTHORITY.trim() && !AUTH_DISCOVERY_URL.trim()) {
      raise("OIDC mode requires VITE_AUTH_AUTHORITY or VITE_AUTH_DISCOVERY_URL.")
    }
  }

  if (!API_BASE_URL.trim()) {
    raise("Client API base URL must not be empty.")
  }
}


function raise(message: string): never {
  throw new ClientConfigurationError(message)
}
