"""UI styles module - exports combined CSS."""

from ui.styles.variables import CSS_VARIABLES
from ui.styles.base import CSS_BASE
from ui.styles.title_bar import CSS_TITLE_BAR
from ui.styles.center_stage import CSS_CENTER_STAGE
from ui.styles.input_bar import CSS_INPUT_BAR
from ui.styles.side_panels import CSS_SIDE_PANELS
from ui.styles.game_components import CSS_GAME_COMPONENTS
from ui.styles.ui_elements import CSS_UI_ELEMENTS

RETRO_CSS = (
    CSS_VARIABLES
    + CSS_BASE
    + CSS_TITLE_BAR
    + CSS_CENTER_STAGE
    + CSS_INPUT_BAR
    + CSS_SIDE_PANELS
    + CSS_GAME_COMPONENTS
    + CSS_UI_ELEMENTS
)

