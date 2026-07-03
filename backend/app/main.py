from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.interview import reports_router, router as interview_router
from app.api.routes.resume import router as resume_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.models import auth, candidate, interview, report

Base.metadata.create_all(bind=engine)


def ensure_sqlite_columns() -> None:
    """Add MVP columns for existing local SQLite databases created before migrations."""
    if engine.dialect.name != "sqlite":
        return

    candidate_columns = {
        "email": "TEXT",
        "projects": "TEXT DEFAULT ''",
        "experience": "TEXT DEFAULT ''",
        "education": "TEXT DEFAULT ''",
        "technologies": "TEXT DEFAULT ''",
    }

    with engine.begin() as connection:
        existing_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(candidates)").fetchall()
        }
        for column_name, column_type in candidate_columns.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE candidates ADD COLUMN {column_name} {column_type}"
                )


ensure_sqlite_columns()
settings = get_settings()

app = FastAPI(title="AI Interview Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(auth_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Backend is running"}
