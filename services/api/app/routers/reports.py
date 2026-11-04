from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_user, get_db
from ssc_core.models.alerting import Alert
from ssc_core.models.monitoring import CheckTargetType, DowntimeIncident, UptimeCheck
from ssc_core.models.security import FileIntegrityEvent, LoginEvent, SecurityEvent
from ssc_core.models.server import Server
from ssc_core.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])

# A table of every matching row can make the PDF unreasonably large; each
# detail table is capped and a note appended when rows were left out. The
# summary counts above each table are always computed over the full set.
MAX_TABLE_ROWS = 40


def _parse_date(value: str | None, *, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field}, expected YYYY-MM-DD") from None


@router.get("/pdf")
async def generate_pdf_report(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    server_id: UUID | None = Query(default=None),
) -> StreamingResponse:
    today = datetime.now(timezone.utc).date()
    parsed_start = _parse_date(start_date, field="start_date") or (today - timedelta(days=29))
    parsed_end = _parse_date(end_date, field="end_date") or today
    if parsed_start > parsed_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must not be after end_date")

    range_start = datetime.combine(parsed_start, time.min, tzinfo=timezone.utc)
    range_end = datetime.combine(parsed_end, time.min, tzinfo=timezone.utc) + timedelta(days=1)

    server: Server | None = None
    if server_id:
        server = (await db.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
        if server is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    servers_query = select(Server).where(Server.is_archived.is_(False))
    if server_id:
        servers_query = servers_query.where(Server.id == server_id)
    servers = (await db.execute(servers_query.order_by(Server.name))).scalars().all()

    # These tables can accumulate a very large number of rows over time
    # (uptime checks run every few minutes per target; failed logins and
    # security events can spike hugely during a brute-force burst). Loading
    # every matching row into memory just to count or display the newest 40
    # of them previously OOM-killed the API container on real data -- counts
    # are now computed in SQL via COUNT(), and only the rows actually shown
    # in the PDF are ever fetched, capped at MAX_TABLE_ROWS in the query itself.

    uptime_filters = [UptimeCheck.checked_at >= range_start, UptimeCheck.checked_at < range_end]
    if server_id:
        uptime_filters += [UptimeCheck.target_type == CheckTargetType.server, UptimeCheck.target_id == server_id]
    total_checks = (await db.execute(select(func.count()).select_from(UptimeCheck).where(*uptime_filters))).scalar_one()
    up_checks = (
        await db.execute(select(func.count()).select_from(UptimeCheck).where(*uptime_filters, UptimeCheck.is_up.is_(True)))
    ).scalar_one()
    uptime_pct = (up_checks / total_checks * 100) if total_checks else None

    incident_filters = [
        DowntimeIncident.started_at < range_end,
        (DowntimeIncident.resolved_at.is_(None)) | (DowntimeIncident.resolved_at >= range_start),
    ]
    if server_id:
        incident_filters += [DowntimeIncident.target_type == CheckTargetType.server, DowntimeIncident.target_id == server_id]
    incident_count = (await db.execute(select(func.count()).select_from(DowntimeIncident).where(*incident_filters))).scalar_one()
    incidents = (
        await db.execute(
            select(DowntimeIncident).where(*incident_filters).order_by(DowntimeIncident.started_at.desc()).limit(MAX_TABLE_ROWS)
        )
    ).scalars().all()

    sec_filters = [SecurityEvent.occurred_at >= range_start, SecurityEvent.occurred_at < range_end]
    if server_id:
        sec_filters.append(SecurityEvent.server_id == server_id)
    security_event_count = (await db.execute(select(func.count()).select_from(SecurityEvent).where(*sec_filters))).scalar_one()
    security_events = (
        await db.execute(
            select(SecurityEvent)
            .options(selectinload(SecurityEvent.server))
            .where(*sec_filters)
            .order_by(SecurityEvent.occurred_at.desc())
            .limit(MAX_TABLE_ROWS)
        )
    ).scalars().all()

    login_filters = [
        LoginEvent.occurred_at >= range_start,
        LoginEvent.occurred_at < range_end,
        LoginEvent.was_successful.is_(False),
    ]
    if server_id:
        login_filters.append(LoginEvent.server_id == server_id)
    failed_login_count = (await db.execute(select(func.count()).select_from(LoginEvent).where(*login_filters))).scalar_one()
    failed_logins = (
        await db.execute(
            select(LoginEvent)
            .options(selectinload(LoginEvent.server))
            .where(*login_filters)
            .order_by(LoginEvent.occurred_at.desc())
            .limit(MAX_TABLE_ROWS)
        )
    ).scalars().all()

    fi_filters = [FileIntegrityEvent.detected_at >= range_start, FileIntegrityEvent.detected_at < range_end]
    if server_id:
        fi_filters.append(FileIntegrityEvent.server_id == server_id)
    file_event_count = (await db.execute(select(func.count()).select_from(FileIntegrityEvent).where(*fi_filters))).scalar_one()
    unapproved_filters = [*fi_filters, FileIntegrityEvent.is_approved_change.is_(False)]
    unapproved_count = (
        await db.execute(select(func.count()).select_from(FileIntegrityEvent).where(*unapproved_filters))
    ).scalar_one()
    unapproved_file_events = (
        await db.execute(
            select(FileIntegrityEvent)
            .options(selectinload(FileIntegrityEvent.server))
            .where(*unapproved_filters)
            .order_by(FileIntegrityEvent.detected_at.desc())
            .limit(MAX_TABLE_ROWS)
        )
    ).scalars().all()

    alert_filters = [Alert.triggered_at >= range_start, Alert.triggered_at < range_end]
    if server_id:
        alert_filters.append(Alert.server_id == server_id)
    alert_count = (await db.execute(select(func.count()).select_from(Alert).where(*alert_filters))).scalar_one()
    alerts = (
        await db.execute(select(Alert).where(*alert_filters).order_by(Alert.triggered_at.desc()).limit(MAX_TABLE_ROWS))
    ).scalars().all()

    pdf_bytes = _render_pdf(
        generated_by=user.display_name or user.email,
        range_start=parsed_start,
        range_end=parsed_end,
        scope_label=server.name if server else "All servers",
        server_count=len(servers),
        total_checks=total_checks,
        uptime_pct=uptime_pct,
        incident_count=incident_count,
        incidents=incidents,
        security_event_count=security_event_count,
        security_events=security_events,
        failed_login_count=failed_login_count,
        failed_logins=failed_logins,
        file_event_count=file_event_count,
        unapproved_count=unapproved_count,
        unapproved_file_events=unapproved_file_events,
        alert_count=alert_count,
        alerts=alerts,
    )

    filename = f"security-report-{parsed_start.isoformat()}_{parsed_end.isoformat()}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_pdf(
    *,
    generated_by: str,
    range_start: date,
    range_end: date,
    scope_label: str,
    server_count: int,
    total_checks: int,
    uptime_pct: float | None,
    incident_count: int,
    incidents: list[DowntimeIncident],
    security_event_count: int,
    security_events: list[SecurityEvent],
    failed_login_count: int,
    failed_logins: list[LoginEvent],
    file_event_count: int,
    unapproved_count: int,
    unapproved_file_events: list[FileIntegrityEvent],
    alert_count: int,
    alerts: list[Alert],
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        title="Server Security Center Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=4)
    meta_style = ParagraphStyle("ReportMeta", parent=styles["Normal"], textColor=colors.HexColor("#555555"), fontSize=9)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=18, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"))
    body = styles["Normal"]
    note_style = ParagraphStyle("Note", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#777777"))

    header_bg = colors.HexColor("#1a1a2e")
    stripe_bg = colors.HexColor("#f4f4f8")
    grid_color = colors.HexColor("#dddddd")

    def table_style(n_rows: int) -> TableStyle:
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, grid_color),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]
        for i in range(1, n_rows):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), stripe_bg))
        return TableStyle(cmds)

    elements = []
    elements.append(Paragraph("Server Security Center", title_style))
    elements.append(Paragraph("Security &amp; Uptime Report", ParagraphStyle("Subtitle", parent=styles["Heading3"], textColor=colors.HexColor("#444444"), spaceAfter=10)))
    elements.append(
        Paragraph(
            f"Scope: {scope_label} &nbsp;|&nbsp; Period: {range_start.isoformat()} to {range_end.isoformat()} &nbsp;|&nbsp; "
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by {generated_by}",
            meta_style,
        )
    )
    elements.append(Spacer(1, 10))

    summary_rows = [
        ["Metric", "Value"],
        ["Servers in scope", str(server_count)],
        ["Uptime checks recorded", str(total_checks)],
        ["Uptime", f"{uptime_pct:.2f}%" if uptime_pct is not None else "No data"],
        ["Downtime incidents", str(incident_count)],
        ["Security events", str(security_event_count)],
        ["Failed login attempts", str(failed_login_count)],
        ["Unapproved file changes", f"{unapproved_count} of {file_event_count} total"],
        ["Alerts triggered", str(alert_count)],
    ]
    t = Table(summary_rows, colWidths=[2.8 * inch, 3.6 * inch])
    t.setStyle(table_style(len(summary_rows)))
    elements.append(t)

    def add_table(
        heading: str, header: list[str], rows: list[list[str]], total: int, col_widths: list[float], empty_msg: str
    ) -> None:
        elements.append(Paragraph(heading, h2))
        if not rows:
            elements.append(Paragraph(empty_msg, body))
            return
        data = [header] + rows
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(table_style(len(data)))
        elements.append(tbl)
        if total > len(rows):
            elements.append(Spacer(1, 4))
            elements.append(Paragraph(f"Showing {len(rows)} most recent of {total} total. See the dashboard for the full list.", note_style))

    add_table(
        "Downtime Incidents",
        ["Target", "Started", "Resolved", "Cause"],
        [
            [
                f"{i.target_type.value} {str(i.target_id)[:8]}",
                i.started_at.strftime("%Y-%m-%d %H:%M"),
                i.resolved_at.strftime("%Y-%m-%d %H:%M") if i.resolved_at else "Ongoing",
                i.cause.value.replace("_", " "),
            ]
            for i in incidents
        ],
        incident_count,
        [1.6 * inch, 1.5 * inch, 1.5 * inch, 1.8 * inch],
        "No downtime incidents in this period.",
    )

    add_table(
        "Security Events",
        ["Server", "Type", "Severity", "Occurred", "Source IP"],
        [
            [
                e.server.name if e.server else str(e.server_id)[:8],
                e.event_type,
                e.severity.value,
                e.occurred_at.strftime("%Y-%m-%d %H:%M"),
                e.source_ip or "—",
            ]
            for e in security_events
        ],
        security_event_count,
        [1.3 * inch, 1.5 * inch, 0.9 * inch, 1.4 * inch, 1.3 * inch],
        "No security events in this period.",
    )

    add_table(
        "Failed Login Attempts",
        ["Server", "Account", "Source IP", "Occurred"],
        [
            [
                e.server.name if e.server else str(e.server_id)[:8],
                e.account or "—",
                e.source_ip or "—",
                e.occurred_at.strftime("%Y-%m-%d %H:%M"),
            ]
            for e in failed_logins
        ],
        failed_login_count,
        [1.6 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch],
        "No failed login attempts in this period.",
    )

    add_table(
        "Unapproved File Changes",
        ["Server", "File", "Change", "Detected"],
        [
            [
                e.server.name if e.server else str(e.server_id)[:8],
                e.file_path,
                e.change_type,
                e.detected_at.strftime("%Y-%m-%d %H:%M"),
            ]
            for e in unapproved_file_events
        ],
        unapproved_count,
        [1.2 * inch, 2.8 * inch, 1.0 * inch, 1.4 * inch],
        "No unapproved file changes in this period.",
    )

    add_table(
        "Alerts",
        ["Title", "Severity", "Status", "Triggered"],
        [[a.title, a.severity.value, a.status.value, a.triggered_at.strftime("%Y-%m-%d %H:%M")] for a in alerts],
        alert_count,
        [3.0 * inch, 1.0 * inch, 1.1 * inch, 1.3 * inch],
        "No alerts in this period.",
    )

    doc.build(elements)
    return buf.getvalue()
