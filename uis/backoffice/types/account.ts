export interface ProfileInput {
  name: string;
  phone: string | null;
  address: string | null;
}

export interface Profile extends ProfileInput {
  id: number;
  user_id: number;
}

export interface Account {
  email: string;
  role: "admin" | "manager" | "user";
  profile: Profile | null;
}
