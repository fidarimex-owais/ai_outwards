import { useAuth } from "./hooks/useAuth";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  const { token, username, isAuthenticated, login, logout } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage onLogin={login} />;
  }

  return <ChatPage key={token} token={token} username={username} onLogout={logout} />;
}
