import streamlit as st
import logging
from typing import Dict
import nest_asyncio
from datetime import datetime
import pytz
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

nest_asyncio.apply()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Jobtimizer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import services and models with error handling
try:
    from services.sync_wrapper import sync_service
    from models import JobAdRequest, FeedbackRequest, CompanyInfo
    from utils.auth import get_current_user, is_authenticated, login_user, logout_user
except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Please check that all required files are in the correct directories")
    st.stop()

# Initialize service
@st.cache_resource
def initialize_service():
    """Initialize the sync service"""
    success = sync_service.initialize()
    if success:
        logger.info("Jobtimizer service initialized successfully")
        return sync_service
    else:
        st.error("Failed to connect to database")
        st.stop()
        return None


service = initialize_service()


def initialize_session_state():
    """Initialize session state variables"""
    if 'current_ad' not in st.session_state:
        st.session_state.current_ad = None
    if 'selected_job_title' not in st.session_state:
        st.session_state.selected_job_title = None
    if 'show_registration' not in st.session_state:
        st.session_state.show_registration = False


# ----------------- UI Functions -----------------

def main():
    # Initialize session state first
    initialize_session_state()
    
    st.title("🎯 JobtimizerAI")
    st.markdown("### Deutsche Stellenanzeigen Generator mit KI")

    # Sidebar for authentication
    with st.sidebar:
        if not is_authenticated():
            authentication_section()
        else:
            user_dashboard()

    # Main content
    if is_authenticated():
        job_ad_interface()
    else:
        welcome_section()


def welcome_section():
    st.markdown("""
    ## Willkommen bei Jobtimizer von Westpress!

    **Erstellen Sie professionelle deutsche Stellenanzeigen in Sekunden:**  

    ✨ **KI-gestützte Generation** basierend auf ESCO-Berufsdaten  
    🎯 **Personalisierte Anzeigen** für Ihr Unternehmen  
    🔄 **Intelligentes Feedback** für kontinuierliche Verbesserung  
    📊 **Konsistente Struktur** mit flexiblen Anpassungen  

    **👈 Melden Sie sich links an, um zu beginnen!**
    """)


# ----------------- Authentication -----------------

def authentication_section():
    if st.session_state.show_registration:
        registration_form()
    else:
        login_form()


def login_form():
    st.header("🔐 Anmeldung")
    with st.form("login_form"):
        username = st.text_input("E-Mail", placeholder="ihre.email@unternehmen.de")
        password = st.text_input("Passwort", type="password")

        col1, col2 = st.columns(2)
        with col1:
            login_button = st.form_submit_button("Anmelden")
        with col2:
            register_button = st.form_submit_button("Registrieren")

        if login_button and username and password:
            try:
                user = service.authenticate_user(username, password)
                if user:
                    login_user(user)
                    st.success("✅ Erfolgreich angemeldet!")
                    st.rerun()
                else:
                    st.error("❌ Ungültige Anmeldedaten")
            except Exception as e:
                st.error(f"❌ Anmeldung fehlgeschlagen: {e}")
                logger.error(f"Login error: {e}")

        if register_button:
            st.session_state.show_registration = True
            st.rerun()


def registration_form():
    st.header("📝 Registrierung")
    with st.form("registration_form"):
        username = st.text_input("E-Mail*")
        password = st.text_input("Passwort*", type="password")
        company_name = st.text_input("Unternehmensname*")
        industry = st.text_input("Branche*")
        mission = st.text_area("Mission/Vision")
        location = st.text_input("Standort")
        culture_values = st.text_area("Unternehmenskultur & Werte (kommagetrennt)")
        company_size = st.selectbox("Unternehmensgröße", ["<10", "10-50", "50-200", "200-1000", ">1000"])

        col1, col2 = st.columns(2)
        with col1:
            register_button = st.form_submit_button("Registrieren")
        with col2:
            back_button = st.form_submit_button("Zurück zur Anmeldung")

        if register_button:
            if not all([username, password, company_name, industry]):
                st.error("❌ Pflichtfelder ausfüllen")
                return
            if len(password) < 6:
                st.error("❌ Passwort muss mindestens 6 Zeichen haben")
                return

            culture_list = [c.strip() for c in culture_values.split(',')] if culture_values else []

            company_info = CompanyInfo(
                company_name=company_name,
                industry=industry,
                mission=mission or None,
                culture=culture_list,
                values=culture_list,
                size=company_size,
                location=location or None
            )

            registration_data = {
                "username": username,
                "password": password,
                "company_info": company_info.model_dump()
            }

            try:
                service.register_user(registration_data)
                st.success("✅ Registrierung erfolgreich! Sie können sich jetzt anmelden.")
                st.session_state.show_registration = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ Registrierung fehlgeschlagen: {e}")
                logger.error(f"Registration error: {e}")

        if back_button:
            st.session_state.show_registration = False
            st.rerun()


def user_dashboard():
    user = get_current_user()
    st.header(f"👋 Willkommen {user['username']}!")
    st.write(f"**{user['company_info']['company_name']}**")

    # Add tabs for navigation
    tab1, tab2 = st.tabs(["🏠 Dashboard", "⚙️ Einstellungen"])

    with tab1:
        if st.button("🚪 Abmelden"):
            logout_user()
            st.rerun()

    with tab2:
        user_profile_settings()


def user_profile_settings():
    """Enhanced user profile settings interface with new tone options"""
    user = get_current_user()
    st.header("⚙️ Profil Einstellungen")

    current_prefs = user.get('preferences', {})

    with st.form("preferences_form"):
        st.subheader("Stellenanzeigen Einstellungen")

        col1, col2 = st.columns(2)

        with col1:
            # Updated tone options
            tone_options = ["sie", "du", "ohne"]
            current_tone = current_prefs.get("tone", "sie")
            if current_tone not in tone_options:
                current_tone = "sie"

            tone = st.selectbox(
                "Anrede-Form",
                options=tone_options,
                index=tone_options.index(current_tone),
                help="Wie sollen Kandidaten angesprochen werden?"
            )

            # NEW: Separate casual tone option
            casual_tone = st.checkbox(
                "Lockerer Ton",
                value=current_prefs.get("casual_tone", False),
                help="Macht die Anzeige lockerer und entspannter (unabhängig von Sie/Du)"
            )

            formality_options = ["formal", "semi_formal", "casual"]
            current_formality = current_prefs.get("formality_level", "formal")
            if current_formality not in formality_options:
                current_formality = "formal"

            formality_level = st.selectbox(
                "Formalitätsstufe",
                options=formality_options,
                index=formality_options.index(current_formality),
                help="Wie formal sollen die Anzeigen sein?"
            )

        with col2:
            focus_options = ["experience", "potential", "skills", "culture,mission,vision"]
            current_focus = current_prefs.get("candidate_focus", "experience")
            if current_focus not in focus_options:
                current_focus = "experience"

            candidate_focus = st.selectbox(
                "Kandidaten-Fokus",
                options=focus_options,
                index=focus_options.index(current_focus),
                help="Worauf soll bei Kandidaten fokussiert werden?"
            )

            # Language style options
            style_options = ["Standard", "Einfacher Deutsch", "Kreativ"]
            current_style = current_prefs.get("language_style", "Standard")

            # Normalize casing if DB stores lowercase values
            style_map = {
                "standard": "Standard",
                "einfacher deutsch": "Einfacher Deutsch",
                "kreativ": "Kreativ"
            }
            current_style = style_map.get(str(current_style).lower(), "Standard")

            language_style = st.selectbox(
                "Sprachstil",
                options=style_options,
                index=style_options.index(current_style),
                help="Sprachlicher Stil der Anzeigen"
            )

        st.markdown("---")
        save_prefs = st.form_submit_button("💾 Einstellungen Speichern", use_container_width=True)

        if save_prefs:
            try:
                new_preferences = {
                    "tone": tone,
                    "casual_tone": casual_tone,  # NEW field
                    "formality_level": formality_level,
                    "candidate_focus": candidate_focus,
                    "language_style": language_style
                }

                success = service.update_user_preferences(user['_id'], new_preferences)

                if success:
                    if 'preferences' not in st.session_state.user:
                        st.session_state.user['preferences'] = {}
                    st.session_state.user['preferences'].update(new_preferences)

                    st.success("✅ Einstellungen erfolgreich gespeichert!")
                else:
                    st.error("❌ Fehler beim Speichern der Einstellungen")

            except Exception as e:
                st.error(f"❌ Fehler beim Speichern: {e}")
                logger.error(f"Preference update error: {e}")

        with st.expander("🔍 Debug: Aktuelle Werte"):
            st.json(current_prefs)


# ----------------- Job Ad Generation -----------------

def fix_job_title_formatting(title: str) -> str:
    """Fix job title formatting - no spaces around / in (m/w/d)"""
    if not title:
        return title
    
    import re
    
    # First, temporarily replace (m/w/d) patterns to protect them
    protected = re.sub(r'\(m\s*/\s*w\s*/\s*d\)', '(m/w/d)', title, flags=re.IGNORECASE)
    
    # Now add spaces around other slashes (but not the ones we just protected)
    # Only add spaces to slashes that are NOT within parentheses containing m, w, d
    parts = []
    i = 0
    while i < len(protected):
        if protected[i:i+7] == '(m/w/d)':
            parts.append('(m/w/d)')
            i += 7
        elif protected[i] == '/':
            parts.append(' / ')
            i += 1
        else:
            parts.append(protected[i])
            i += 1
    
    return ''.join(parts)


def job_ad_interface():
    # Ensure session state is initialized
    initialize_session_state()
    
    user = get_current_user()
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("🎯 Stellenanzeige erstellen")

        # Job title input with suggestions
        st.subheader("Jobtitel eingeben")

        job_title_input = st.text_input(
            "Jobtitel*",
            placeholder="Z.B. Software Engineer, Marketing Manager, ...",
            help="Beginnen Sie zu tippen für Vorschläge aus der ESCO-Datenbank",
            key="job_title_input"
        )

        # Only search if query changed and is long enough - with debouncing
        suggestions = []
        if (job_title_input and 
            len(job_title_input) >= 2 and 
            job_title_input != st.session_state.get('last_search_query', '')):
            
            try:
                with st.spinner("Suche Vorschläge..."):
                    suggestions = service.search_job_titles(job_title_input, limit=6)
                    st.session_state.last_search_query = job_title_input
                    st.session_state.cached_suggestions = suggestions
            except Exception as e:
                st.error(f"Fehler bei der Vorschlagssuche: {e}")
                suggestions = []
        elif job_title_input == st.session_state.get('last_search_query', ''):
            # Use cached results
            suggestions = st.session_state.get('cached_suggestions', [])

        # Display suggestions with fixed formatting
        selected_suggestion = None
        if suggestions:
            st.write("**💡 Vorschläge aus ESCO-Datenbank:**")

            cols = st.columns(2)
            for i, suggestion in enumerate(suggestions):
                col = cols[i % 2]
                with col:
                    # Fix formatting of suggestion title
                    fixed_title = fix_job_title_formatting(suggestion['title'])
                    button_key = f"suggestion_{i}_{hash(fixed_title)}"  # More unique key
                    
                    if st.button(
                            f"🎯 {fixed_title}",
                            key=button_key,
                            help=suggestion['description']
                    ):
                        st.session_state.selected_job_title = fixed_title
                        # Clear search cache to avoid confusion
                        st.session_state.pop('last_search_query', None)
                        st.session_state.pop('cached_suggestions', None)
                        st.rerun()

        # Process the final job title
        if st.session_state.get('selected_job_title'):
            final_job_title = st.session_state.selected_job_title
        else:
            # Clean the input and add (m/w/d) if needed
            clean_input = fix_job_title_formatting(job_title_input) if job_title_input else ""
            if clean_input and not clean_input.endswith("(m/w/d)"):
                final_job_title = f"{clean_input}(m/w/d)"  # No space before (m/w/d)
            else:
                final_job_title = clean_input

        if final_job_title and final_job_title != job_title_input:
            st.info(f"✅ Gewählter Titel: **{final_job_title}**")
            if st.button("🗑️ Auswahl zurücksetzen"):
                st.session_state.pop('selected_job_title', None)
                st.session_state.pop('last_search_query', None) 
                st.session_state.pop('cached_suggestions', None)
                st.rerun()
        base_title = fix_job_title_formatting(job_title_input)

        final_job_title = (
                st.session_state.get('selected_job_title')
                or (base_title + "(m/w/d)" if job_title_input and not job_title_input.endswith("(m/w/d)") else base_title)
        )

        if final_job_title != fix_job_title_formatting(job_title_input) and final_job_title:
            st.info(f"✅ Gewählter Titel: **{final_job_title}**")
            if st.button("🗑️ Auswahl zurücksetzen"):
                if 'selected_job_title' in st.session_state:
                    del st.session_state.selected_job_title
                st.rerun()

        # Seniority Level Selection (Optional)
        seniority_section(final_job_title)

        # Job ad form
        with st.form("job_ad_form"):
            # Get the final title with seniority if selected
            display_title = get_final_job_title_with_seniority(final_job_title)

            st.text_input("Finaler Jobtitel", value=display_title or "", disabled=True)

            additional_context = st.text_area(
                "Zusätzliche Informationen",
                placeholder="Besondere Anforderungen, Benefits, Arbeitsweise..."
            )

            generate_button = st.form_submit_button("✨ Stellenanzeige Generieren")

            if generate_button and final_job_title:
                with st.spinner("🤖 KI erstellt Ihre Stellenanzeige..."):
                    try:
                        search_title = final_job_title.replace("(m/w/d)", "").strip()
                        seniority_level = st.session_state.get('selected_seniority_level')
                        seniority_years = st.session_state.get('selected_seniority_years')

                        request = JobAdRequest(
                            job_title=search_title,
                            additional_context=additional_context,
                            seniority_level=seniority_level,
                            seniority_years=seniority_years,
                        )

                        result = service.generate_job_ad(request, user['_id'])
                        st.session_state.current_ad = result

                        # Clean up session state
                        cleanup_session_state()

                        st.success("✅ Stellenanzeige erstellt!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Fehler beim Erstellen: {e}")
                        logger.error(f"Fehler bei der Stellenanzeigen-Generierung: {e}")

            elif generate_button:
                st.error("❌ Bitte geben Sie einen Jobtitel ein oder wählen Sie einen Vorschlag")

    with col2:
        # Safe check for current_ad
        if st.session_state.get('current_ad') is not None:
            feedback_section()

    # Safe check for current_ad
    if st.session_state.get('current_ad') is not None:
        display_job_ad()


def seniority_section(job_title):
    """Display seniority level selection section - now in German"""
    if not job_title:
        return

    st.subheader("🎖️ Erfahrungsstufe (Optional)")

    # Import the seniority levels
    from models.job_ad import SENIORITY_LEVELS

    # Check if seniority selection is enabled
    show_seniority = st.checkbox("Erfahrungsstufe hinzufügen", key="show_seniority_checkbox")

    if show_seniority:
        st.write("**Wählen Sie die Erfahrungsstufe:**")

        # Create buttons for each seniority level
        cols = st.columns(len(SENIORITY_LEVELS))

        for i, seniority in enumerate(SENIORITY_LEVELS):
            with cols[i]:
                if st.button(
                        f"**{seniority.display_name}**\n({seniority.years})",
                        key=f"seniority_{seniority.level}",
                        help=f"Fügt '{seniority.display_name}' vor dem Jobtitel hinzu"
                ):
                    st.session_state.selected_seniority_level = seniority.level
                    st.session_state.selected_seniority_years = seniority.years
                    st.session_state.selected_seniority_display = seniority.display_name
                    st.rerun()

        # Show selected seniority
        if 'selected_seniority_display' in st.session_state:
            st.success(
                f"✅ Gewählt: **{st.session_state.selected_seniority_display}** ({st.session_state.selected_seniority_years})")

            if st.button("🗑️ Erfahrungsstufe zurücksetzen", key="reset_seniority"):
                st.session_state.pop('selected_seniority_level', None)
                st.session_state.pop('selected_seniority_years', None)
                st.session_state.pop('selected_seniority_display', None)
                st.rerun()
    else:
        # Clear seniority selection if checkbox is unchecked
        if 'selected_seniority_level' in st.session_state:
            st.session_state.pop('selected_seniority_level', None)
            st.session_state.pop('selected_seniority_years', None)
            st.session_state.pop('selected_seniority_display', None)


def get_final_job_title_with_seniority(base_title):
    """Get the final job title with seniority prefix if selected"""
    if not base_title:
        return base_title

    seniority_display = st.session_state.get('selected_seniority_display')

    if seniority_display:
        # Remove (m/w/d) temporarily, add seniority, then add (m/w/d) back
        title_without_suffix = base_title.replace("(m/w/d)", "").strip()
        return f"{seniority_display} {title_without_suffix}(m/w/d)"

    return base_title


def cleanup_session_state():
    """Clean up session state after job ad generation"""
    keys_to_remove = [
        'selected_job_title',
        'selected_seniority_level',
        'selected_seniority_years',
        'selected_seniority_display'
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)


# ----------------- Feedback -----------------

def feedback_section():
    st.header("🔧 Schnelle Anpassungen")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📈 Formeller"):
            apply_feedback(["mehr_formell"], None)
        if st.button("🎯 Mehr Benefits"):
            apply_feedback(["mehr_benefits"], None)
    with col2:
        if st.button("😊 Lockerer"):
            apply_feedback(["lockerer"], None)
        if st.button("🏢 Mehr Kultur"):
            apply_feedback(["mehr_unternehmenskultur"], None)

    custom_feedback = st.text_area("💬 Individuelle Anpassungen")
    if st.button("🔄 Anpassung anwenden") and custom_feedback:
        apply_feedback(None, custom_feedback)


def apply_feedback(button_clicks, text_feedback):
    try:
        with st.spinner("🤖 Stellenanzeige wird verfeinert..."):
            feedback_request = FeedbackRequest(
                feedback_type="button_click" if button_clicks else "text_feedback",
                button_clicks=button_clicks,
                text_feedback=text_feedback
            )
            refined_ad = service.refine_job_ad_with_feedback(
                st.session_state.current_ad.job_ad,
                feedback_request,
                get_current_user()['_id']
            )
            st.session_state.current_ad.job_ad = refined_ad
            st.success("✅ Anpassung angewendet!")
            st.rerun()
    except Exception as e:
        st.error(f"❌ Fehler beim Verfeinern: {e}")


# ----------------- Display Job Ad -----------------

def display_job_ad():
    st.header("📄 Ihre Stellenanzeige")
    user = get_current_user()
    
    # Get Germany timezone - fixed
    germany_tz = pytz.timezone('Europe/Berlin')
    
    # Ensure the timestamp is timezone-aware
    timestamp = st.session_state.current_ad.generation_timestamp
    if timestamp.tzinfo is None:
        # If naive datetime, assume it's UTC
        timestamp = timestamp.replace(tzinfo=pytz.UTC)
    
    # Convert to Germany time
    created_time = timestamp.astimezone(germany_tz)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏢 Unternehmen", user['company_info']['company_name'])
    with col2:
        st.metric("🎯 Position", st.session_state.current_ad.esco_data.name)
    with col3:
        st.metric("⏰ Erstellt", created_time.strftime("%d.%m.%Y %H:%M")) 
    st.markdown("---")
    st.markdown(st.session_state.current_ad.job_ad)
    st.markdown("---")

    edited_ad = st.text_area("📝 Bearbeiten", value=st.session_state.current_ad.job_ad, height=400)
    if edited_ad != st.session_state.current_ad.job_ad:
        if st.button("💾 Änderungen speichern"):
            try:
                feedback_request = FeedbackRequest(
                    feedback_type="manual_edit",
                    manual_changes=edited_ad
                )
                service.refine_job_ad_with_feedback(
                    st.session_state.current_ad.job_ad,
                    feedback_request,
                    user['_id']
                )
                st.session_state.current_ad.job_ad = edited_ad
                st.success("✅ Änderungen gespeichert!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Fehler beim Speichern: {e}")

    # Download button
    job_name_safe = st.session_state.current_ad.esco_data.name.replace(' ', '_').replace('/', '_')
    st.download_button(
        label="📥 Als Markdown herunterladen",
        data=st.session_state.current_ad.job_ad,
        file_name=f"stellenanzeige_{job_name_safe}.md",
        mime="text/markdown"
    )
def initialize_session_state():
    """Initialize session state variables"""
    if 'current_ad' not in st.session_state:
        st.session_state.current_ad = None
    if 'selected_job_title' not in st.session_state:
        st.session_state.selected_job_title = None
    if 'show_registration' not in st.session_state:
        st.session_state.show_registration = False
    # Add caching for suggestions
    if 'last_search_query' not in st.session_state:
        st.session_state.last_search_query = ""
    if 'cached_suggestions' not in st.session_state:
        st.session_state.cached_suggestions = []

# ----------------- Run -----------------

if __name__ == "__main__":
    main()


