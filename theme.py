"""Lyrio Dashboard — visual theme injection."""
import streamlit as st


def inject_css() -> None:
    """Inject Lyrio theme CSS. Call once at app startup after st.set_page_config."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@300;500;700&family=JetBrains+Mono:wght@400;700&display=swap');

        /* Hide Streamlit's automatic multipage nav (we use our own radio) */
        [data-testid="stSidebarNav"] { display: none !important; }

        :root {
            --bg: #05070A;
            --card-bg: rgba(13, 17, 23, 0.85);
            --border: rgba(255, 255, 255, 0.06);
            --accent: #6366F1;
            --text-primary: #FFFFFF;
            --text-body: #E6EDF3;
            --text-secondary: #8B949E;
            --hot: #ef4444;
            --warm: #f59e0b;
            --cold: #3b82f6;
            --success: #10b981;
            --bot-seller: #6366F1;
            --bot-buyer: #10b981;
            --bot-lead: #F59E0B;
            --handoff: #8B5CF6;
            --workflow: #EC4899;
        }

        /* Base */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
            color: var(--text-body) !important;
        }

        .stApp {
            background-color: var(--bg) !important;
        }

        .stAppViewContainer, .main {
            background-color: var(--bg) !important;
        }

        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        /* Headings — sentence case */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Space Grotesk', sans-serif !important;
            font-weight: 700 !important;
            color: var(--text-primary) !important;
            letter-spacing: -0.02em !important;
        }

        /* Hide Streamlit chrome */
        #MainMenu, footer, header { visibility: hidden; }
        .stDeployButton { display: none; }

        /* Hide sidebar collapse/expand buttons */
        [data-testid="collapsedControl"] { display: none; }
        button[data-testid="baseButton-header"] { display: none; }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #0A0C10 !important;
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
        }

        /* Radio nav */
        [data-testid="stSidebar"] .stRadio > div {
            gap: 0.25rem;
        }
        [data-testid="stSidebar"] .stRadio label {
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            color: var(--text-body) !important;
            padding: 0.4rem 0.75rem;
            border-radius: 6px;
            cursor: pointer;
        }
        [data-testid="stSidebar"] .stRadio label:has(input:checked) {
            background: rgba(99, 102, 241, 0.15);
            color: var(--accent) !important;
        }

        /* Buttons */
        .stButton > button {
            background-color: var(--accent);
            color: white;
            border: none;
            border-radius: 6px;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            font-size: 0.85rem;
        }
        .stButton > button:hover {
            background-color: #4f46e5;
            border: none;
        }

        /* Chat messages */
        [data-testid="stChatMessage"] {
            background-color: rgba(13, 17, 23, 0.6) !important;
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 0.5rem;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background-color: transparent;
            border-bottom: 1px solid var(--border);
            gap: 0;
        }
        .stTabs [data-baseweb="tab"] {
            font-family: 'Inter', sans-serif;
            font-size: 0.875rem;
            color: var(--text-secondary) !important;
            border-bottom: 2px solid transparent;
            padding: 0.5rem 1rem;
            background: transparent;
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent) !important;
            border-bottom: 2px solid var(--accent);
        }

        /* Dataframe */
        .stDataFrame {
            border: 1px solid var(--border);
            border-radius: 8px;
        }

        /* Selectbox / inputs */
        .stSelectbox > div > div,
        .stMultiSelect > div > div {
            background-color: rgba(13, 17, 23, 0.85) !important;
            border-color: var(--border) !important;
            color: var(--text-body) !important;
        }

        /* Divider */
        hr {
            border-color: var(--border);
            margin: 1rem 0;
        }

        /* Metric card class (used by components.py) */
        .lyrio-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
        }

        .lyrio-stat-value {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 2rem;
            color: var(--text-primary);
            line-height: 1.1;
        }

        .lyrio-stat-label {
            font-family: 'Inter', sans-serif;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }

        .lyrio-mono {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
