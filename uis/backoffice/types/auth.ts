export interface LoginInput {
  email: string;
  password: string;
}

export interface RegistrationInput extends LoginInput {
  name?: string;
  phone?: string;
  address?: string;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
}

export type AuthField = keyof RegistrationInput;
export type AuthFieldErrors = Partial<Record<AuthField, string>>;
export type AuthMode = "login" | "register";
