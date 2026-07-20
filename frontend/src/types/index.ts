export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
  request_id?: string;
}
export interface User {
  id: number;
  username: string;
  email: string;
  nickname: string;
  avatar_url?: string;
  status: string;
  roles: string[];
}
export interface TokenData {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
}
export interface Course {
  id: number;
  title: string;
  subtitle: string;
  description: string;
  cover_url?: string;
  category_id: number;
  teacher_id: number;
  status: string;
  difficulty: string;
  total_duration: number;
  student_count: number;
  chapters: Chapter[];
}
export interface Chapter {
  id: number;
  title: string;
  sort_order: number;
  lessons: Lesson[];
}
export interface Lesson {
  id: number;
  title: string;
  lesson_type: string;
  content: string;
  duration_seconds: number;
  sort_order: number;
  is_required: boolean;
  is_free_preview: boolean;
}
export interface Category {
  id: number;
  name: string;
  parent_id?: number;
  sort_order: number;
}
export interface Question {
  id: number;
  stem: string;
  question_type: "single" | "multiple" | "boolean";
  options: Record<string, string>;
  correct_answers: string[];
  analysis: string;
  difficulty: "easy" | "medium" | "hard";
}
export interface PaperQuestion {
  question_id: number;
  score: number;
  sort_order: number;
  question: Question;
}
export interface Paper {
  id: number;
  title: string;
  description: string;
  total_score: number;
  questions: PaperQuestion[];
}
export interface PageData<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface Enrollment {
  id: number;
  course_id: number;
  status: string;
  progress: number;
}
export interface MessageItem {
  id: number;
  title: string;
  content: string;
  type: string;
  is_read: boolean;
  created_at: string;
}
