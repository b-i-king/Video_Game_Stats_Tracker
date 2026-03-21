const API_URL = process.env.EXPO_PUBLIC_API_URL ?? '';

export interface LoginResponse {
  token: string;
  user: {
    email: string;
    username: string;
    role: string;
  };
}

export async function loginWithEmail(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? `Login failed (${res.status})`);
  }
  return res.json();
}

export async function registerUser(
  email: string,
  username: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/api/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? `Registration failed (${res.status})`);
  }
  return res.json();
}

export async function registerPushToken(jwt: string, pushToken: string): Promise<void> {
  await fetch(`${API_URL}/api/register_push_token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${jwt}`,
    },
    body: JSON.stringify({ push_token: pushToken }),
  });
}
