// authService.js
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

class AuthService {
  constructor() {
    this._loadFromStorage();
    this.refreshInProgress = false;
    this.refreshQueue = [];
  }

  _loadFromStorage() {
    try {
      this.tokens = {
        access: localStorage.getItem("access_token"),
        refresh: localStorage.getItem("refresh_token"),
      };
      const userStr = localStorage.getItem("user");
      this.user = userStr ? JSON.parse(userStr) : null;
    } catch (err) {
      console.error("authService load error:", err);
      this.tokens = { access: null, refresh: null };
      this.user = null;
    }
  }

  setTokens(accessToken, refreshToken) {
    this.tokens = { access: accessToken, refresh: refreshToken };
    if (accessToken) localStorage.setItem("access_token", accessToken);
    else localStorage.removeItem("access_token");
    if (refreshToken) localStorage.setItem("refresh_token", refreshToken);
    else localStorage.removeItem("refresh_token");
  }

  setUser(user) {
    this.user = user;
    if (user) localStorage.setItem("user", JSON.stringify(user));
    else localStorage.removeItem("user");
  }

  clearAuth() {
    this.tokens = { access: null, refresh: null };
    this.user = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
  }

  getAccessToken() {
    return this.tokens?.access || localStorage.getItem("access_token");
  }

  getRefreshToken() {
    return this.tokens?.refresh || localStorage.getItem("refresh_token");
  }

  getUser() {
    if (this.user) return this.user;
    try {
      const s = localStorage.getItem("user");
      if (s) {
        this.user = JSON.parse(s);
        return this.user;
      }
    } catch {}
    return null;
  }

  isAuthenticated() {
    return !!(this.getAccessToken() && this.getUser());
  }

  // Queueing to avoid parallel refreshes
  async _enqueueRefresh() {
    if (this.refreshInProgress) {
      return new Promise((resolve, reject) => {
        this.refreshQueue.push({ resolve, reject });
      });
    }
    this.refreshInProgress = true;
    try {
      const newAccess = await this.refreshAccessToken();
      this.refreshInProgress = false;
      this.refreshQueue.forEach(q => q.resolve(newAccess));
      this.refreshQueue = [];
      return newAccess;
    } catch (err) {
      this.refreshInProgress = false;
      this.refreshQueue.forEach(q => q.reject(err));
      this.refreshQueue = [];
      throw err;
    }
  }

  async refreshAccessToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      this.clearAuth();
      throw new Error("No refresh token available");
    }

    // call backend refresh endpoint
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${refreshToken}`,
        "Content-Type": "application/json"
      }
    });

    if (!res.ok) {
      this.clearAuth();
      throw new Error("Refresh token invalid or expired");
    }

    const data = await res.json();
    if (data?.status === "success" && data?.data) {
      const { access_token, refresh_token, user } = data.data;
      this.setTokens(access_token, refresh_token);
      if (user) this.setUser(user);
      return access_token;
    } else {
      this.clearAuth();
      throw new Error("Invalid refresh response");
    }
  }

  // main wrapper used by get/post/patch/delete
  async authenticatedFetch(url, options = {}) {
    // Normalize url (allow endpoint paths)
    const fullUrl = url.startsWith("http") ? url : `${API_URL}${url}`;

    const accessToken = this.getAccessToken();
    const headers = Object.assign({}, options.headers || {});

    if (!(options.body instanceof FormData)) {
      // don't override Content-Type for FormData
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    let response;
    try {
      response = await fetch(fullUrl, { ...options, headers });
    } catch (err) {
      // network error
      throw err;
    }

    // If 401 -> try refresh and retry once
    if (response.status === 401) {
      try {
        const newAccess = await this._enqueueRefresh();
        headers["Authorization"] = `Bearer ${newAccess}`;
        response = await fetch(fullUrl, { ...options, headers });
      } catch (refreshErr) {
        // refresh failed
        this.clearAuth();
        // recommended: force a reload to send user back to login
        window.location.href = "/login";
        throw refreshErr;
      }
    }

    return response;
  }

  // helpers for common HTTP verbs (endpoints expected to start with '/')
  async get(endpoint) {
    return this.authenticatedFetch(endpoint, { method: "GET" });
  }

  async post(endpoint, data) {
    const isForm = data instanceof FormData;
    return this.authenticatedFetch(endpoint, {
      method: "POST",
      body: isForm ? data : JSON.stringify(data)
    });
  }

  async patch(endpoint, data) {
    const isForm = data instanceof FormData;
    return this.authenticatedFetch(endpoint, {
      method: "PATCH",
      body: isForm ? data : JSON.stringify(data)
    });
  }

  async delete(endpoint) {
    return this.authenticatedFetch(endpoint, { method: "DELETE" });
  }

  // file upload helper - endpoint should accept a 'file' field
  async uploadFile(endpoint, file, additionalData = {}) {
    const formData = new FormData();
    formData.append("file", file);
    Object.keys(additionalData || {}).forEach(k => {
      formData.append(k, additionalData[k]);
    });
    return this.authenticatedFetch(endpoint, {
      method: "POST",
      body: formData
    });
  }
}

// export singleton
const authService = new AuthService();
export default authService;
