import { create } from "zustand";

interface User {
  id: string;
  email: string;
  full_name: string;
  user_type: string;
  org_id: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string, refreshToken: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: (user, token, refreshToken) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("voiceai_token", token);
      localStorage.setItem("voiceai_refresh", refreshToken);
      localStorage.setItem("voiceai_user", JSON.stringify(user));
    }
    set({ user, token, isAuthenticated: true });
  },
  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("voiceai_token");
      localStorage.removeItem("voiceai_refresh");
      localStorage.removeItem("voiceai_user");
    }
    set({ user: null, token: null, isAuthenticated: false });
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("voiceai_token");
    const userStr = localStorage.getItem("voiceai_user");
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        set({ user, token, isAuthenticated: true });
      } catch {
        set({ user: null, token: null, isAuthenticated: false });
      }
    }
  },
}));

interface Notification {
  id: string;
  type: string;
  message: string;
  timestamp: string;
}

interface DashboardState {
  sidebarOpen: boolean;
  notifications: Notification[];
  toggleSidebar: () => void;
  addNotification: (n: Notification) => void;
  clearNotifications: () => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  sidebarOpen: true,
  notifications: [],
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  addNotification: (n) =>
    set((s) => ({ notifications: [n, ...s.notifications].slice(0, 50) })),
  clearNotifications: () => set({ notifications: [] }),
}));
