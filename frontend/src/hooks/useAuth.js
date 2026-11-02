import { useCallback, useState } from "react";
import { login as apiLogin } from "../services/api";

const TOKEN_KEY = "vda_token";
const USERNAME_KEY = "vda_username";

export function useAuth() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY));
  const [username, setUsername] = useState(() => sessionStorage.getItem(USERNAME_KEY));

  const login = useCallback(async (user, password) => {
    const accessToken = await apiLogin(user, password);
    sessionStorage.setItem(TOKEN_KEY, accessToken);
    sessionStorage.setItem(USERNAME_KEY, user);
    setToken(accessToken);
    setUsername(user);
    return accessToken;
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USERNAME_KEY);
    sessionStorage.removeItem("vda_session_id");
    setToken(null);
    setUsername(null);
  }, []);

  return { token, username, isAuthenticated: !!token, login, logout };
}
