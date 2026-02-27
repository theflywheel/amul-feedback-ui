# Data Model

## Tables

### `users`
- `id` INTEGER PK
- `email` TEXT UNIQUE NOT NULL
- `username` TEXT NULL
- `is_admin` INTEGER NOT NULL DEFAULT 0 (legacy/unused for auth)

### `questions`
- `id` INTEGER PK
- `category` TEXT
- `q_gu` TEXT NOT NULL
- `q_en` TEXT
- `search_results` TEXT
- `a_en` TEXT
- `a_gu` TEXT
- `active` INTEGER NOT NULL DEFAULT 1

Unique index:
- `(category, q_gu, q_en)` for dedupe/upsert behavior.

### `assignments`
- `id` INTEGER PK
- `user_id` INTEGER FK -> `users.id`
- `question_id` INTEGER FK -> `questions.id`
- UNIQUE `(user_id, question_id)`

### `feedback`
- `id` INTEGER PK
- `user_id` INTEGER FK
- `question_id` INTEGER FK
- `submission_status` TEXT NOT NULL (`draft` or `submitted`)
- `q_translation_rating` INTEGER NULL
- `q_translation_comment` TEXT
- `search_rating` INTEGER NULL
- `search_issue_type` TEXT NULL (`query|retrieval|both|NULL`)
- `search_comment` TEXT
- `answer_accuracy_rating` INTEGER NULL
- `answer_translation_rating` INTEGER NULL
- `answer_comment` TEXT
- `created_at` TEXT (ISO UTC)
- `updated_at` TEXT (ISO UTC)
- UNIQUE `(user_id, question_id)`

### `suggested_questions`
- `id` INTEGER PK
- `user_id` INTEGER FK
- `question_text_gu` TEXT NOT NULL
- `question_text_en` TEXT NULL
- `status` TEXT (`new|accepted|rejected`, enforced by convention)
- `notes` TEXT
- `created_at` TEXT

## Semantics

- Queue completion uses `feedback.submission_status = 'submitted'`.
- `draft` feedback is retained but not counted complete.
- `questions.active = 0` means hidden from annotator queue and "all questions" view.
