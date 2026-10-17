"""PADRÃO CRIACIONAL: Abstract Factory.

Uma fábrica de tema cria uma *família* de produtos compatíveis entre si
(paleta, estilo de botão e estilo de célula do calendário). Trocar a fábrica
troca o visual inteiro sem alterar o código das telas.

Este módulo não importa Qt: apenas gera strings de folha de estilo (QSS).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


# ------------------------------------------------------------ produtos abstratos
class Palette(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    window: str
    surface: str
    text: str
    muted: str
    border: str
    accent: str
    accent_text: str
    today: str
    selected: str
    other_month: str


class ButtonStyle(ABC):
    def __init__(self, palette: Palette):
        self.palette = palette

    @abstractmethod
    def css(self) -> str: ...


class CellStyle(ABC):
    def __init__(self, palette: Palette):
        self.palette = palette

    @abstractmethod
    def css(self, selected: bool, today: bool, other_month: bool) -> str: ...


class ThemeFactory(ABC):
    """Fábrica abstrata: declara a criação de cada produto da família."""

    @abstractmethod
    def create_palette(self) -> Palette: ...

    @abstractmethod
    def create_button_style(self) -> ButtonStyle: ...

    @abstractmethod
    def create_cell_style(self) -> CellStyle: ...


# ----------------------------------------------------------- família "claro"
class LightPalette(Palette):
    name = "claro"
    window = "#f4f6fb"
    surface = "#ffffff"
    text = "#1d2433"
    muted = "#7a8499"
    border = "#d5dbe8"
    accent = "#3b6fd8"
    accent_text = "#ffffff"
    today = "#e3edff"
    selected = "#cfe0ff"
    other_month = "#eef1f7"


class FlatButtonStyle(ButtonStyle):
    def css(self) -> str:
        p = self.palette
        return (
            f"QPushButton, QToolButton {{ background: {p.surface}; color: {p.text};"
            f" border: 1px solid {p.border}; border-radius: 5px; padding: 5px 10px; }}"
            f"QPushButton:hover, QToolButton:hover {{ border-color: {p.accent}; color: {p.accent}; }}"
            f"QPushButton:disabled, QToolButton:disabled {{ color: {p.muted}; }}"
        )


class LightCellStyle(CellStyle):
    def css(self, selected, today, other_month):
        p = self.palette
        background = p.selected if selected else p.today if today else p.other_month if other_month else p.surface
        border = p.accent if selected else p.border
        return f"QFrame#dayCell {{ background: {background}; border: 1px solid {border}; border-radius: 4px; }}"


class LightThemeFactory(ThemeFactory):
    """Fábrica concreta: tema claro."""

    def create_palette(self) -> Palette:
        return LightPalette()

    def create_button_style(self) -> ButtonStyle:
        return FlatButtonStyle(self.create_palette())

    def create_cell_style(self) -> CellStyle:
        return LightCellStyle(self.create_palette())


# ----------------------------------------------------------- família "escuro"
class DarkPalette(Palette):
    name = "escuro"
    window = "#161a23"
    surface = "#1f2430"
    text = "#e6e9f2"
    muted = "#8a93a8"
    border = "#343b4d"
    accent = "#6f9bff"
    accent_text = "#0d1220"
    today = "#26324d"
    selected = "#31416b"
    other_month = "#191d27"


class FilledButtonStyle(ButtonStyle):
    def css(self) -> str:
        p = self.palette
        return (
            f"QPushButton, QToolButton {{ background: {p.border}; color: {p.text};"
            f" border: none; border-radius: 3px; padding: 6px 12px; }}"
            f"QPushButton:hover, QToolButton:hover {{ background: {p.accent}; color: {p.accent_text}; }}"
            f"QPushButton:disabled, QToolButton:disabled {{ color: {p.muted}; background: {p.surface}; }}"
        )


class DarkCellStyle(CellStyle):
    def css(self, selected, today, other_month):
        p = self.palette
        background = p.selected if selected else p.today if today else p.other_month if other_month else p.surface
        border = p.accent if selected else p.window
        return f"QFrame#dayCell {{ background: {background}; border: 1px solid {border}; border-radius: 2px; }}"


class DarkThemeFactory(ThemeFactory):
    """Fábrica concreta: tema escuro."""

    def create_palette(self) -> Palette:
        return DarkPalette()

    def create_button_style(self) -> ButtonStyle:
        return FilledButtonStyle(self.create_palette())

    def create_cell_style(self) -> CellStyle:
        return DarkCellStyle(self.create_palette())


THEMES: dict[str, ThemeFactory] = {"claro": LightThemeFactory(), "escuro": DarkThemeFactory()}


def build_stylesheet(factory: ThemeFactory) -> str:
    """Monta a folha de estilo global a partir dos produtos da fábrica."""
    p = factory.create_palette()
    buttons = factory.create_button_style().css()
    return (
        f"QWidget {{ background-color: {p.window}; color: {p.text}; font-size: 13px; }}"
        f"QLabel {{ background: transparent; }}"
        f"QLineEdit, QPlainTextEdit, QComboBox, QDateTimeEdit, QDateEdit, QSpinBox, QTextBrowser,"
        f" QListWidget, QTreeWidget {{ background-color: {p.surface}; border: 1px solid {p.border};"
        f" border-radius: 4px; padding: 3px; }}"
        f"QListWidget::item:selected, QTreeWidget::item:selected {{ background: {p.accent}; color: {p.accent_text}; }}"
        f"QToolBar {{ border: none; spacing: 6px; padding: 4px; }}"
        f"QStatusBar {{ color: {p.muted}; }}"
        f"QMenu {{ background: {p.surface}; border: 1px solid {p.border}; }}"
        f"QMenu::item:selected {{ background: {p.accent}; color: {p.accent_text}; }}"
        + buttons
    )
