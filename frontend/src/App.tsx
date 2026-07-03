import { useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import "./App.css";

type UploadResult = {
  candidate_id: number;
  name: string;
  role_applied: string;
  difficulty: string;
  resume_preview: string;
  profile: CandidateProfile;
  candidate_access_token: string;
};

type CandidateProfile = {
  candidate_name: string | null;
  email: string | null;
  skills: string[];
  projects: string[];
  experience: string[];
  education: string[];
  technologies: string[];
};

type AdminLoginResult = {
  role: "admin";
  username: string;
  access_token: string;
  token_type: string;
};

type InterviewQuestion = {
  id: number;
  skill_area: string;
  question: string;
};

type InterviewPlan = {
  candidate_id: number;
  candidate_name: string;
  candidate_profile: CandidateProfile;
  role_applied: string;
  difficulty: string;
  questions: InterviewQuestion[];
};

type CurrentQuestion = {
  question_index: number;
  question_number: number;
  total_questions: number;
  skill_area: string;
  question: string;
  is_follow_up: boolean;
};

type InterviewSession = {
  interview_id: number;
  candidate_id: number;
  candidate_name: string;
  candidate_profile: CandidateProfile;
  role_applied: string;
  status: string;
  current_question: CurrentQuestion;
};

type InterviewAnswerResponse = {
  interview_id: number;
  status: string;
  is_complete: boolean;
  saved_answer_id: number;
  overall_score?: number | null;
  recommendation?: string | null;
  report_id?: number | null;
  current_question: CurrentQuestion | null;
};

type ChatMessage = {
  id: string;
  speaker: "interviewer" | "candidate" | "system";
  text: string;
  skill_area: string;
  is_follow_up?: boolean;
};

type AdminInterview = {
  interview_id: number;
  candidate_id: number;
  candidate_name: string;
  candidate_email?: string | null;
  candidate_profile?: CandidateProfile;
  role_applied: string;
  status: string;
  overall_score: number | null;
  recommendation: string | null;
  created_at: string;
};

type AdminAnswer = {
  id: number;
  question_index: number;
  skill_area: string;
  question: string;
  answer: string;
  score: number | null;
  feedback: string | null;
  created_at: string;
};

type AdminReport = {
  summary?: string;
  overall_score?: number;
  recommendation?: string;
  recommendation_reason?: string;
  strengths?: string[];
  weaknesses?: string[];
  skill_scores?: Array<{
    skill_area: string;
    score: number;
    notes?: string;
  }>;
  transcript_summary?: Array<{
    skill_area: string;
    score: number | null;
    feedback: string;
  }>;
};

type AdminInterviewDetail = AdminInterview & {
  report: AdminReport | null;
  answers: AdminAnswer[];
};

type SavedReport = {
  report_id: number;
  interview_id: number;
  candidate_id: number;
  candidate: {
    id: number;
    name: string;
    email: string | null;
    role_applied: string;
    difficulty: string;
    profile: CandidateProfile;
  };
  status: string;
  overall_score: number | null;
  recommendation: string | null;
  created_at: string;
  report: AdminReport;
  answers: AdminAnswer[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";
const ADMIN_TOKEN_KEY = "interview-agent-admin-token";
const CANDIDATE_TOKEN_KEY = "interview-agent-candidate-token";
const EMPTY_PROFILE: CandidateProfile = {
  candidate_name: null,
  email: null,
  skills: [],
  projects: [],
  experience: [],
  education: [],
  technologies: [],
};

function getErrorMessage(err: unknown, fallback: string) {
  if (!axios.isAxiosError(err)) {
    return fallback;
  }

  if (!err.response) {
    return "Could not reach the backend. Make sure the API server is running.";
  }

  const detail = err.response.data?.detail;

  if (detail === "Not Found" || err.response.status === 404) {
    return "Backend endpoint not found. Check that the API server is running with the latest routes.";
  }

  return detail || fallback;
}

function authHeaders(token: string | null) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getAdminToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

function getCandidateToken() {
  return sessionStorage.getItem(CANDIDATE_TOKEN_KEY);
}

function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const isInterviewRoute = location.pathname.startsWith("/interview/");

  return (
    <div className={`app-shell${isInterviewRoute ? " interview-shell" : ""}`}>
      {children}
    </div>
  );
}

function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleAdminLogin(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    try {
      setIsSubmitting(true);
      const response = await axios.post<AdminLoginResult>(
        `${API_BASE_URL}/api/auth/admin/login`,
        { username, password },
      );
      localStorage.setItem("interview-agent-role", "admin");
      localStorage.setItem(ADMIN_TOKEN_KEY, response.data.access_token);
      navigate("/admin");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Admin login failed."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={handleAdminLogin}>
        <Link to="/" className="back-link">
          Back to home
        </Link>
        <p className="eyebrow">Admin access</p>
        <h1>Sign in to review interviews.</h1>
        <p>
          This screen is for administrators only. Candidate interviews start from
          the resume upload flow.
        </p>

        <div className="login-fields">
          <label>
            Admin username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label>
            Admin password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
        </div>

        {error && <p className="error-message">{error}</p>}

        <button className="primary-action full-width" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in as Admin"}
        </button>
      </form>
    </main>
  );
}

function HomePage() {
  return (
    <main className="home-page">
      <nav className="product-nav" aria-label="Primary">
        <Link to="/" className="product-mark">
          AI Interview Agent
        </Link>
      </nav>

      <section className="hero-section">
        <div className="hero-bg" aria-hidden="true">
          <div className="dot-field" />
          <div className="wave wave-one" />
          <div className="wave wave-two" />
        </div>

        <div className="hero-label-row">
          <span>AI SCREENING</span>
          <span>/</span>
          <span>RESUME AWARE</span>
          <span>/</span>
          <span>TECHNICAL INTERVIEWS</span>
        </div>

        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Resume-aware technical screening</p>
            <h1>AI Interview Agent</h1>
            <p className="hero-text">
              Upload a resume, generate a focused question plan, run the interview,
              and hand recruiters a scored report without losing the human review loop.
            </p>

            <div className="hero-actions">
              <Link to="/upload" className="primary-action">
                Upload Resume
              </Link>
              <Link to="/admin" className="secondary-action">
                Review Reports
              </Link>
            </div>
          </div>

          <aside className="interface-preview" aria-label="Product preview">
            <div className="preview-header">
              <span>SESSION 01</span>
              <span>READY</span>
            </div>

            <div className="preview-card candidate-preview">
              <span className="tiny-label">Candidate profile</span>
              <strong>Full-stack developer</strong>
              <p>Resume text parsed into role, background, and project signals.</p>
            </div>

            <div className="preview-list">
              <div>
                <span>01</span>
                <p>Walk through a project you owned end to end.</p>
              </div>
              <div>
                <span>02</span>
                <p>Explain the hardest technical tradeoff in that work.</p>
              </div>
              <div>
                <span>03</span>
                <p>Debug a production issue with incomplete context.</p>
              </div>
            </div>

            <div className="preview-footer">
              <span>5 questions</span>
              <span>medium difficulty</span>
            </div>
          </aside>
        </div>
      </section>

    </main>
  );
}

function UploadPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [roleApplied, setRoleApplied] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [plan, setPlan] = useState<InterviewPlan | null>(null);
  const [error, setError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    setPlan(null);

    if (!file) {
      setError("Please choose a resume file.");
      return;
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("role_applied", roleApplied);
    formData.append("difficulty", difficulty);
    formData.append("file", file);

    try {
      setIsUploading(true);
      const response = await axios.post<UploadResult>(
        `${API_BASE_URL}/api/resume/upload`,
        formData,
      );

      setResult(response.data);
      sessionStorage.setItem(
        CANDIDATE_TOKEN_KEY,
        response.data.candidate_access_token,
      );
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Resume upload failed.");
      } else {
        setError("Resume upload failed.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function handleGeneratePlan() {
    if (!result?.candidate_id) {
      setError("Upload a resume first.");
      return;
    }

    setError("");

    try {
      setIsPlanning(true);
      const response = await axios.post<InterviewPlan>(
        `${API_BASE_URL}/api/interview/plan`,
        {
          candidate_id: result.candidate_id,
        },
        {
          headers: authHeaders(getCandidateToken()),
        },
      );

      setPlan(response.data);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Could not generate interview plan.");
      } else {
        setError("Could not generate interview plan.");
      }
    } finally {
      setIsPlanning(false);
    }
  }

  async function handleStartInterview() {
    if (!result?.candidate_id) {
      setError("Upload a resume first.");
      return;
    }

    setError("");

    try {
      setIsStarting(true);
      const response = await axios.post<InterviewSession>(
        `${API_BASE_URL}/api/interview/start`,
        {
          candidate_id: result.candidate_id,
        },
        {
          headers: authHeaders(getCandidateToken()),
        },
      );

      sessionStorage.setItem(
        `interview:${response.data.interview_id}`,
        JSON.stringify(response.data),
      );

      navigate(`/interview/${response.data.interview_id}`, {
        state: response.data,
      });
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Could not start interview.");
      } else {
        setError("Could not start interview.");
      }
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <main className="workspace-page">
      <section className="workspace-header">
        <Link to="/" className="back-link">
          Back to home
        </Link>
        <p className="eyebrow">Interview setup</p>
        <h1>Build the candidate profile.</h1>
        <p>
          Start with the resume. Once the parser confirms the profile, generate a
          role-aware question plan from the same screen.
        </p>
      </section>

      <section className="workspace-grid">
        <form className="upload-panel" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <span className="panel-kicker">Input</span>
            <h2>Candidate details</h2>
          </div>

          <label>
            Candidate name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Aisha Khan"
              required
            />
          </label>

          <label>
            Role applied for
            <input
              value={roleApplied}
              onChange={(event) => setRoleApplied(event.target.value)}
              placeholder="Full-stack Developer"
              required
            />
          </label>

          <label>
            Difficulty
            <select
              value={difficulty}
              onChange={(event) => setDifficulty(event.target.value)}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>

          <label className="file-drop">
            <span>{file ? file.name : "Choose a PDF, DOCX, or TXT resume"}</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <button className="primary-action full-width" type="submit" disabled={isUploading}>
            {isUploading ? "Parsing resume..." : "Upload and Parse Resume"}
          </button>

          {error && <p className="error-message">{error}</p>}
        </form>

        <aside className="status-panel">
          <div className="panel-heading">
            <span className="panel-kicker">Output</span>
            <h2>Profile status</h2>
          </div>

          {!result && (
            <div className="empty-state">
              <span className="pulse-dot" />
              <p>Waiting for a parsed resume.</p>
            </div>
          )}

          {result && (
            <div className="candidate-card">
              <div>
                <span className="tiny-label">Candidate #{result.candidate_id}</span>
                <h3>{result.name}</h3>
                <p>{result.role_applied}</p>
                {result.profile.email && <p>{result.profile.email}</p>}
              </div>
              <span className="difficulty-pill">{result.difficulty}</span>
            </div>
          )}

          {result && (
            <>
              <div className="profile-details">
                {!!result.profile.skills.length && (
                  <div>
                    <span className="tiny-label">Skills</span>
                    <div className="chip-row">
                      {result.profile.skills.slice(0, 10).map((skill) => (
                        <span key={skill}>{skill}</span>
                      ))}
                    </div>
                  </div>
                )}

                {!!result.profile.technologies.length && (
                  <div>
                    <span className="tiny-label">Technologies</span>
                    <div className="chip-row">
                      {result.profile.technologies.slice(0, 10).map((technology) => (
                        <span key={technology}>{technology}</span>
                      ))}
                    </div>
                  </div>
                )}

                {!!result.profile.projects.length && (
                  <div>
                    <span className="tiny-label">Project signals</span>
                    <ul>
                      {result.profile.projects.slice(0, 3).map((project) => (
                        <li key={project}>{project}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="resume-preview">
                <span className="tiny-label">Resume preview</span>
                <p>{result.resume_preview}</p>
              </div>

              <button
                className="secondary-action full-width"
                type="button"
                onClick={handleGeneratePlan}
                disabled={isPlanning}
              >
                {isPlanning ? "Generating plan..." : "Generate Interview Plan"}
              </button>
            </>
          )}
        </aside>
      </section>

      {plan && (
        <section className="plan-section">
          <div className="section-heading">
            <p className="eyebrow">Private interviewer plan</p>
            <h2>{plan.questions.length} topic flow generated</h2>
          </div>

          <p className="private-plan-note">
            The candidate will only see one prompt at a time. Upcoming questions stay
            hidden so follow-ups can happen naturally.
          </p>

          <div className="topic-grid">
            {plan.questions.map((question) => (
              <article className="topic-card" key={question.id}>
                <div className="question-topline">
                  <span>{String(question.id).padStart(2, "0")}</span>
                  <strong>{question.skill_area}</strong>
                </div>
                <p>Prepared but hidden from the candidate.</p>
              </article>
            ))}
          </div>

          <button
            className="primary-action start-interview-action"
            type="button"
            onClick={handleStartInterview}
            disabled={isStarting}
          >
            {isStarting ? "Starting interview..." : "Start Interview"}
          </button>
        </section>
      )}
    </main>
  );
}

function InterviewPage() {
  const { interviewId } = useParams();
  const location = useLocation();
  const storedSession =
    (location.state as InterviewSession | null) ||
    (interviewId
      ? JSON.parse(sessionStorage.getItem(`interview:${interviewId}`) || "null")
      : null);
  const initialSession = storedSession
    ? {
        ...storedSession,
        candidate_profile: storedSession.candidate_profile || EMPTY_PROFILE,
      }
    : null;
  const [session] = useState<InterviewSession | null>(initialSession);
  const [currentQuestion, setCurrentQuestion] = useState<CurrentQuestion | null>(
    initialSession?.current_question || null,
  );
  const [answer, setAnswer] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    initialSession?.current_question
      ? [
          {
            id: "initial-question",
            speaker: "interviewer",
            text: initialSession.current_question.question,
            skill_area: initialSession.current_question.skill_area,
            is_follow_up: initialSession.current_question.is_follow_up,
          },
        ]
      : [],
  );
  const [status, setStatus] = useState(initialSession?.status || "not_started");
  const [reportId, setReportId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [isSessionOpen, setIsSessionOpen] = useState(false);
  const latestMessageRef = useRef<HTMLDivElement | null>(null);
  const answerInputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    latestMessageRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [messages.length]);

  async function handleSubmitAnswer(event: React.FormEvent) {
    event.preventDefault();

    if (!session || !currentQuestion) {
      setError("Start an interview from the upload page first.");
      return;
    }

    const trimmedAnswer = answer.trim();

    if (!trimmedAnswer) {
      setError("Write an answer before submitting.");
      return;
    }

    setError("");

    try {
      setIsSubmitting(true);
      const response = await axios.post<InterviewAnswerResponse>(
        `${API_BASE_URL}/api/interview/answer`,
        {
          interview_id: session.interview_id,
          answer: trimmedAnswer,
          question: currentQuestion.question,
          question_index: currentQuestion.question_index,
          skill_area: currentQuestion.skill_area,
        },
        {
          headers: authHeaders(getCandidateToken()),
        },
      );

      setMessages((items) => [
        ...items,
        {
          id: `answer-${items.length + 1}`,
          speaker: "candidate",
          text: trimmedAnswer,
          skill_area: currentQuestion.skill_area,
        },
        ...(response.data.current_question
          ? [
              {
                id: `question-${items.length + 2}`,
                speaker: "interviewer" as const,
                text: response.data.current_question.question,
                skill_area: response.data.current_question.skill_area,
                is_follow_up: response.data.current_question.is_follow_up,
              },
            ]
          : [
              {
                id: `complete-${items.length + 2}`,
                speaker: "system" as const,
                text: "Interview complete. The transcript has been saved for review.",
                skill_area: "Complete",
              },
            ]),
      ]);
      setAnswer("");
      if (answerInputRef.current) {
        answerInputRef.current.style.height = "auto";
      }
      setStatus(response.data.status);
      if (response.data.report_id) {
        setReportId(response.data.report_id);
      }
      setCurrentQuestion(response.data.current_question);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Could not submit answer.");
      } else {
        setError("Could not submit answer.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleEndInterview() {
    if (!session) {
      setError("Start an interview from the upload page first.");
      return;
    }

    setError("");

    try {
      setIsEnding(true);
      const response = await axios.post<SavedReport>(
        `${API_BASE_URL}/api/interview/end`,
        {
          interview_id: session.interview_id,
        },
        {
          headers: authHeaders(getCandidateToken()),
        },
      );
      setStatus(response.data.status);
      setReportId(response.data.report_id);
      setCurrentQuestion(null);
      setMessages((items) => [
        ...items,
        {
          id: `ended-${items.length + 1}`,
          speaker: "system",
          text: "Interview ended. The final report has been generated.",
          skill_area: "Complete",
        },
      ]);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Could not end interview.");
      } else {
        setError("Could not end interview.");
      }
    } finally {
      setIsEnding(false);
    }
  }

  if (!session) {
    return (
      <main className="placeholder-page">
        <p className="eyebrow">No active session</p>
        <h1>Start from a candidate profile.</h1>
        <p>Upload a resume, generate a plan, then start the interview.</p>
        <Link to="/upload" className="primary-action">
          Go to Upload
        </Link>
      </main>
    );
  }

  return (
    <main className="interview-page">
      <form className="chat-shell" onSubmit={handleSubmitAnswer}>
        <header className="chat-header">
          <div>
            <Link to="/upload" className="back-link chat-back-link">
              Back to setup
            </Link>
            <h1>{session.candidate_name}</h1>
            <p>
              {session.role_applied} screening session. The candidate only sees the
              current prompt.
            </p>
          </div>

          <div className="chat-header-actions">
            <span className="chat-status">{status}</span>
            <button
              className="secondary-action"
              type="button"
              onClick={() => setIsSessionOpen(true)}
            >
              Session State
            </button>
            {currentQuestion && (
              <button
                className="secondary-action"
                type="button"
                onClick={handleEndInterview}
                disabled={isEnding}
              >
                {isEnding ? "Ending..." : "End Interview"}
              </button>
            )}
          </div>
        </header>

        <section className="interview-profile-strip" aria-label="Candidate profile">
          <div>
            <span className="tiny-label">Candidate profile</span>
            <strong>{session.candidate_profile.email || "No email extracted"}</strong>
          </div>
          <div className="chip-row">
            {[...session.candidate_profile.skills, ...session.candidate_profile.technologies]
              .slice(0, 8)
              .map((item) => (
                <span key={item}>{item}</span>
              ))}
          </div>
        </section>

        <section className="conversation-window" aria-label="Interview conversation">
          {messages.map((message, index) => (
            <article
              className={`chat-message chat-message-${message.speaker}`}
              key={message.id}
              ref={index === messages.length - 1 ? latestMessageRef : undefined}
            >
              <span>
                {message.speaker === "candidate"
                  ? "Candidate"
                  : message.speaker === "system"
                    ? "System"
                    : "Interviewer"}
                {message.is_follow_up ? " follow-up" : ""}
              </span>
              <p>{message.text}</p>
            </article>
          ))}
        </section>

        <footer className="chat-composer">
          {currentQuestion ? (
            <>
              <label>
                Reply
                <textarea
                  ref={answerInputRef}
                  value={answer}
                  onChange={(event) => {
                    setAnswer(event.target.value);
                    event.currentTarget.style.height = "auto";
                    event.currentTarget.style.height = `${event.currentTarget.scrollHeight}px`;
                  }}
                  placeholder="Type the candidate's response..."
                  rows={1}
                />
              </label>

              <button
                className="primary-action"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Saving answer..." : "Submit Answer"}
              </button>
            </>
          ) : (
            <div className="completion-card">
              <p className="eyebrow">Complete</p>
              <h2>Interview finished.</h2>
              <p>
                All answers have been saved. The final report is ready for review.
              </p>
              {reportId && (
                <Link to={`/reports/${reportId}`} className="primary-action">
                  View Report
                </Link>
              )}
            </div>
          )}

          {error && <p className="error-message">{error}</p>}
        </footer>
      </form>

      {isSessionOpen && (
        <div className="session-overlay" role="dialog" aria-modal="true">
          <aside className="session-floating-panel">
            <button
              className="session-close"
              type="button"
              onClick={() => setIsSessionOpen(false)}
              aria-label="Close session state"
            >
              Close
            </button>
          <div className="panel-heading">
            <span className="panel-kicker">Session state</span>
            <h2>Conversation control</h2>
          </div>

          <div className="session-meter">
            <span>Progress</span>
            <strong>
              {currentQuestion
                ? `${currentQuestion.question_number} / ${currentQuestion.total_questions}`
                : "Complete"}
            </strong>
          </div>

          <div className="session-meter">
            <span>Current area</span>
            <strong>{currentQuestion?.skill_area || "Review"}</strong>
          </div>

          <div className="session-note">
            <p>
              Short or vague answers trigger one follow-up before the interview moves
              to the next prepared topic.
            </p>
          </div>
          </aside>
        </div>
      )}
    </main>
  );
}

function AdminDashboardPage() {
  const navigate = useNavigate();
  const [interviews, setInterviews] = useState<AdminInterview[]>([]);
  const [selectedInterview, setSelectedInterview] = useState<AdminInterviewDetail | null>(
    null,
  );
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadInterviews() {
      const token = getAdminToken();

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        const response = await axios.get<{ interviews: AdminInterview[] }>(
          `${API_BASE_URL}/api/admin/interviews`,
          {
            headers: authHeaders(token),
          },
        );
        setInterviews(response.data.interviews);
      } catch (err: unknown) {
        if (axios.isAxiosError(err)) {
          setError(err.response?.data?.detail || "Could not load interviews.");
        } else {
          setError("Could not load interviews.");
        }
      } finally {
        setIsLoading(false);
      }
    }

    loadInterviews();
  }, [navigate]);

  async function loadInterviewDetail(interviewId: number) {
    setError("");

    try {
      const response = await axios.get<AdminInterviewDetail>(
        `${API_BASE_URL}/api/admin/interviews/${interviewId}`,
        {
          headers: authHeaders(getAdminToken()),
        },
      );
      setSelectedInterview(response.data);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Could not load interview detail.");
      } else {
        setError("Could not load interview detail.");
      }
    }
  }

  function handleAdminLogout() {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem("interview-agent-role");
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    setSelectedInterview(null);
    navigate("/login");
  }

  return (
    <main className="admin-page">
      <section className="admin-page-header">
        <div>
          <p className="eyebrow">Admin dashboard</p>
          <h1>Completed interviews and scores.</h1>
          <p>
            Review candidate outcomes, score summaries, and answer-level feedback from
            the LLM-assisted interview flow.
          </p>
        </div>

        <button className="secondary-action" type="button" onClick={handleAdminLogout}>
          Log out
        </button>
      </section>

      {error && <p className="error-message">{error}</p>}

      <section className="admin-grid">
        <div className="admin-list-panel">
          <div className="panel-heading">
            <span className="panel-kicker">Completed</span>
            <h2>Interview sessions</h2>
          </div>

          {isLoading && (
            <div className="empty-state">
              <span className="pulse-dot" />
              <p>Loading completed interviews.</p>
            </div>
          )}

          {!isLoading && interviews.length === 0 && (
            <div className="empty-state">
              <p>No completed interviews yet.</p>
            </div>
          )}

          <div className="admin-interview-list">
            {interviews.map((interview) => (
              <button
                type="button"
                key={interview.interview_id}
                onClick={() => loadInterviewDetail(interview.interview_id)}
                className={
                  selectedInterview?.interview_id === interview.interview_id
                    ? "admin-row active"
                    : "admin-row"
                }
              >
                <span>#{interview.interview_id}</span>
                <strong>{interview.candidate_name}</strong>
                <p>{interview.role_applied}</p>
                <b>{interview.overall_score ?? "Pending"}</b>
              </button>
            ))}
          </div>
        </div>

        <aside className="admin-detail-panel">
          {!selectedInterview && (
            <div className="empty-state">
              <p>Select an interview to view scores and feedback.</p>
            </div>
          )}

          {selectedInterview && (
            <>
              <div className="admin-score-header">
                <div>
                  <span className="tiny-label">Candidate</span>
                  <h2>{selectedInterview.candidate_name}</h2>
                  <p>{selectedInterview.role_applied}</p>
                </div>
                <div className="score-badge">
                  <span>Score</span>
                  <strong>{selectedInterview.overall_score ?? "-"}</strong>
                </div>
              </div>

              <div className="session-meter">
                <span>Recommendation</span>
                <strong>{selectedInterview.recommendation || "Pending"}</strong>
              </div>

              {selectedInterview.report && (
                <section className="admin-report-card">
                  <p className="eyebrow">Generated report</p>
                  <h3>Summary</h3>
                  <p>{selectedInterview.report.summary || "No summary available."}</p>

                  <div className="report-columns">
                    <div>
                      <strong>Strengths</strong>
                      <ul>
                        {(selectedInterview.report.strengths || []).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <strong>Weaknesses</strong>
                      <ul>
                        {(selectedInterview.report.weaknesses || []).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {selectedInterview.report.recommendation_reason && (
                    <div className="report-reason">
                      <strong>Recommendation reason</strong>
                      <p>{selectedInterview.report.recommendation_reason}</p>
                    </div>
                  )}

                  {!!selectedInterview.report.skill_scores?.length && (
                    <div className="skill-score-grid">
                      {selectedInterview.report.skill_scores.map((skill) => (
                        <article key={skill.skill_area}>
                          <span>{skill.skill_area}</span>
                          <strong>{skill.score}</strong>
                          {skill.notes && <p>{skill.notes}</p>}
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              )}

              <div className="admin-answer-list">
                {selectedInterview.answers.map((answer) => (
                  <article key={answer.id}>
                    <div className="question-topline">
                      <span>{String(answer.question_index + 1).padStart(2, "0")}</span>
                      <strong>{answer.skill_area}</strong>
                    </div>
                    <p>{answer.question}</p>
                    <blockquote>{answer.answer}</blockquote>
                    <div className="answer-score-line">
                      <span>Score {answer.score ?? "-"}/5</span>
                      <span>{answer.feedback || "No feedback yet."}</span>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </aside>
      </section>
    </main>
  );
}

function ReportsPage() {
  const { reportId } = useParams();
  const [report, setReport] = useState<SavedReport | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadReport() {
      if (!reportId) {
        setError("Open a specific report from a completed interview.");
        setIsLoading(false);
        return;
      }

      try {
        const response = await axios.get<SavedReport>(
          `${API_BASE_URL}/api/reports/${reportId}`,
          {
            headers: authHeaders(getCandidateToken()),
          },
        );
        setReport(response.data);
      } catch (err: unknown) {
        setError(getErrorMessage(err, "Could not load report."));
      } finally {
        setIsLoading(false);
      }
    }

    loadReport();
  }, [reportId]);

  if (isLoading) {
    return (
      <main className="placeholder-page">
        <p className="eyebrow">Reports</p>
        <h1>Loading report.</h1>
      </main>
    );
  }

  if (error || !report) {
    return (
      <main className="placeholder-page">
        <p className="eyebrow">Reports</p>
        <h1>Report unavailable.</h1>
        <p>{error || "The report could not be found."}</p>
        <Link to="/upload" className="primary-action">
          Start New Interview
        </Link>
      </main>
    );
  }

  const payload = report.report;
  const strengths = payload.strengths || [];
  const weaknesses = payload.weaknesses || [];
  const skillScores = payload.skill_scores || [];
  const transcript = report.answers.length ? report.answers : [];

  return (
    <main className="report-page">
      <section className="report-hero">
        <Link to="/" className="back-link">
          Back to home
        </Link>
        <p className="eyebrow">Report #{report.report_id}</p>
        <div className="report-title-row">
          <div>
            <h1>{report.candidate.name}</h1>
            <p>
              {report.candidate.role_applied} screening
              {report.candidate.email ? ` · ${report.candidate.email}` : ""}
            </p>
          </div>
          <div className="score-badge">
            <span>Score</span>
            <strong>{report.overall_score ?? payload.overall_score ?? "-"}</strong>
          </div>
        </div>
      </section>

      <section className="report-grid">
        <article className="admin-report-card report-summary-card">
          <p className="eyebrow">Summary</p>
          <p>{payload.summary || "No summary available."}</p>
          <div className="session-meter">
            <span>Recommendation</span>
            <strong>{report.recommendation || payload.recommendation || "Pending"}</strong>
          </div>
          {payload.recommendation_reason && (
            <div className="report-reason">
              <strong>Recommendation reason</strong>
              <p>{payload.recommendation_reason}</p>
            </div>
          )}
        </article>

        <article className="admin-report-card">
          <p className="eyebrow">Candidate details</p>
          <div className="profile-details">
            {!!report.candidate.profile.skills.length && (
              <div>
                <span className="tiny-label">Skills</span>
                <div className="chip-row">
                  {report.candidate.profile.skills.map((skill) => (
                    <span key={skill}>{skill}</span>
                  ))}
                </div>
              </div>
            )}
            {!!report.candidate.profile.projects.length && (
              <div>
                <span className="tiny-label">Projects</span>
                <ul>
                  {report.candidate.profile.projects.slice(0, 4).map((project) => (
                    <li key={project}>{project}</li>
                  ))}
                </ul>
              </div>
            )}
            {!!report.candidate.profile.experience.length && (
              <div>
                <span className="tiny-label">Experience</span>
                <ul>
                  {report.candidate.profile.experience.slice(0, 4).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {!!report.candidate.profile.education.length && (
              <div>
                <span className="tiny-label">Education</span>
                <ul>
                  {report.candidate.profile.education.slice(0, 3).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {!!report.candidate.profile.technologies.length && (
              <div>
                <span className="tiny-label">Technologies</span>
                <div className="chip-row">
                  {report.candidate.profile.technologies.map((technology) => (
                    <span key={technology}>{technology}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </article>
      </section>

      <section className="report-columns report-page-columns">
        <div>
          <strong>Strengths</strong>
          <ul>
            {strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <strong>Weaknesses</strong>
          <ul>
            {weaknesses.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>

      {!!skillScores.length && (
        <section className="skill-score-grid report-skill-grid">
          {skillScores.map((skill) => (
            <article key={skill.skill_area}>
              <span>{skill.skill_area}</span>
              <strong>{skill.score}</strong>
              {skill.notes && <p>{skill.notes}</p>}
            </article>
          ))}
        </section>
      )}

      <section className="admin-answer-list">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Transcript</p>
            <h2>Q&A summary</h2>
          </div>
        </div>
        {transcript.map((answer) => (
          <article key={answer.id}>
            <div className="question-topline">
              <span>{String(answer.question_index + 1).padStart(2, "0")}</span>
              <strong>{answer.skill_area}</strong>
            </div>
            <p>{answer.question}</p>
            <blockquote>{answer.answer}</blockquote>
            <div className="answer-score-line">
              <span>Score {answer.score ?? "-"}/5</span>
              <span>{answer.feedback || "No feedback yet."}</span>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

function NotFoundPage() {
  return (
    <main className="not-found-page">
      <section>
        <p className="eyebrow">404</p>
        <h1>Page not found.</h1>
        <p>The route you opened does not exist in this interview workspace.</p>
        <div className="not-found-actions">
          <Link to="/" className="primary-action">
            Back Home
          </Link>
          <Link to="/upload" className="secondary-action">
            Upload Resume
          </Link>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/interview/:interviewId" element={<InterviewPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:reportId" element={<ReportsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
