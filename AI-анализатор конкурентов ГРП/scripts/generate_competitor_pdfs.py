from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

COMPETITORS = [
    {
        "file": "01_halliburton.pdf",
        "name": "Halliburton",
        "position": "Интегрированные услуги и оборудование ГРП с упором на электрификацию, автоматизацию и контроль операции в реальном времени.",
        "facts": [
            "ZEUS - интегрированная электрическая площадка ГРП; заявлены снижение выбросов и затрат на топливо.",
            "Электрическая насосная установка ZEUS имеет заявленную мощность 5 000 hydraulic horsepower.",
            "OCTIV обеспечивает автоматизацию ГРП, цифровые операции и удалённое подключение.",
            "Официальный кейс 2025 года сообщает о 17% росте эффективности стадий при первичном внедрении Octiv Auto Frac у Coterra.",
        ],
        "questions": [
            "Насколько конкретно раскрыты измеримые показатели оборудования?",
            "Как визуально доказаны безопасность, надёжность и цифровизация?",
            "Какие идеи можно перенести в Pulat GRP Expert без копирования бренда?",
        ],
        "sources": [
            "https://www.halliburton.com/en/completions/stimulation/hydraulic-fracturing",
            "https://www.halliburton.com/en/completions/stimulation/hydraulic-fracturing/zeus-fracturing-services",
            "https://www.halliburton.com/en/products/octiv-digital-fracturing-services",
        ],
    },
    {
        "file": "02_liberty_energy.pdf",
        "name": "Liberty Energy",
        "position": "Североамериканский поставщик completion-услуг, оборудования и инфраструктуры с акцентом на низкие выбросы и собственные digi-технологии.",
        "facts": [
            "Официальная страница позиционирует все новые флоты Liberty, построенные с 2013 года, как low-emission.",
            "Подразделение LAET проектирует и производит оборудование для ГРП, ГИС и логистики песка.",
            "В портфеле заявлены электрические флоты digiFrac и гибридные газовые флоты digiPrime.",
            "Компания публикует образовательные материалы по чистому давлению, реологии и лабораторному контролю жидкостей ГРП.",
        ],
        "questions": [
            "Как образовательный контент усиливает доверие к коммерческим услугам?",
            "Какие цифры подтверждают экологические и операционные заявления?",
            "Насколько понятен путь пользователя от технологии к контакту со специалистом?",
        ],
        "sources": [
            "https://libertyenergy.com/completion-services/frac/",
            "https://libertyenergy.com/",
            "https://libertyenergy.com/resource-library/frac-viscometers/",
        ],
    },
    {
        "file": "03_jereh.pdf",
        "name": "Jereh Group",
        "position": "Производитель комплектного нефтесервисного оборудования, включая электрические и турбинные решения для ГРП.",
        "facts": [
            "Официальная страница называет Jereh первым китайским поставщиком полного комплекта электрического оборудования ГРП для Северной Америки.",
            "В портфеле представлены Direct Drive Turbine Frac и Electric Frac.",
            "Для IntelliFrac заявлена электрическая установка мощностью 7 000 hp.",
            "Для турбинного насосного агрегата заявлены двигатель 5 600 hp и плунжерный насос 5 000 hhp.",
        ],
        "questions": [
            "Хватает ли на сайте спецификаций для инженерного сравнения?",
            "Как показаны компоновка, занимаемая площадь и HSE-преимущества?",
            "Какие параметры полезно автоматически извлекать из паспортов оборудования?",
        ],
        "sources": [
            "https://www.jereh.com/en/business-area/oilfield-equipment",
            "https://www.jereh.com/en/news/news-detail-616144.htm",
            "https://www.jereh.com/en/news/news-detail-614854.htm",
        ],
    },
    {
        "file": "04_slb.pdf",
        "name": "SLB",
        "position": "Глобальный поставщик технологий заканчивания и многостадийного ГРП с сильным инженерным и цифровым контуром.",
        "facts": [
            "SLB описывает решения многостадийного ГРП для плотных песчаников, сланцев и других нетрадиционных коллекторов.",
            "Позиционирование включает создание проводящих трещин с контролем рисков frac hit, водоносных и газоносных интервалов.",
            "В официальной библиотеке представлены материалы по моделированию гидравлических трещин.",
            "Портфель сочетает сервис, инженерное проектирование и техническую базу знаний.",
        ],
        "questions": [
            "Насколько понятно связаны моделирование, дизайн и полевая реализация?",
            "Какие доказательства эффективности доступны без запроса коммерческого предложения?",
            "Как подать сложную инженерию простым языком, не теряя точности?",
        ],
        "sources": [
            "https://www.slb.com/products-and-services/innovating-in-oil-and-gas/completions/stimulation/fracturing-services",
            "https://www.slb.com/resource-library/blogs/di/modeling-hydraulic-fractures",
            "https://glossary.slb.com/terms/h/hydraulic_fracturing",
        ],
    },
]


def bullets(items: list[str], style: ParagraphStyle) -> list[Paragraph]:
    return [Paragraph(f"• {item}", style) for item in items]


def build_pdf(item: dict[str, object]) -> None:
    target = OUT / str(item["file"])
    doc = SimpleDocTemplate(
        str(target), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=16 * mm,
        title=f"Карточка конкурента: {item['name']}", author="Pulat",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleRu", parent=styles["Title"], fontName="DejaVuBold", fontSize=19, leading=24, textColor=colors.HexColor("#111827"), alignment=TA_CENTER, spaceAfter=10)
    h2 = ParagraphStyle("H2Ru", parent=styles["Heading2"], fontName="DejaVuBold", fontSize=13, leading=17, textColor=colors.HexColor("#111827"), spaceBefore=9, spaceAfter=6)
    body = ParagraphStyle("BodyRu", parent=styles["BodyText"], fontName="DejaVu", fontSize=9.7, leading=14, textColor=colors.HexColor("#28313D"), spaceAfter=4)
    small = ParagraphStyle("SmallRu", parent=body, fontSize=7.7, leading=10, textColor=colors.HexColor("#5D6773"))
    story = [
        Paragraph("PULAT GRP COMPETITOR AI", small),
        Paragraph(f"Карточка конкурента: {item['name']}", title),
        Table(
            [
                [Paragraph("Ниша", body), Paragraph("Оборудование и услуги гидроразрыва пласта", body)],
                [Paragraph("Дата", body), Paragraph("20.08.2026", body)],
            ],
            colWidths=[35 * mm, 120 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF1F4")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CED6")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DDE3")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Spacer(1, 5 * mm),
        Paragraph("Позиционирование", h2),
        Paragraph(str(item["position"]), body),
        Paragraph("Подтверждённые факты", h2),
        *bullets(item["facts"], body),
        Paragraph("Что должен проверить AI-анализатор", h2),
        *bullets(item["questions"], body),
        Paragraph("Официальные источники", h2),
        *[Paragraph(f'<link href="{url}" color="#245AA5">{url}</link>', small) for url in item["sources"]],
        Spacer(1, 5 * mm),
        Paragraph("Учебная аналитическая карточка. Это не коммерческий рейтинг. Факты зафиксированы по официальным страницам компаний; оценки должен сформировать анализатор.", small),
    ]
    doc.build(story)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("DejaVu", FONT))
    pdfmetrics.registerFont(TTFont("DejaVuBold", FONT_BOLD))
    for competitor in COMPETITORS:
        build_pdf(competitor)
        print(competitor["file"])


if __name__ == "__main__":
    main()
