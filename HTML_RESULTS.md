# HTML Results Feature

## Overview

All agent task results are now automatically saved as beautifully formatted HTML files, organized by task ID and timestamp.

## Directory Structure

```
results/
├── task_abc123_20250104_143022/
│   ├── subtask_xyz_agent_1.html
│   ├── subtask_def_agent_2.html
│   └── subtask_ghi_agent_1.html
├── task_def456_20250104_143525/
│   └── subtask_jkl_agent_3.html
└── ...
```

**Format:** `{task_id}_{YYYYMMDD_HHMMSS}/`

Each task gets its own folder with a timestamp when the first subtask completes.

## HTML File Features

### Automatic Styling
Each HTML file includes:
- ✅ Professional gradient header with metadata
- ✅ Responsive design (mobile-friendly)
- ✅ Syntax highlighting for code blocks
- ✅ Table styling
- ✅ Clean typography
- ✅ Task metadata (Task ID, Subtask ID, Agent ID, Execution Time, Timestamp)

### Agent Output Format
Agents are instructed to generate HTML with:
- **Summary section** - Key findings at a glance
- **Detailed results** - Comprehensive information
- **Structured content** - Proper headings (h1, h2, h3)
- **Rich formatting** - Tables, lists, code blocks where appropriate

## Viewing Results

### Option 1: Streamlit UI (Recommended)

**Monitor Tasks Tab:**
1. Enter task ID and click "Refresh Status"
2. Expand any completed subtask
3. See embedded HTML preview
4. Download individual HTML files

**Results Files Tab:**
1. Navigate to the "📁 Results Files" tab
2. Select a task folder from the dropdown
3. Browse all subtask results
4. Preview HTML inline
5. Download individual files or entire task as ZIP

### Option 2: Direct File Access

Navigate to `results/` directory and open any `.html` file in your browser.

## Example Output

### Sample Agent Response

```html
<h1>Vietnam Provinces Research</h1>

<h2>Summary</h2>
<p>Found information about 5 new provinces created in Vietnam:</p>
<ul>
  <li>Hải Dương Province (2008)</li>
  <li>Điện Biên Province (2004)</li>
  <li>Đắk Nông Province (2004)</li>
  <li>Hậu Giang Province (2004)</li>
  <li>Cần Thơ (elevated to municipality, 2004)</li>
</ul>

<h2>Detailed Information</h2>
<table>
  <thead>
    <tr>
      <th>Province</th>
      <th>Year Established</th>
      <th>Population</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Hải Dương</td>
      <td>2008</td>
      <td>~1.8 million</td>
    </tr>
    <!-- More rows... -->
  </tbody>
</table>
```

This gets automatically wrapped with professional styling and metadata.

## Benefits

### For Users
- ✅ **Easy sharing** - Send HTML files to stakeholders
- ✅ **Professional appearance** - Ready for presentations
- ✅ **Offline access** - View results without running the system
- ✅ **Long-term storage** - Archive important results

### For Developers
- ✅ **Debugging** - Review agent outputs easily
- ✅ **Testing** - Verify agent behavior visually
- ✅ **Documentation** - Auto-generated result documentation

## File Naming Convention

**Format:** `{subtask_id}_{agent_id}.html`

**Example:** `subtask_54daafc4141b_agent_2.html`
- Subtask ID: `subtask_54daafc4141b`
- Agent: `agent_2`

## Storage Management

### Automatic Organization
- Each task gets a dedicated folder
- Timestamp prevents folder name conflicts
- Easy to archive by date

### Manual Cleanup
To free up space, simply delete old task folders:

```bash
# Delete tasks older than 30 days
find results/ -type d -mtime +30 -exec rm -rf {} +
```

## Customization

### Changing HTML Style

Edit `agent/agent_service.py` in the `save_result_html()` function to customize:
- Color scheme (currently purple gradient)
- Font family
- Layout width
- Table styling
- Code block appearance

### Changing Output Format

Modify the agent prompt in `agent/agent_service.py` to change how agents structure their responses.

## Troubleshooting

### HTML files not appearing
- Check that agents completed successfully (no errors)
- Verify `results/` directory exists
- Check agent logs for file write errors

### HTML not rendering correctly
- Agents may output plain text instead of HTML
- Check agent prompt in `agent_service.py`
- Verify Claude Code authentication is working

### Cannot view in Streamlit
- Ensure Streamlit has file read permissions
- Check file paths are relative to project root
- Verify `st.components.v1.html` is not blocked

## API Integration

Access HTML files programmatically:

```python
import os
from pathlib import Path

# Get all results for a task
task_id = "task_abc123"
results_dir = Path("results")

# Find task folder (may have timestamp suffix)
task_folders = [d for d in results_dir.iterdir() if d.name.startswith(task_id)]

if task_folders:
    task_folder = task_folders[0]
    html_files = list(task_folder.glob("*.html"))

    for html_file in html_files:
        print(f"Found result: {html_file}")
        content = html_file.read_text(encoding='utf-8')
        # Process content...
```

## Future Enhancements

Potential improvements:
- 📊 **PDF generation** - Convert HTML to PDF
- 📧 **Email delivery** - Send results automatically
- 🔍 **Full-text search** - Search across all results
- 📈 **Analytics dashboard** - Visualize result trends
- 🎨 **Themes** - Multiple style templates
- 🔗 **Cross-linking** - Link related subtasks

---

**Status:** ✅ Fully implemented and ready to use!

**Last Updated:** 2025-01-04
