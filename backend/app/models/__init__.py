"""Import every model so that ``Base.metadata`` is complete (Alembic, tests)."""
from app.models.access import (  # noqa: F401
    AccessEvent,
    AccessGroup,
    AccessLocation,
    AccessRule,
    Terminal,
    TerminalStatus,
    VerificationEvent,
)
from app.models.attendance import (  # noqa: F401
    AttendanceAdjustment,
    AttendanceJustification,
    AttendanceRecord,
    RecordType,
)
from app.models.auth import (  # noqa: F401
    Permission,
    Role,
    User,
    UserSession,
    role_permissions,
    user_department_scopes,
    user_roles,
    user_unit_scopes,
)
from app.models.biometric import BiometricEnrollment, EnrollmentStatus  # noqa: F401
from app.models.employee import (  # noqa: F401
    AccessProfile,
    BiometricStatus,
    Employee,
    EmploymentStatus,
    employee_access_groups,
)
from app.models.organization import (  # noqa: F401
    Department,
    Holiday,
    Organization,
    Position,
    ScheduleAssignment,
    Sector,
    Unit,
    WorkSchedule,
    WorkShift,
)
from app.models.privacy import (  # noqa: F401
    AuditLog,
    DataSubjectRequest,
    LegalBasisRecord,
    PrivacyNotice,
    RetentionPolicy,
    SecurityIncident,
    SystemSetting,
)
