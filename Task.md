### Task Description: Golden Set Feedback UI

**Goal**  
Build a small, clean web UI for agro-domain experts to review and give structured feedback on a golden set of Q&A data (Gujarati ↔ English translations, search results, and answers). The system should be simple enough for non‑technical government users, but robust enough to support CSV‑based data management and basic user assignment.

---

### Core Data & Entities

- **Source data** (from `ui/500_goldenset_final_sheet.csv`):
  - `Category`
  - `Q (Gu)` – original Gujarati question
  - `Q (En)` – English translation of the question
  - `Search Results` – retrieved context (possibly multiple query‑response blocks)
  - `A(En)` – English answer
  - `A (Gu)` – Gujarati answer

- **Database (SQLite)**
  - **Users**
    - `id`
    - `email` (mandatory, unique-ish; used for selection/dropdown)
    - `username` (optional, display name)
    - `is_admin` (bool)
  - **Questions**
    - `id`
    - fields mirroring the CSV columns above
    - `active` flag (for temporarily disabling certain questions, optional)
  - **Assignments**
    - `id`
    - `user_id`
    - `question_id`
  - **Feedback**
    - `id`
    - `user_id`
    - `question_id`
    - **Question translation feedback** (e.g. rating + free text)
    - **Search results feedback** (see nuances below)
    - **Answer translation & accuracy feedback** (e.g. separate ratings for En/Gu + free text)
    - `created_at`, `updated_at`
  - **Suggested Questions**
    - `id`
    - `user_id` (who suggested it)
    - `question_text_gu`
    - optional `question_text_en`
    - `status` (new / accepted / rejected)
    - `notes` (admin notes)

---

### Feedback Aims (per Section)

These will become short helper texts below each feedback header in the UI.

- **Question Translation (Gu → En)**
  - Aim: Evaluate whether the English translation accurately captures the meaning, tone, and important details of the Gujarati question.
  - Hints for experts:
    - Is any important nuance or context from Gujarati missing or distorted?
    - Is the domain terminology (e.g. disease names, farming practices) translated correctly?
    - Would a non‑Gujarati agro expert understand the original farmer’s intent from this English text?

- **Search Results**
  - Aim: Judge whether the retrieved context is appropriate and sufficient to answer the question.
  - Important nuance: Problems may come from:
    - **Bad query formulation** (the queries used to call the search tool are off‑topic or too vague).
    - **Bad retrieval** (queries are fine, but documents returned are irrelevant or low quality).
  - Hints for experts:
    - Are the documents clearly related to the farmer’s question?
    - Is there enough information in the retrieved text to answer the question confidently?
    - If something is wrong, is it:
      - The **query** focus is wrong (e.g. wrong disease, wrong species, wrong concept)?
      - The **retrieved documents** are off‑topic or too general?

- **Answer Translation & Accuracy**
  - Aim: Assess whether the answers (English and Gujarati) are factually correct, appropriate for the question, and understandable for farmers.
  - Hints for experts:
    - **Accuracy**: Is the agronomy / veterinary advice technically correct and safe?
    - **Relevance**: Does the answer directly address the question, or does it wander?
    - **Clarity**: Is the language simple and unambiguous enough for farmers?
    - **Translation**:
      - Does the Gujarati answer reflect the same content as the English answer?
      - Are technical terms and disease names in Gujarati correct and standard?

(You can refine these into specific rating scales + optional comment fields later.)

---

### User Flows

#### 1. Annotator / Expert Flow

- **“Login” by selecting email**
  - On page load, show a simple dropdown of all known user emails (no password).
  - User selects their email and clicks “Continue”.
  - This just sets a “current user” in the session; no real auth.

- **Work queue: one question at a time**
  - After selecting email:
    - Show **one assigned question**:
      - Category
      - `Q (Gu)`
      - `Q (En)`
      - `Search Results` (possibly in a scrollable/collapsible area due to size)
      - `A(En)`
      - `A (Gu)`
    - Show **feedback controls** for:
      - Question translation
      - Search results
      - Answer translation & accuracy
    - Provide **“Save & Next Question”** button:
      - Creates/updates feedback for that `(user, question)`.
      - Moves to the next assigned, not‑yet‑completed question.
  - If the user has no more assigned questions:
    - Show a friendly message like “You have completed all your assigned questions.”

- **Global list + suggestion**
  - Separate view / tab: “All Questions”
    - Show a simple table of all existing questions (at least `Q (Gu)` and maybe ID/category).
    - At the top or bottom: a form to **suggest a new question**:
      - `New question (Gujarati)` [required]
      - `New question (English)` [optional]
      - Brief text: “Suggest questions you think should be added to the feedback set.”
    - On submit, create a `SuggestedQuestion` row linked to the current user.

#### 2. Admin Flow

- **Admin login**
  - Simple email + password form, or just password + hardcoded admin email.
  - Once logged in, show an admin dashboard.

- **User management**
  - View list of users (email, username, is_admin).
  - Button to **add user**:
    - Enter email, optional username.
    - “Make admin” checkbox.
  - (If you prefer) “Auto-generate credentials” can just create a new user with a random password for a future, more secure flow, but for now email selection is enough.

- **Assignments**
  - View list of questions and current assignment counts.
  - Controls:
    - **Random assignment**:
      - Select one or more users.
      - Choose number of questions per user (or “assign all unassigned”).
      - System randomly assigns remaining questions to selected users.
    - **Manual assignment**:
      - For a given question, choose a user from a dropdown and add an assignment.
  - Should be easy to see which questions are:
    - Unassigned
    - Partially annotated
    - Fully annotated (all required users done)

- **CSV import/export**
  - **Export feedback** as CSV:
    - Columns like: `user_email, question_id, Q (Gu), Q (En), feedback_* fields, timestamps`.
  - **Export questions** as CSV (current DB copy of your original CSV).
  - **Import / update questions**:
    - Upload a CSV in the same format as the original.
    - Options:
      - Insert new questions.
      - Optionally update existing ones by ID or by `(Category, Q (Gu), Q (En))`.
  - **Import / update answers / search results** in case you regenerate them:
    - Same pattern: admin uploads updated CSV, backend merges into `Questions` table.

---

### UI / UX Guidelines

- **Style**
  - Clean, minimal, no decorative fluff.
  - **Light background**: white and very light greys.
  - **Soft pastel accent colors** for buttons / highlights.
  - Large, readable fonts; clear labels.
  - Avoid dense tables except in admin views.

- **Layout**
  - For annotators:
    - Top section: user email selector (if not yet chosen).
    - Main panel:
      - Question info and answers stacked vertically.
      - Search results in a scrollable box, maybe with collapsible sections per query.
      - Feedback controls grouped under clear headings (with 1–2 line helper text under each).
    - Bottom: “Save & Next Question”.
  - For admin:
    - Simple navigation tabs: `Users`, `Assignments`, `Data (Import/Export)`, `Suggestions`.

- **Resilience**
  - Auto‑save feedback on “Next” with clear confirmation/errors.
  - Handle huge `Search Results` gracefully (scrolling, expandable sections).
  - If something fails, show a simple error message with a “Retry” button, not a stack trace.

---

### Gaps / Design Choices You May Want to Clarify Later

- **Feedback granularity**
  - For each of the three areas, do you want:
    - Numeric ratings (e.g. 1–5), or simple “good / needs fix” toggles?
    - Required vs optional free‑text comments?
- **Multiple annotators per question**
  - Is each question annotated by **one** expert or **multiple**?
  - If multiple, admin views may need aggregation (e.g. average rating, disagreement flags).
- **Concurrency rules**
  - If you reassign the same question to different users, should they overwrite or add separate feedback entries? (Design above assumes separate entries per `(user, question)`.)

If you’d like, next step can be a concrete tech stack proposal (e.g. FastAPI + SQLite + a small React/Vue frontend, or a single‑page Flask/Jinja app) and an initial schema + API endpoint list implementing this spec.