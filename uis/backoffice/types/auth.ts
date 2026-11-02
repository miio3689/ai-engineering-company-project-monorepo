export interface LoginInput {
  email: string;
  password: string;
}

export interface RegistrationInput extends LoginInput {
  name?: string;
  phone?: string;
  address?: string;
}

export interface ForgotPasswordInput {
  email: string;
}

export interface ResetPasswordInput {
  token: string;
  new_password: string;
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
}

export type AuthField = keyof RegistrationInput;
export type PasswordField = "current_password" | "new_password" | "confirm_password";
export type AuthFieldErrors = Partial<Record<AuthField | PasswordField, string>>;
export type AuthMode = "login" | "register";
