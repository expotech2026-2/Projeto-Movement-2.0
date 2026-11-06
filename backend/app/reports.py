"""Relatório PDF com unidades, salas, inventário, condições atuais e médias mensais."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Principal
from app.catalog import catalog_metadata
from app.dependencies import CurrentUser, Db
from app.models import AirConditioner, CatalogModel, Device, Room, SensorReading, Unit
from app.repository import PostgresTelemetryRepository
from app.retention import monthly_history

LOGO = Path(__file__).resolve().parent / "assets" / "logo.png"
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
KINDS = {
    "split": "Split",
    "janela": "Janela",
    "cassete": "Cassete",
    "piso_teto": "Piso-teto",
    "portatil": "Portátil",
    "vrf": "VRF / VRV",
}
STATUS = {"ativo": "Em operação", "manutencao": "Em manutenção", "inativo": "Inativo"}
ROLES = {"admin": "Administrador", "professor": "Professor"}
MONTHS = (
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro"
).split()

INK = colors.HexColor("#1e2330")
ACCENT = colors.HexColor("#7e22ce")
MUTED = colors.HexColor("#5b6472")
ZEBRA = colors.HexColor("#f4f5f8")
RULE = colors.HexColor("#d9dce3")
SOFT = colors.HexColor("#f3e8ff")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


def style(name: str, **values) -> ParagraphStyle:
    base = {"fontName": "Helvetica", "fontSize": 9, "leading": 12, "textColor": INK}
    return ParagraphStyle(name, **{**base, **values})


TITLE = style("title", fontName="Helvetica-Bold", fontSize=20, leading=24)
META = style("meta", fontSize=9, leading=13, textColor=MUTED)
H2 = style("h2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=ACCENT)
H3 = style("h3", fontName="Helvetica-Bold", fontSize=11, leading=14)
LABEL = style("label", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=MUTED)
BODY = style("body")
CELL = style("cell", fontSize=8, leading=10)
HEAD = style("head", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white)
KPI = style("kpi", fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=ACCENT)
NOTE = style("note", fontSize=7.5, leading=10, textColor=MUTED)


def number(value, decimals: int = 1) -> str:
    if value is None:
        return "—"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def local_time(value: datetime) -> str:
    return value.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M")


def text(value: str) -> str:
    return escape(value or "")


def count(value: int, singular: str, plural: str) -> str:
    return f"{number(value, 0)} {singular if value == 1 else plural}"


@dataclass
class RoomReport:
    room: Room
    appliances: list[AirConditioner]
    energy: dict = field(default_factory=dict)
    latest: SensorReading | None = None
    monthly: list[dict] = field(default_factory=list)
    has_device: bool = False


def room_report(session: Session, room: Room) -> RoomReport:
    appliances = session.scalars(
        select(AirConditioner)
        .where(AirConditioner.room_id == room.id)
        .order_by(AirConditioner.name)
    ).all()
    energy = {}
    for appliance in appliances:
        if appliance.brand and appliance.model:
            energy[appliance.id] = session.scalar(
                select(CatalogModel)
                .where(
                    CatalogModel.brand == appliance.brand.strip().upper(),
                    func.upper(CatalogModel.model) == appliance.model.strip().upper(),
                )
                .limit(1)
            )
    return RoomReport(
        room=room,
        appliances=list(appliances),
        energy=energy,
        latest=PostgresTelemetryRepository(session).latest(room.id),
        monthly=monthly_history(session, room.id),
        has_device=session.scalar(select(Device.id).where(Device.room_id == room.id)) is not None,
    )


def collect(session: Session, unit_id: str | None, room_id: str | None):
    if room_id:
        room = session.get(Room, room_id)
        if room is None:
            raise HTTPException(404, "Sala não encontrada")
        unit = session.get(Unit, room.unit_id)
        return [(unit, [room_report(session, room)])], f"Sala {room.name} · {unit.name}"
    if unit_id:
        units = [session.get(Unit, unit_id)]
        if units[0] is None:
            raise HTTPException(404, "Unidade não encontrada")
        scope = f"Unidade {units[0].name}"
    else:
        units = session.scalars(select(Unit).order_by(Unit.name)).all()
        scope = "Todas as unidades"
    groups = []
    for unit in units:
        rooms = session.scalars(
            select(Room).where(Room.unit_id == unit.id).order_by(Room.name, Room.id)
        ).all()
        groups.append((unit, [room_report(session, room) for room in rooms]))
    return groups, scope


def grid(rows: list[list], widths: list[float], align_right: tuple[int, ...] = ()) -> Table:
    data = [[Paragraph(text(str(cell)), HEAD) for cell in rows[0]]]
    data += [[Paragraph(text(str(cell)), CELL) for cell in row] for row in rows[1:]]
    table = Table(data, colWidths=widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
    ]
    commands += [("BACKGROUND", (0, i), (-1, i), ZEBRA) for i in range(2, len(data), 2)]
    commands += [("ALIGN", (c, 1), (c, -1), "RIGHT") for c in align_right]
    table.setStyle(TableStyle(commands))
    return table


def widths(*fractions: float) -> list[float]:
    return [CONTENT_WIDTH * fraction / sum(fractions) for fraction in fractions]


def capacity_of(rooms: list[RoomReport]) -> int:
    return sum(item.capacity_btu for report in rooms for item in report.appliances)


def summary(groups) -> list:
    rooms = [report for _, reports in groups for report in reports]
    appliances = sum(len(report.appliances) for report in rooms)
    kpis = [
        ("Unidades", number(len(groups), 0)),
        ("Salas", number(len(rooms), 0)),
        ("Aparelhos", number(appliances, 0)),
        ("Capacidade instalada", f"{number(capacity_of(rooms), 0)} BTU/h"),
    ]
    cells = [[Paragraph(value, KPI) for _, value in kpis], [Paragraph(k, LABEL) for k, _ in kpis]]
    table = Table(cells, colWidths=[CONTENT_WIDTH / 4] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("LINEAFTER", (0, 0), (-2, -1), 0.6, colors.white),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    rows = [["Unidade", "Salas", "Aparelhos", "BTU/h instalados", "Com sensor", "Em manutenção"]]
    for unit, reports in groups:
        rows.append(
            [
                unit.name,
                number(len(reports), 0),
                number(sum(len(r.appliances) for r in reports), 0),
                number(capacity_of(reports), 0),
                number(sum(r.has_device for r in reports), 0),
                number(sum(a.status == "manutencao" for r in reports for a in r.appliances), 0),
            ]
        )
    return [
        table,
        Spacer(1, 6 * mm),
        Paragraph("Resumo por unidade", H3),
        Spacer(1, 2 * mm),
        grid(rows, widths(3.2, 1, 1.2, 1.6, 1.2, 1.4), (1, 2, 3, 4, 5)),
    ]


def conditions(report: RoomReport, now: datetime, stale_after: int) -> list:
    reading = report.latest
    if reading is None:
        detail = "sensor cadastrado" if report.has_device else "nenhum sensor cadastrado"
        return [Paragraph(f"Sem leituras nos últimos 30 dias ({detail}).", META)]
    age = (now - reading.measured_at).total_seconds()
    rows = [
        ["Última leitura", "Temp. interna", "Temp. externa", "Umidade int.", "Ocupação", "A/C"],
        [
            local_time(reading.measured_at)
            + (" (sem leitura recente)" if age > stale_after else ""),
            f"{number(reading.temp_inside)} °C",
            f"{number(reading.temp_outside)} °C",
            f"{number(reading.humidity_inside)}%",
            count(reading.occupancy, "pessoa", "pessoas"),
            "Ligado" if reading.ac_on else "Desligado",
        ],
    ]
    return [grid(rows, widths(2.6, 1.2, 1.2, 1.2, 1.2, 1))]


def inventory(report: RoomReport) -> list:
    if not report.appliances:
        return [Paragraph("Nenhum aparelho cadastrado nesta sala.", META)]
    rows = [["Aparelho", "Tipo", "Marca / modelo", "BTU/h", "Tecnologia", "Inmetro", "Situação"]]
    for item in report.appliances:
        catalog = report.energy.get(item.id)
        rows.append(
            [
                item.name,
                KINDS.get(item.kind, item.kind),
                " · ".join(filter(None, [item.brand, item.model])) or "Não informado",
                number(item.capacity_btu, 0),
                "Inverter" if item.inverter else "Convencional",
                f"Classe {catalog.energy_class} · Reg. {catalog.registration}" if catalog else "—",
                STATUS.get(item.status, item.status),
            ]
        )
    return [grid(rows, widths(1.5, 0.9, 2.1, 0.9, 1.35, 1.6, 1.25), (3,))]


def monthly(report: RoomReport) -> list:
    if not report.monthly:
        return [Paragraph("Ainda não há médias mensais para esta sala.", META)]
    rows = [["Mês", "Temp. int.", "Temp. ext.", "Umid. int.", "Ocupação", "A/C ligado", "Amostras"]]
    for item in report.monthly:
        month = item["month"]
        rows.append(
            [
                f"{MONTHS[month.month - 1]}/{month.year}"
                + ("" if item["finalized"] else " (parcial)"),
                f"{number(item['avg_temp_inside'])} °C",
                f"{number(item['avg_temp_outside'])} °C",
                f"{number(item['avg_humidity_inside'])}%",
                number(item["avg_occupancy"]),
                f"{number(item['ac_on_percent'])}%",
                number(item["sample_count"], 0),
            ]
        )
    return [grid(rows, widths(1.8, 1, 1, 1, 1, 1, 1), (1, 2, 3, 4, 5, 6))]


def room_section(report: RoomReport, now: datetime, stale_after: int) -> list:
    room = report.room
    details = [f"Capacidade: {count(room.capacity, 'pessoa', 'pessoas')}"]
    if room.location:
        details.insert(0, room.location)
    details.append("Sensor vinculado" if report.has_device else "Sem sensor vinculado")
    heading = [
        Paragraph(text(room.name), H3),
        Paragraph(text(" · ".join(details)), META),
        Spacer(1, 2.5 * mm),
        Paragraph("CONDIÇÕES ATUAIS", LABEL),
        Spacer(1, 1.2 * mm),
        *conditions(report, now, stale_after),
    ]
    return [
        KeepTogether(heading),
        Spacer(1, 3 * mm),
        KeepTogether([Paragraph("INVENTÁRIO", LABEL), Spacer(1, 1.2 * mm), *inventory(report)]),
        Spacer(1, 3 * mm),
        KeepTogether([Paragraph("MÉDIAS MENSAIS", LABEL), Spacer(1, 1.2 * mm), *monthly(report)]),
        Spacer(1, 7 * mm),
    ]


def numbered_canvas(footer: str):
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.decorate(total)
                super().showPage()
            super().save()

        def decorate(self, total: int):
            top = PAGE_HEIGHT - 12 * mm
            if LOGO.exists():
                self.drawImage(str(LOGO), MARGIN, top - 7 * mm, 9 * mm, 9 * mm, mask="auto")
            self.setFillColor(INK)
            self.setFont("Helvetica-Bold", 12)
            self.drawString(MARGIN + 11.5 * mm, top - 2.2 * mm, "movement")
            self.setFont("Helvetica", 6.5)
            self.setFillColor(MUTED)
            self.drawString(MARGIN + 11.5 * mm, top - 5.6 * mm, "GESTÃO DE CLIMATIZAÇÃO")
            self.setFont("Helvetica", 8)
            self.drawRightString(PAGE_WIDTH - MARGIN, top - 3.5 * mm, "Relatório de climatização")
            self.setStrokeColor(RULE)
            self.setLineWidth(0.6)
            self.line(MARGIN, top - 9.5 * mm, PAGE_WIDTH - MARGIN, top - 9.5 * mm)
            self.line(MARGIN, 13 * mm, PAGE_WIDTH - MARGIN, 13 * mm)
            self.setFont("Helvetica", 7.5)
            self.drawString(MARGIN, 8.5 * mm, footer)
            self.drawRightString(
                PAGE_WIDTH - MARGIN, 8.5 * mm, f"Página {self._pageNumber} de {total}"
            )

    return NumberedCanvas


def render(groups, scope: str, principal: Principal, now: datetime, stale_after: int) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=28 * mm,
        bottomMargin=20 * mm,
        title=f"Relatório de climatização — {scope}",
        author=f"Movement · {principal.full_name}",
        subject="Unidades, salas, inventário e médias mensais",
    )
    generated = local_time(now)
    story = [
        Paragraph("Relatório de climatização", TITLE),
        Spacer(1, 2 * mm),
        Paragraph(f"<b>Abrangência:</b> {text(scope)}", META),
        Paragraph(
            f"<b>Gerado em:</b> {generated} (horário de Brasília) por "
            f"{text(principal.full_name)} · {ROLES.get(principal.role, principal.role)}",
            META,
        ),
        Spacer(1, 6 * mm),
        *summary(groups),
        Spacer(1, 8 * mm),
    ]
    for unit, reports in groups:
        story.append(Paragraph("UNIDADE", LABEL))
        story.append(Paragraph(text(unit.name), H2))
        details = [unit.address, count(len(reports), "sala", "salas")]
        story.append(Paragraph(text(" · ".join(filter(None, details))), META))
        story.append(Spacer(1, 4 * mm))
        if not reports:
            story += [Paragraph("Nenhuma sala cadastrada nesta unidade.", META), Spacer(1, 6 * mm)]
        for report in reports:
            story += room_section(report, now, stale_after)
    metadata = catalog_metadata()
    updated = metadata.get("updated_at") or ""
    updated = f"{updated[8:10]}/{updated[5:7]}/{updated[:4]}" if len(updated) == 10 else "—"
    story += [
        Paragraph("Notas", H3),
        Spacer(1, 1.5 * mm),
        Paragraph(
            "Médias por amostra, separadas por sala e mês civil no fuso de Brasília. Meses ainda "
            "dentro da janela de 30 dias aparecem como parciais. “A/C ligado” é o percentual de "
            "amostras com estado ligado informado pelo sensor da sala; não representa consumo "
            "de energia.",
            NOTE,
        ),
        Spacer(1, 1.5 * mm),
        Paragraph(
            "Classe e registro Inmetro conforme a tabela de eficiência energética de "
            "condicionadores de ar do Programa Brasileiro de Etiquetagem, atualizada em "
            f"{updated}. A tabela não substitui a consulta oficial de registros do Inmetro.",
            NOTE,
        ),
    ]
    document.build(story, canvasmaker=numbered_canvas(f"Movement 2.0 · Gerado em {generated}"))
    return buffer.getvalue()


def create_reports_router() -> APIRouter:
    router = APIRouter(prefix="/reports", tags=["Relatórios"])

    @router.get(
        "/pdf",
        response_class=Response,
        responses={200: {"content": {"application/pdf": {}}, "description": "Relatório PDF"}},
    )
    def pdf_report(
        request: Request,
        session: Db,
        principal: CurrentUser,
        unit_id: Annotated[str | None, Query(max_length=64)] = None,
        room_id: Annotated[str | None, Query(max_length=64)] = None,
    ):
        groups, scope = collect(session, unit_id, room_id)
        now = datetime.now(UTC)
        content = render(
            groups, scope, principal, now, request.app.state.settings.stale_after_seconds
        )
        filename = f"movement-relatorio-{now.astimezone(LOCAL_TZ):%Y%m%d-%H%M}.pdf"
        return Response(
            content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
