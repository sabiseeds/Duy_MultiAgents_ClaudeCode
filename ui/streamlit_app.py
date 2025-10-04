"""
Streamlit UI for the Multi-Agent Task Execution System.
Provides task submission, monitoring, and agent dashboard.
"""
import streamlit as st
import httpx
import time
import os
from datetime import datetime


# Configuration
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")


# Page configuration
st.set_page_config(
    page_title="Multi-Agent Task Execution System",
    page_icon="🤖",
    layout="wide"
)


def main():
    st.title("🤖 Multi-Agent Task Execution System")
    st.markdown("*Powered by Claude AI and distributed agent architecture*")

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Submit Task", "📊 Monitor Tasks", "🤖 Agent Dashboard", "📁 Results Files"])

    with tab1:
        show_task_submission()

    with tab2:
        show_task_monitoring()

    with tab3:
        show_agent_dashboard()

    with tab4:
        show_results_browser()


def show_task_submission():
    """Task submission interface"""
    st.header("Submit New Task")

    with st.form("task_form"):
        description = st.text_area(
            "Task Description",
            height=150,
            placeholder="Enter a detailed task description (min 10 characters)...\n\nExamples:\n- Calculate factorial of 10\n- Analyze sales data and generate a report\n- Fetch weather data from API and create visualizations\n- Analyze this CSV file and create a summary report"
        )

        user_id = st.text_input(
            "User ID (optional)",
            value="streamlit_user",
            help="Identifier for tracking your tasks"
        )

        # File upload section
        st.markdown("#### 📎 Attach Files (Optional)")
        st.caption("Supported: Images (jpg, png), Documents (pdf, docx, txt), Spreadsheets (csv, xlsx), Archives (zip) - Max 50MB per file")

        uploaded_files = st.file_uploader(
            "Upload files for agents to process",
            type=['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'txt',
                  'xls', 'xlsx', 'csv', 'zip', 'rar', 'json', 'xml', 'yaml', 'md'],
            accept_multiple_files=True,
            help="Agents will have access to these files when executing the task"
        )

        submitted = st.form_submit_button("🚀 Submit Task", use_container_width=True)

        if submitted:
            if len(description) < 10:
                st.error("Task description must be at least 10 characters")
            elif len(description) > 5000:
                st.error("Task description must be less than 5000 characters")
            else:
                with st.spinner("Submitting task..."):
                    try:
                        # Prepare multipart form data
                        files_data = []
                        form_data = {
                            "description": description,
                            "user_id": user_id
                        }

                        # Add uploaded files to form data
                        if uploaded_files:
                            for uploaded_file in uploaded_files:
                                files_data.append(
                                    ("files", (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type))
                                )

                        # Submit task with files
                        response = httpx.post(
                            f"{ORCHESTRATOR_URL}/tasks",
                            data=form_data,
                            files=files_data if files_data else None,
                            timeout=60.0
                        )

                        if response.status_code == 200:
                            data = response.json()
                            st.success(f"✅ Task submitted successfully!")
                            st.info(f"**Task ID:** `{data['task_id']}`")
                            st.info(f"**Subtasks Created:** {data['subtasks_count']}")
                            st.info(f"**Queued for Execution:** {data['initial_subtasks_queued']}")

                            if data.get('files_uploaded', 0) > 0:
                                st.info(f"**Files Uploaded:** {data['files_uploaded']}")

                            # Store task ID in session state for monitoring
                            st.session_state['last_task_id'] = data['task_id']

                        else:
                            st.error(f"Error: {response.status_code} - {response.text}")

                    except Exception as e:
                        st.error(f"Failed to submit task: {e}")


def show_task_monitoring():
    """Task monitoring interface"""
    st.header("Monitor Task Execution")

    # Task ID input
    col1, col2 = st.columns([3, 1])

    with col1:
        task_id = st.text_input(
            "Task ID",
            value=st.session_state.get('last_task_id', ''),
            placeholder="Enter task ID to monitor..."
        )

    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        auto_refresh = st.checkbox("Auto-refresh", value=False)

    if task_id:
        # Fetch button or auto-refresh
        if st.button("🔄 Refresh Status", use_container_width=True) or auto_refresh:
            show_task_status(task_id)

            if auto_refresh:
                time.sleep(2)
                st.rerun()


def show_task_status(task_id: str):
    """Display detailed task status"""
    try:
        response = httpx.get(
            f"{ORCHESTRATOR_URL}/tasks/{task_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            st.error("Task not found")
            return
        elif response.status_code != 200:
            st.error(f"Error: {response.status_code}")
            return

        data = response.json()
        task = data['task']
        subtask_results = data['subtask_results']

        # Task overview
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            status_emoji = {
                "pending": "⏳",
                "in_progress": "▶️",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫"
            }
            st.metric("Status", f"{status_emoji.get(task['status'], '❓')} {task['status'].upper()}")

        with col2:
            st.metric("Subtasks", len(task.get('subtasks', [])))

        with col3:
            completed = len([r for r in subtask_results if r['status'] == 'completed'])
            st.metric("Completed", completed)

        with col4:
            failed = len([r for r in subtask_results if r['status'] == 'failed'])
            st.metric("Failed", failed)

        # Progress bar
        if task.get('subtasks'):
            progress = len(subtask_results) / len(task['subtasks'])
            st.progress(progress, text=f"Progress: {len(subtask_results)}/{len(task['subtasks'])} subtasks")

        # Task details
        st.subheader("Task Details")
        st.write(f"**Description:** {task['description']}")
        st.write(f"**User ID:** {task['user_id']}")
        st.write(f"**Created:** {task['created_at']}")
        st.write(f"**Updated:** {task['updated_at']}")

        # Attached files
        if task.get('attachments') and len(task['attachments']) > 0:
            st.markdown("#### 📎 Attached Files")
            for att in task['attachments']:
                file_size_mb = att['file_size'] / (1024 * 1024)
                st.write(f"- **{att['original_filename']}** ({file_size_mb:.2f} MB, {att['mime_type']})")
                if os.path.exists(att['file_path']):
                    with open(att['file_path'], 'rb') as f:
                        st.download_button(
                            f"⬇️ Download {att['filename']}",
                            data=f.read(),
                            file_name=att['original_filename'],
                            mime=att['mime_type'],
                            key=f"download_att_{att['filename']}"
                        )

        # Subtasks
        if task.get('subtasks'):
            st.subheader("Subtasks")
            for i, subtask in enumerate(task['subtasks']):
                with st.expander(f"Subtask {i+1}: {subtask['description'][:60]}..."):
                    st.write(f"**ID:** `{subtask['id']}`")
                    st.write(f"**Capabilities:** {', '.join(subtask['required_capabilities'])}")
                    st.write(f"**Priority:** {subtask['priority']}")
                    st.write(f"**Dependencies:** {subtask.get('dependencies', [])}")

                    # Find result for this subtask
                    result = next((r for r in subtask_results if r['subtask_id'] == subtask['id']), None)
                    if result:
                        st.write(f"**Status:** {result['status']}")
                        st.write(f"**Agent:** {result['agent_id']}")
                        st.write(f"**Execution Time:** {result['execution_time']:.2f}s")

                        if result['output']:
                            # Check if HTML file exists
                            html_file = result['output'].get('html_file')
                            if html_file and os.path.exists(html_file):
                                st.success(f"📄 **Result saved to:** `{html_file}`")

                                # Display HTML content
                                try:
                                    with open(html_file, 'r', encoding='utf-8') as f:
                                        html_content = f.read()

                                    # Use iframe to safely display HTML
                                    st.components.v1.html(html_content, height=600, scrolling=True)

                                    # Download button
                                    st.download_button(
                                        label="⬇️ Download HTML Result",
                                        data=html_content,
                                        file_name=os.path.basename(html_file),
                                        mime="text/html"
                                    )
                                except Exception as e:
                                    st.error(f"Error reading HTML file: {e}")
                                    st.json(result['output'])
                            else:
                                st.json(result['output'])

                        if result['error']:
                            st.error(result['error'])

        # Final result
        if task.get('result'):
            st.subheader("Final Result")
            st.json(task['result'])

        if task.get('error'):
            st.error(f"**Error:** {task['error']}")

    except Exception as e:
        st.error(f"Failed to fetch task status: {e}")


def show_agent_dashboard():
    """Agent dashboard interface"""
    st.header("Agent Dashboard")

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Refresh Agents", use_container_width=True):
            st.rerun()

    with col2:
        auto_refresh_agents = st.checkbox("Auto-refresh (5s)", value=False, key="agent_auto_refresh")

    try:
        response = httpx.get(
            f"{ORCHESTRATOR_URL}/agents",
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            agents = data['agents']

            if not agents:
                st.warning("No agents registered")
                return

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Agents", len(agents))

            with col2:
                available = len([a for a in agents if a['is_available']])
                st.metric("Available", available)

            with col3:
                total_completed = sum(a['tasks_completed'] for a in agents)
                st.metric("Tasks Completed", total_completed)

            with col4:
                avg_cpu = sum(a['cpu_usage'] for a in agents) / len(agents)
                st.metric("Avg CPU", f"{avg_cpu:.1f}%")

            # Agent details
            st.subheader("Agent Status")

            for agent in agents:
                with st.expander(
                    f"{'🟢' if agent['is_available'] else '🔴'} {agent['agent_id']} (Port {agent['port']})",
                    expanded=not agent['is_available']
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Status:** {'✅ Available' if agent['is_available'] else '⏳ Busy'}")
                        st.write(f"**Current Task:** {agent['current_task'] or 'None'}")
                        st.write(f"**Tasks Completed:** {agent['tasks_completed']}")

                    with col2:
                        st.write(f"**Capabilities:** {', '.join(agent['capabilities'])}")
                        st.write(f"**CPU Usage:** {agent['cpu_usage']:.1f}%")
                        st.write(f"**Memory Usage:** {agent['memory_usage']:.1f}%")

                    st.caption(f"Last heartbeat: {agent['last_heartbeat']}")

        else:
            st.error(f"Failed to fetch agents: {response.status_code}")

    except Exception as e:
        st.error(f"Failed to connect to orchestrator: {e}")

    # Auto-refresh
    if auto_refresh_agents:
        time.sleep(5)
        st.rerun()


def show_results_browser():
    """Browse and view saved HTML result files"""
    st.header("📁 Results Files Browser")

    results_dir = "artifacts/results"

    if not os.path.exists(results_dir):
        st.warning("No results directory found. Results will appear here after agents complete tasks.")
        return

    # Get all task directories
    task_dirs = [d for d in os.listdir(results_dir) if os.path.isdir(os.path.join(results_dir, d))]

    if not task_dirs:
        st.info("No task results saved yet. Complete some tasks to see results here!")
        return

    # Sort by timestamp (most recent first)
    task_dirs.sort(reverse=True)

    st.write(f"**Total task folders:** {len(task_dirs)}")

    # Select task folder
    selected_task = st.selectbox(
        "Select Task Folder",
        task_dirs,
        format_func=lambda x: f"{x.split('_')[0]} - {x.split('_', 1)[1] if '_' in x else x}"
    )

    if selected_task:
        task_path = os.path.join(results_dir, selected_task)

        # Get all HTML files in this task folder
        html_files = [f for f in os.listdir(task_path) if f.endswith('.html')]

        if html_files:
            st.write(f"**Subtask results:** {len(html_files)}")

            # Display each HTML file
            for html_file in html_files:
                file_path = os.path.join(task_path, html_file)

                # Extract info from filename
                parts = html_file.replace('.html', '').split('_')
                subtask_id = parts[0] if len(parts) > 0 else "unknown"
                agent_id = parts[1] if len(parts) > 1 else "unknown"

                with st.expander(f"📄 {subtask_id} (by {agent_id})", expanded=False):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**File:** `{html_file}`")
                        st.write(f"**Size:** {os.path.getsize(file_path) / 1024:.2f} KB")

                    with col2:
                        # Download button
                        with open(file_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()

                        st.download_button(
                            label="⬇️ Download",
                            data=html_content,
                            file_name=html_file,
                            mime="text/html",
                            key=f"download_{html_file}"
                        )

                    # Display HTML preview
                    try:
                        st.components.v1.html(html_content, height=500, scrolling=True)
                    except Exception as e:
                        st.error(f"Error displaying HTML: {e}")

                    st.divider()

            # Bulk download option
            st.subheader("Bulk Actions")
            if st.button("📦 Download All Results as ZIP"):
                import zipfile
                from io import BytesIO

                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for html_file in html_files:
                        file_path = os.path.join(task_path, html_file)
                        zip_file.write(file_path, html_file)

                st.download_button(
                    label="⬇️ Download ZIP",
                    data=zip_buffer.getvalue(),
                    file_name=f"{selected_task}_results.zip",
                    mime="application/zip"
                )

        else:
            st.warning("No HTML files found in this task folder.")


if __name__ == "__main__":
    main()
