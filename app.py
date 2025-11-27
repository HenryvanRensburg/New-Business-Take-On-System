import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date
from fpdf import FPDF # Used for PDF generation
import os # For environment variables

# --- Configuration and Initialization ---

# Load Supabase credentials from environment variables or secrets
# IMPORTANT: For local development, use st.secrets or set OS environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    """Initializes and caches the Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- Utility Functions ---

def fetch_data(table_name: str, columns: str = "*", filters: dict = None) -> pd.DataFrame:
    """Fetches data from a Supabase table."""
    try:
        query = supabase.table(table_name).select(columns)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        response = query.execute()
        
        # Check if the data is a list and convert to DataFrame
        if response.data and isinstance(response.data, list):
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching data from {table_name}: {e}")
        return pd.DataFrame()

def insert_data(table_name: str, data: dict):
    """Inserts a single record into a Supabase table."""
    try:
        supabase.table(table_name).insert(data).execute()
        st.success(f"Successfully added to {table_name}!")
        st.rerun() # Refresh app to see new data
    except Exception as e:
        st.error(f"Error inserting data into {table_name}: {e}")

# --- Authentication ---

def sign_in(email, password):
    """Handles user sign-in via Supabase Auth."""
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            st.session_state['user'] = response.user
            st.session_state['logged_in'] = True
            st.success("Signed in successfully!")
            st.rerun()
        else:
            st.error("Invalid email or password.")
    except Exception as e:
        st.error(f"Sign-in failed: {e}")

def sign_out():
    """Handles user sign-out."""
    try:
        supabase.auth.sign_out()
        st.session_state['user'] = None
        st.session_state['logged_in'] = False
        st.success("Signed out successfully.")
        st.rerun()
    except Exception as e:
        st.error(f"Sign-out failed: {e}")

def login_form():
    """Renders the login form."""
    with st.sidebar:
        st.title("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In")
            if submitted:
                sign_in(email, password)

# --- PDF Generation (Requirement 5 - Reporting) ---

class PDF(FPDF):
    """Custom FPDF class for the progress report."""
    def header(self):
        # FIX: Removed encoding parameter
        self.set_font('Arial', 'B', 15) 
        self.cell(0, 10, 'Pretor Group Take-On Progress Report', 0, 1, 'C')
        self.line(10, 20, 200, 20)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        # FIX: Removed encoding parameter
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 8, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, data: pd.DataFrame, scheme_name: str):
        # FIX: Removed encoding parameter
        self.set_font('Arial', '', 10) 
        
        # --- Defensive Data Preparation (Ensuring all data is string/no NaN) ---
        data = data.copy()
        data['item_description'] = data['item_description'].fillna('N/A').astype(str)
        data['date_completed'] = data['date_completed'].fillna('-').astype(str)
        data['completed_by'] = data['completed_by'].fillna('-').astype(str)
        # ----------------------------------------------------------------------
        
        # Scheme Info
        self.chapter_title(f"Scheme: {scheme_name}")
        
        # Table Header
        # FIX: Removed encoding parameter
        self.set_font('Arial', 'B', 10) 
        col_widths = [100, 30, 30, 30]
        self.cell(col_widths[0], 7, 'Item', 1, 0, 'L')
        self.cell(col_widths[1], 7, 'Status', 1, 0, 'C')
        self.cell(col_widths[2], 7, 'Date', 1, 0, 'C')
        self.cell(col_widths[3], 7, 'Completed By', 1, 1, 'C')
        
        # Table Rows
        # FIX: Removed encoding parameter
        self.set_font('Arial', '', 10) 
        
        for index, row in data.iterrows():
            
            # --- FINAL STRING GUARANTEE (ASCII sanitization to prevent Unicode errors) ---
            item = str(row['item_description']).encode('ascii', errors='ignore').decode('ascii')
            # -------------------------------------------------------------------------
            
            status = "Complete" if row['is_complete'] else "Pending"
            date_str = row['date_completed']
            completed_by = row['completed_by']
            
            # Use multi_cell for wrapping long text
            # Calculate height for multiline cell
            line_height = 6
            item_lines = self.multi_cell(col_widths[0], line_height, item, 0, 'L', 0, dry_run=True, output='LINES')
            
            x = self.get_x()
            y = self.get_y()
            
            # Draw Item cell
            self.multi_cell(col_widths[0], line_height, item, 1, 'L', 0)
            
            # Go back to start x and move down to the cell's max height
            self.set_xy(x + col_widths[0], y)
            
            # Draw Status, Date, and Completed By cells aligned with the item
            cell_height = len(item_lines) * line_height
            
            self.cell(col_widths[1], cell_height, status, 1, 0, 'C')
            self.cell(col_widths[2], cell_height, date_str, 1, 0, 'C')
            self.cell(col_widths[3], cell_height, completed_by, 1, 1, 'C')

def generate_pdf_report(scheme_name: str, progress_data: pd.DataFrame) -> bytes:
    """Generates the weekly progress PDF report."""
    
    # Filter for Pretor Group items only (Requirement 5)
    pretor_data = progress_data[progress_data['type'] == 'Pretor']
    
    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    
    if not pretor_data.empty:
        pdf.chapter_body(pretor_data, scheme_name)
    else:
        pdf.chapter_body(pd.DataFrame({'item_description':['No Pretor Group items found or linked.'], 'is_complete':[False], 'date_completed':['-'], 'completed_by':['-']}), scheme_name)

    pdf_output = pdf.output(dest='S')
    
    # FIX: Check if the output is a string (str) and explicitly convert it to bytes.
    # This ensures st.download_button always receives the required bytes format.
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1', errors='ignore')
    
    # If it's already bytes, return it directly.
    return pdf_output

# --- Application Pages ---

def master_data_page():
    """Handles master data entry for Departments and Checklists (Requirements 1, 2, 3)."""
    st.header("📚 Master Data Management")
    st.markdown("---")
    
    tab_checklist, tab_departments = st.tabs(["Master Checklists", "Pretor Departments"])
    
    # --- Master Checklists Tab (Requirements 1 & 2) ---
    with tab_checklist:
        st.subheader("Add New Checklist Item")
        
        with st.form("new_checklist_item"):
            col1, col2 = st.columns(2)
            
            item_description = st.text_area("Checklist Item Description", placeholder="e.g., Obtain previous year's audited financials")
            
            with col1:
                item_type = st.radio("Item Type", options=["PMA", "Pretor"], horizontal=True, 
                                     help="PMA: Previous Managing Agent items. Pretor: Pretor Group internal items.")
            
            with col2:
                scheme_type = st.radio("Scheme Type", options=["BC", "HOA"], horizontal=True, 
                                       help="BC: Body Corporate. HOA: Home Owners Association.")
            
            if st.form_submit_button("Add Item"):
                if item_description:
                    data = {
                        "item_description": item_description,
                        "type": item_type,
                        "scheme_type": scheme_type
                    }
                    insert_data("master_checklist", data)
                else:
                    st.warning("Please enter an item description.")

        st.subheader("Existing Master Checklists")
        df_checklist = fetch_data("master_checklist")
        
        if not df_checklist.empty:
            df_checklist.rename(columns={'item_description': 'Item', 'type': 'Source', 'scheme_type': 'Scheme Type'}, inplace=True)
            st.dataframe(df_checklist[['Source', 'Scheme Type', 'Item']], use_container_width=True, hide_index=True)
        else:
            st.info("No master checklist items defined yet.")

    # --- Pretor Departments Tab (Requirement 3) ---
    with tab_departments:
        st.subheader("Add New Department Contact")
        
        with st.form("new_department_contact"):
            department_name = st.text_input("Department Name")
            email = st.text_input("Email Address")
            
            if st.form_submit_button("Add Department"):
                if department_name and email:
                    data = {"department_name": department_name, "email": email}
                    insert_data("departments", data)
                else:
                    st.warning("Please fill in both department name and email.")

        st.subheader("Pretor Group Departments")
        df_departments = fetch_data("departments")
        
        if not df_departments.empty:
            df_departments.rename(columns={'department_name': 'Department', 'email': 'Email'}, inplace=True)
            st.table(df_departments[['Department', 'Email']].set_index('Department'))
        else:
            st.info("No department contacts defined yet.")

def new_scheme_page():
    """Handles the creation of a new scheme and initial checklist copy (Requirement 4)."""
    st.header("➕ Create New Scheme")
    st.markdown("---")
    
    # Fetch master checklists for automatic copying
    df_master_checklist = fetch_data("master_checklist")
    
    with st.form("new_scheme_form"):
        st.subheader("Basic Scheme Information")
        scheme_name = st.text_input("Scheme Name *")
        scheme_type = st.radio("Scheme Type *", options=["Body Corporate", "Home Owners Association"], horizontal=True)
        is_bc = scheme_type == "Body Corporate"
        
        col1, col2 = st.columns(2)
        with col1:
            # FIX: Using date.today() for safe initialization
            appointment_date = st.date_input("Appointment Date *", value=date.today())
            financial_year_end = st.date_input("Financial Year End (Date)", value=date.today())
            assigned_portfolio_manager = st.text_input("Assigned Portfolio Manager (Name) *")
            pm_email = st.text_input("PM Email Address *")
            
        with col2:
            number_of_units = st.number_input("Number of Units", min_value=1, step=1)
            management_fees = st.number_input("Management Fees (Excluding VAT)", min_value=0.0)
            initial_request_date = st.date_input("Initial Request for Info Date", value=date.today())
        
        # Statutory Details
        st.subheader("Statutory and Financial Details")
        col3, col4 = st.columns(2)
        with col3:
            registration_label = "SS Number" if is_bc else "CIPC Registration Number"
            registration_number = st.text_input(f"{registration_label} *")
            sars_income_tax_number = st.text_input("SARS Income Tax Number")
            auditors = st.text_input("Current Auditors")
            erf_number = st.text_input("Erf Number")

        with col4:
            is_vat_registered = st.checkbox("Is Scheme registered for VAT?")
            vat_registration_number = st.text_input("VAT Registration Number", disabled=not is_vat_registered)
            building_code = st.text_input("Building Code")
            building_expense_code = st.text_input("Building Expense Code")
            
        st.text_area("Physical Address", key="physical_address")

        # Previous Managing Agent Details
        st.subheader("Previous Managing Agent (PMA) Details")
        col5, col6 = st.columns(2)
        with col5:
            previous_managing_agent = st.text_input("Previous Managing Agent Name")
            previous_portfolio_manager = st.text_input("Name of Previous PM")
        with col6:
            pma_email = st.text_input("Email Address of Previous PM")
            pma_phone = st.text_input("Telephone Number of Previous PM")
        
        submitted = st.form_submit_button("Create Scheme and Copy Checklists")

        if submitted:
            if not all([scheme_name, assigned_portfolio_manager, pm_email, registration_number]):
                st.error("Please fill in all mandatory fields (*).")
                return

            scheme_type_abbr = 'BC' if is_bc else 'HOA'
            
            # 1. Insert New Scheme
            scheme_data = {
                "scheme_name": scheme_name,
                "previous_managing_agent": previous_managing_agent,
                "previous_portfolio_manager": previous_portfolio_manager,
                "pma_email": pma_email,
                "pma_phone": pma_phone,
                # FIX: Converting date objects to JSON serializable strings
                "appointment_date": appointment_date.isoformat(), 
                "financial_year_end": financial_year_end.isoformat(), 
                
                "number_of_units": number_of_units,
                "management_fees": management_fees,
                "erf_number": erf_number,
                "scheme_type": scheme_type_abbr,
                "registration_number": registration_number,
                "is_vat_registered": is_vat_registered,
                "vat_registration_number": vat_registration_number,
                "sars_income_tax_number": sars_income_tax_number,
                "auditors": auditors,
                "building_code": building_code,
                "building_expense_code": building_expense_code,
                "physical_address": st.session_state.physical_address,
                "assigned_portfolio_manager": assigned_portfolio_manager,
                "pm_email": pm_email,
                # FIX: Converting date objects to JSON serializable strings
                "initial_request_date": initial_request_date.isoformat() 
            }
            
            try:
                # Insert the scheme and get its new ID
                response = supabase.table("schemes").insert(scheme_data).execute()
                new_scheme_id = response.data[0]['id']
                st.success(f"Scheme '{scheme_name}' created successfully!")
                
                # 2. Copy Checklists (Requirements 1 & 2)
                # Filter master items based on scheme type
                items_to_copy = df_master_checklist[df_master_checklist['scheme_type'] == scheme_type_abbr]
                
                if not items_to_copy.empty:
                    progress_data = []
                    for index, row in items_to_copy.iterrows():
                        progress_data.append({
                            "scheme_id": new_scheme_id,
                            "master_item_id": row['id'],
                            "is_complete": False, # Start as incomplete
                        })
                    
                    # Bulk insert into progress_tracker
                    supabase.table("progress_tracker").insert(progress_data).execute()
                    st.success(f"Copied {len(progress_data)} checklist items to the new scheme.")
                else:
                    st.warning("No master checklist items found for this scheme type to copy.")

            except Exception as e:
                st.error(f"Failed to create scheme or copy checklists: {e}")

def progress_tracker_page():
    """Handles marking off progress and generating the PDF report (Requirement 5)."""
    st.header("✅ Take-On Progress Tracker")
    st.markdown("---")

    # Fetch all schemes and merge with progress tracker data
    df_schemes = fetch_data("schemes")
    
    if df_schemes.empty:
        st.info("Please create a new scheme first.")
        return

    # Scheme Selector
    scheme_options = df_schemes.set_index('id')['scheme_name'].to_dict()
    selected_scheme_id = st.selectbox("Select Scheme", options=list(scheme_options.keys()), format_func=lambda x: scheme_options[x])
    
    if selected_scheme_id:
        
        # Join progress_tracker with master_checklist for item details
        progress_data_list = supabase.from_('progress_tracker').select("*, master_checklist(*)").eq('scheme_id', selected_scheme_id).execute().data
        
        if not progress_data_list:
            st.info("No checklist items linked to this scheme.")
            return

        # Flatten the joined data for easier use with Pandas
        data_for_df = []
        for item in progress_data_list:
            data_for_df.append({
                'progress_id': item['id'],
                'item_description': item['master_checklist']['item_description'],
                'scheme_type': item['master_checklist']['scheme_type'],
                'type': item['master_checklist']['type'],
                'is_complete': item['is_complete'],
                'date_completed': item['date_completed'],
                'completed_by': item['completed_by'],
                'notes': item['notes'] 
            })
        
        df_progress = pd.DataFrame(data_for_df)
        
        # --- Display and Edit Progress ---
        
        # Split into PMA and Pretor Group items
        df_pma = df_progress[df_progress['type'] == 'PMA'].reset_index(drop=True)
        df_pretor = df_progress[df_progress['type'] == 'Pretor'].reset_index(drop=True)
        
        tab_pma, tab_pretor, tab_report = st.tabs(["PMA Items", "Pretor Group Items", "Progress Report"])
        
        # Function to display and edit progress (nested to maintain scope/indentation)
        def display_and_edit_progress(df: pd.DataFrame, source_type: str):
            """Renders an editable table for progress tracking."""
            
            if df.empty:
                st.info(f"No {source_type} checklist items available for this scheme type.")
                return

            st.subheader(f"{source_type} Take-On Items")
            
            # Prepare data for Streamlit's data_editor
            df_display = df.copy()
            df_display = df_display.rename(columns={
                'item_description': 'Checklist Item', 
                'is_complete': 'Complete', 
                'date_completed': 'Date', 
                'completed_by': 'Completed By',
                'notes': 'Notes' 
            })
            
            # Columns we actually want to compare later (using their display names)
            editable_cols = ['Complete', 'Date', 'Completed By', 'Notes']

            # Configure columns for editing
            column_config = {
                "Checklist Item": st.column_config.TextColumn("Checklist Item", disabled=True),
                "Complete": st.column_config.CheckboxColumn("Complete"),
                "Date": st.column_config.DateColumn("Date", required=False),
                "Completed By": st.column_config.SelectboxColumn("Completed By", options=["Me", "Portfolio Assistant", "Bookkeeper"], required=False),
                "Notes": st.column_config.TextColumn("Notes", width="large", required=False),
                # Hide internal columns
                "progress_id": None,
                "scheme_type": None,
                "type": None,
            }

            edited_df = st.data_editor(
                df_display,
                column_config=column_config,
                hide_index=True,
                use_container_width=True
            )
            
            if st.button(f"Save {source_type} Changes", key=f"save_{source_type}"):
                
                # FIX for ValueError: Ensure alignment by comparing only editable columns
                comparison_df_original = df_display[editable_cols]
                comparison_df_edited = edited_df[editable_cols]
                changes = comparison_df_edited.compare(comparison_df_original, keep_shape=True)
                
                if not changes.empty:
                    updated_rows = []
                    
                    for index in changes.index:
                        progress_id = df.loc[index, 'progress_id']
                        
                        # Get new values from the edited DataFrame (using display names)
                        new_complete = edited_df.loc[index, 'Complete']
                        new_date = edited_df.loc[index, 'Date']
                        new_by = edited_df.loc[index, 'Completed By']
                        new_notes = edited_df.loc[index, 'Notes'] 
                        
                        # Prepare update payload (using database names)
                        update_payload = {
                            "is_complete": new_complete,
                            "date_completed": new_date if new_complete and new_date else None, 
                            "completed_by": new_by if new_complete and new_by else None,
                            "notes": new_notes
                        }
                        
                        # Update the database
                        supabase.table('progress_tracker').update(update_payload).eq('id', progress_id).execute()
                        updated_rows.append(progress_id)
                    
                    st.success(f"Successfully updated {len(updated_rows)} item(s) in the {source_type} list.")
                    st.rerun() 
                else:
                    st.info("No changes detected to save.")


        with tab_pma:
            display_and_edit_progress(df_pma, "PMA")
            
        with tab_pretor:
            display_and_edit_progress(df_pretor, "Pretor Group")

        with tab_report:
            st.subheader("Weekly Progress Report (Client View)")
            st.info("This report will **only include Pretor Group items** for client-facing progress confirmation.")
            
            # Pass the full df_progress which contains both types, the PDF function will filter.
            pdf_bytes = generate_pdf_report(scheme_options[selected_scheme_id], df_progress)
            
            # Display a download button for the PDF
            st.download_button(
                label="Download PDF Progress Report",
                data=pdf_bytes,
                file_name=f"{scheme_options[selected_scheme_id]}_TakeOn_Report_{date.today()}.pdf",
                mime="application/pdf"
            )


# --- Main Application Logic ---

def main():
    """The main function to run the Streamlit app."""
    st.set_page_config(page_title="Pretor Group Take-On App", layout="wide", initial_sidebar_state="expanded")
    st.sidebar.title("☁️ Pretor Take-On App")

    # Initialize session state for login status
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['user'] = None

    if st.session_state['logged_in']:
        # Logged in view
        st.sidebar.success(f"Logged in as: {st.session_state['user'].email}")
        
        # Navigation
        app_mode = st.sidebar.selectbox("Go to", ["Progress Tracker", "Create New Scheme", "Master Data"])
        st.sidebar.markdown("---")
        st.sidebar.button("Sign Out", on_click=sign_out)

        if app_mode == "Master Data":
            master_data_page()
        elif app_mode == "Create New Scheme":
            new_scheme_page()
        elif app_mode == "Progress Tracker":
            progress_tracker_page()
            
    else:
        # Not logged in view
        st.title("Welcome to the Pretor Group Take-On App")
        st.info("Please sign in on the sidebar to access the application.")
        login_form()

if __name__ == "__main__":
    main()
