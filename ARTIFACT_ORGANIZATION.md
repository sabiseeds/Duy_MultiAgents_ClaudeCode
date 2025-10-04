# Artifact Organization

## Overview

All generated files are now organized in the `artifacts/` directory to keep the project root clean and professional.

## Directory Structure

```
MultiAgents_ClaudeCode/
├── artifacts/                          # All generated outputs
│   ├── results/                        # HTML task results
│   │   ├── 041025150230_task_abc_20251004_150230/
│   │   │   ├── subtask_123_agent_1.html
│   │   │   └── subtask_456_agent_2.html
│   │   └── 041025151545_task_xyz_20251004_151545/
│   │       └── subtask_789_agent_3.html
│   ├── uploads/                        # User-uploaded files
│   │   ├── 041025150230_task_abc/
│   │   │   ├── sales_data.csv
│   │   │   └── report.pdf
│   │   └── 041025151545_task_xyz/
│   │       └── image.jpg
│   ├── reports/                        # Analysis reports
│   │   ├── efficiency_analysis.html
│   │   └── correlation_report.html
│   ├── data/                          # Generated data files
│   │   ├── analysis_results.json
│   │   └── processed_data.csv
│   ├── images/                        # Visualizations
│   │   ├── correlation_heatmap.png
│   │   └── trend_chart.png
│   └── temp/                          # Temporary files
│       └── (auto-cleaned)
├── agent/                             # Source code
├── orchestrator/
├── shared/
├── ui/
└── scripts/
```

## Artifact Types

### 1. Results (`artifacts/results/`)
**Purpose**: HTML outputs from agent task execution

**Format**: `{task_id}_{timestamp}/subtask_{id}_agent_{id}.html`

**Contents**:
- Agent-generated HTML reports
- Task execution results
- Formatted with professional styling

**Example**:
```
artifacts/results/041025150230_task_abc_20251004_150230/
├── subtask_a1b2c3_agent_1.html
└── subtask_d4e5f6_agent_2.html
```

### 2. Uploads (`artifacts/uploads/`)
**Purpose**: User-uploaded files attached to tasks

**Format**: `{task_id}/original_filename.ext`

**Contents**:
- CSV, Excel files
- PDFs, Word documents
- Images
- Archives (ZIP, RAR)

**Example**:
```
artifacts/uploads/041025150230_task_abc/
├── sales_data.csv
├── contracts.pdf
└── product_images.zip
```

### 3. Reports (`artifacts/reports/`)
**Purpose**: Analysis and summary reports

**Usage**:
```python
from shared.artifact_manager import artifact_manager

# Save report
path = artifact_manager.save_report(
    filename="analysis_report.html",
    content=html_content,
    subfolder="efficiency"  # Optional
)
```

**Example**:
```
artifacts/reports/
├── efficiency/
│   ├── rebate_analysis.html
│   └── discount_correlation.html
└── quarterly_summary.html
```

### 4. Data (`artifacts/data/`)
**Purpose**: Generated data files (JSON, CSV, XML)

**Usage**:
```python
# Save data file
path = artifact_manager.save_data(
    filename="processed_results.json",
    content=json_string,
    subfolder="analysis_outputs"  # Optional
)
```

**Example**:
```
artifacts/data/
├── analysis_outputs/
│   ├── correlation_matrix.json
│   └── summary_stats.csv
└── raw_extracts.json
```

### 5. Images (`artifacts/images/`)
**Purpose**: Visualizations, charts, graphs

**Usage**:
```python
# Save image file
path = artifact_manager.save_image(
    filename="heatmap.png",
    content=image_bytes,
    subfolder="correlations"  # Optional
)
```

**Example**:
```
artifacts/images/
├── correlations/
│   ├── discount_heatmap.png
│   └── trend_visualization.png
└── summary_chart.png
```

### 6. Temp (`artifacts/temp/`)
**Purpose**: Temporary processing files

**Auto-cleanup**: Can be cleaned anytime
```python
artifact_manager.cleanup_temp()
```

## Using the Artifact Manager

### Import
```python
from shared.artifact_manager import artifact_manager
```

### Save HTML Result (Agents)
```python
# Automatically called by agents
html_path = await save_result_html(
    task_id="041025150230_task_abc",
    subtask_id="subtask_123",
    agent_id="agent_1",
    html_content="<h1>Results</h1>...",
    execution_time=45.2
)
```

### Save Report
```python
# For analysis reports
report_path = artifact_manager.save_report(
    filename="efficiency_report.html",
    content=report_html,
    subfolder="quarterly"  # Optional subfolder
)
```

### Save Data
```python
# For JSON/CSV/data files
data_path = artifact_manager.save_data(
    filename="analysis.json",
    content=json.dumps(data),
    subfolder="raw_data"
)
```

### Save Image
```python
# For charts/visualizations
image_path = artifact_manager.save_image(
    filename="chart.png",
    content=png_bytes,
    subfolder="charts"
)
```

### Get Storage Info
```python
# Check artifact statistics
info = artifact_manager.get_artifact_info()
print(info)
# {
#     "base_directory": "artifacts",
#     "results": {"count": 25, "size_mb": 12.5},
#     "uploads": {"count": 10, "size_mb": 45.2},
#     "reports": {"count": 5, "size_mb": 8.3},
#     "data": {"count": 15, "size_mb": 5.1},
#     "images": {"count": 8, "size_mb": 3.2},
#     "total_files": 63,
#     "total_size_mb": 74.3
# }
```

## Benefits

### ✅ Organization
- **Clean project root**: No scattered files
- **Logical grouping**: Files organized by type and purpose
- **Easy navigation**: Find what you need quickly

### ✅ Maintenance
- **Simple cleanup**: Delete entire `artifacts/` folder
- **Selective cleanup**: Remove specific subfolders
- **Git-friendly**: Entire folder in `.gitignore`

### ✅ Scalability
- **No file conflicts**: Structured subdirectories
- **Timestamp-based**: Automatic chronological ordering
- **Unlimited growth**: No hardcoded paths

## Cleanup Strategies

### Full Reset
```bash
# Deletes everything and recreates structure
python scripts/reset_all_tasks.py
```

### Manual Cleanup
```bash
# Delete old results (Windows)
forfiles /p artifacts\results /s /d -30 /c "cmd /c rmdir /s /q @path"

# Delete old results (Linux/Mac)
find artifacts/results -type d -mtime +30 -exec rm -rf {} +
```

### Selective Cleanup
```bash
# Keep uploads, delete everything else
rm -rf artifacts/results artifacts/reports artifacts/data artifacts/images
```

### Temp Cleanup
```python
# In code
from shared.artifact_manager import artifact_manager
artifact_manager.cleanup_temp()
```

## Migration from Old Structure

If you have files in the old locations:

### Move Existing Files
```bash
# Windows
if exist results\ move results artifacts\results
if exist uploads\ move uploads artifacts\uploads

# Linux/Mac
if [ -d "results" ]; then mv results artifacts/results; fi
if [ -d "uploads" ]; then mv uploads artifacts/uploads; fi
```

### Or Clean Start
```bash
# Delete old directories
rm -rf results uploads *.html *.json *.png *.csv

# Reset system
python scripts/reset_all_tasks.py
```

## Accessing Artifacts

### In Streamlit UI
1. **Results Files Tab**: Browse `artifacts/results/`
2. **Task Monitoring**: View HTML results inline
3. **Download**: Download files directly

### Programmatically
```python
from pathlib import Path

# List all results
results = Path("artifacts/results").glob("**/*.html")
for result in results:
    print(result)

# Find task uploads
task_id = "041025150230_task_abc"
uploads = Path(f"artifacts/uploads/{task_id}").glob("*")
```

### Direct Access
Simply navigate to `artifacts/` folder in your file explorer.

## Best Practices

1. **Use artifact_manager**: Don't create files manually
2. **Proper subfolder usage**: Organize by category when needed
3. **Regular cleanup**: Delete old artifacts periodically
4. **Check storage**: Monitor with `get_artifact_info()`
5. **Backup important results**: Move critical files elsewhere

## Storage Guidelines

### Recommended Limits
- **Per task results**: ~10MB
- **Per upload file**: 50MB (enforced)
- **Total artifacts**: Monitor and clean as needed

### Warning Signs
- Artifacts folder > 1GB: Consider cleanup
- Thousands of files: Archive old tasks
- Slow file operations: Too many files in one folder

---

**Implementation Status**: ✅ Fully implemented
**Last Updated**: 2025-10-04
