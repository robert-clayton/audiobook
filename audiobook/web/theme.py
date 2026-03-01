"""Shared theme constants and CSS for the audiobook web GUI."""
from nicegui import ui

# Color palette
BG = '#0d0f11'
SURFACE = '#151820'
BORDER = '#1e2430'
TEXT = '#c8ccd4'
TEXT_DIM = '#6b7280'
ACCENT = '#e8a027'      # amber/orange — primary actions
SUCCESS = '#3ddc84'
ERROR = '#ff4444'
INFO = '#4fc3f7'
WARNING = '#f59e0b'

STATUS_DOT = {
    'done': SUCCESS,
    'pending': INFO,
    'failed': ERROR,
    'processing': ACCENT,
}


def apply_theme():
    """Inject Google Font, global CSS overrides, and Quasar dark theming."""
    ui.dark_mode(True)
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?'
        'family=JetBrains+Mono:wght@300;400;500;600;700&display=swap" rel="stylesheet">'
    )
    ui.add_css(f'''
        /* Global reset */
        body, .q-page {{ background: {BG} !important; }}
        * {{ font-family: 'JetBrains Mono', monospace !important; }}
        .material-icons, .q-icon, [class*="notranslate"] {{ font-family: 'Material Icons' !important; }}

        /* Cards / surfaces */
        .q-card, .q-table {{
            background: {SURFACE} !important;
            border: 1px solid {BORDER} !important;
            border-radius: 2px !important;
            box-shadow: none !important;
        }}

        /* Table overrides — dense rows */
        .q-table th {{
            font-size: 11px !important; text-transform: uppercase !important;
            letter-spacing: 0.08em !important; color: {TEXT_DIM} !important;
            border-bottom: 1px solid {BORDER} !important;
        }}
        .q-table td {{
            font-size: 13px !important; color: {TEXT} !important;
            border-bottom: 1px solid {BORDER} !important;
            padding: 6px 12px !important;
        }}
        .q-table tbody tr:hover td {{ background: rgba(232,160,39,0.06) !important; }}

        /* Buttons */
        .q-btn {{ border-radius: 2px !important; letter-spacing: 0.04em !important; }}

        /* Log panel — terminal look */
        .nicegui-log {{
            background: {BG} !important;
            border: 1px solid {BORDER} !important;
            border-radius: 2px !important;
            font-size: 12px !important;
            color: {TEXT_DIM} !important;
        }}

        /* Badge overrides */
        .q-badge {{ border-radius: 2px !important; font-size: 11px !important; }}

        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-track {{ background: {BG}; }}
        ::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 2px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: {TEXT_DIM}; }}

        /* Dialog overrides */
        .q-dialog__inner > .q-card {{
            border: 1px solid {BORDER} !important;
        }}
    ''')
