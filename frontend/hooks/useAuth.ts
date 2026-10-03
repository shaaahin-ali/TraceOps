/**
 * useAuth — Authentication Hook
 * ================================
 * Manages JWT token and user session stored in localStorage.
 *
 * Usage:
 *   const { user, token, login, logout, isAuthenticated } = useAuth();
 *
 * Features:
 * - Reads token/user from localStorage on mount
 * - login() stores token and user, redirects to dashboard
 * - logout() clears storage, redirects to login
 * - isAuthenticated computed from token existence
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { User, AuthResponse } from "@/types";

const TOKEN_KEY = "rt_token";
const USER_KEY = "rt_user";

export function useAuth() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Read from localStorage on mount (client-side only)
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (storedToken) setToken(storedToken);
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem(USER_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  /**
   * Store credentials after a successful login API response.
   * Redirects to /dashboard.
   */
  const login = useCallback(
    (authResponse: AuthResponse) => {
      const userObj: User = {
        user_id: authResponse.user_id,
        name: authResponse.name,
        email: authResponse.email,
        role: authResponse.role,
      };
      localStorage.setItem(TOKEN_KEY, authResponse.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(userObj));
      setToken(authResponse.access_token);
      setUser(userObj);
      router.replace("/dashboard");
    },
    [router]
  );

  /**
   * Clear all session data and redirect to /login.
   */
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  /**
   * Require authentication — redirect to login if no token.
   * Call this in useEffect on protected pages.
   */
  const requireAuth = useCallback(() => {
    if (!isLoading && !token) {
      router.replace("/login");
    }
  }, [isLoading, token, router]);

  /**
   * Check if the current user has one of the given roles.
   * Returns false if user is not authenticated.
   */
  const hasRole = useCallback(
    (...roles: User["role"][]): boolean => {
      if (!user) return false;
      return roles.includes(user.role);
    },
    [user]
  );

  return {
    token,
    user,
    isLoading,
    isAuthenticated: !!token,
    login,
    logout,
    requireAuth,
    hasRole,
  };
}
