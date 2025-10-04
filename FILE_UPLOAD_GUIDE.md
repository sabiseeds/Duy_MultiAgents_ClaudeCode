# File Upload Feature Guide

## Overview

The Multi-Agent System now supports file uploads! Attach files to your tasks and agents will have access to them during execution.

## Supported File Types

### Documents
- PDF (`.pdf`)
- Word (`.doc`, `.docx`)
- Text (`.txt`)
- Rich Text (`.rtf`)

### Spreadsheets & Data
- Excel (`.xls`, `.xlsx`)
- CSV (`.csv`)
- JSON (`.json`)
- XML (`.xml`)
- YAML (`.yaml`, `.yml`)

### Images
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- BMP (`.bmp`)
- SVG (`.svg`)
- WebP (`.webp`)

### Archives
- ZIP (`.zip`)
- RAR (`.rar`)
- 7-Zip (`.7z`)
- TAR (`.tar`, `.gz`)

### Other
- PowerPoint (`.ppt`, `.pptx`)
- Markdown (`.md`)

## File Size Limits

- **Maximum file size**: 50MB per file
- **Multiple files**: Upload as many files as needed
- **Total limit**: No total size limit (within reasonable storage)

## How to Upload Files

### Via Streamlit UI

1. Go to **Submit Task** tab
2. Enter your task description
3. Scroll to **📎 Attach Files** section
4. Click **Browse files** or drag & drop
5. Select one or more files
6. Click **🚀 Submit Task**

### Example Tasks with Files

#### Analyze CSV Data
```
Task: Analyze the sales data in the attached CSV file and create a summary report with:
- Total revenue by region
- Top 10 products
- Monthly trends
- Recommendations

Attach: sales_data.csv
```

#### Process Multiple Documents
```
Task: Review these contract documents and create a comparison table highlighting:
- Key terms
- Pricing differences
- Contract duration
- Special clauses

Attach: contract_a.pdf, contract_b.pdf, contract_c.pdf
```

#### Image Analysis
```
Task: Analyze these product images and generate:
- Quality assessment
- Recommendations for improvement
- Comparison table

Attach: product1.jpg, product2.jpg, product3.jpg
```

## File Organization

### Task-Specific Folders

Each task gets its own folder with a timestamped ID:

```
uploads/
├── 041025150230_task_abc123def456/
│   ├── sales_data.csv
│   ├── contracts.zip
│   └── report.pdf
├── 041025151545_task_xyz789ghi012/
│   ├── image1.jpg
│   └── image2.jpg
```

**Format**: `{ddmmyyhhmmss}_task_{unique_id}/`

### Timestamped Task IDs

All task IDs now include a timestamp prefix for easy sorting:

- **Format**: `ddmmyyhhmmss_task_{unique_id}`
- **Example**: `041025150230_task_abc123def456`
- **Benefits**:
  - Chronological ordering
  - Easy to find recent tasks
  - No ID collisions

## Agent Access to Files

### How Agents See Files

When agents execute subtasks, they receive information about attached files:

```
Attached Files:
  - sales_data.csv (2.5MB, text/csv)
    Path: uploads/041025150230_task_abc123def456/sales_data.csv
  - report.pdf (1.8MB, application/pdf)
    Path: uploads/041025150230_task_abc123def456/report.pdf
```

### Agent Capabilities

Agents can:
- ✅ See file names, sizes, and types
- ✅ Access file paths
- ✅ Read file contents
- ✅ Process data from files
- ✅ Reference files in their responses

## Viewing Uploaded Files

### In Monitor Tasks Tab

1. Enter task ID and refresh
2. Scroll to **📎 Attached Files** section
3. See list of all files with:
   - Original filename
   - File size
   - MIME type
4. Click **⬇️ Download** to get the file

### File Metadata

Each file includes:
- `filename`: Sanitized storage name
- `original_filename`: Original upload name
- `file_path`: Relative path from project root
- `file_size`: Size in bytes
- `mime_type`: Content type
- `uploaded_at`: Upload timestamp

## Security Features

### File Validation

- ✅ Extension whitelist (only allowed types)
- ✅ Size limit enforcement (50MB)
- ✅ Filename sanitization (no path traversal)
- ✅ MIME type detection

### Safe Storage

- ✅ Files stored outside web root
- ✅ Unique task-specific folders
- ✅ No executable files allowed
- ✅ Sanitized filenames (dangerous chars removed)

### Duplicate Handling

If you upload multiple files with the same name:
- First file: `document.pdf`
- Second file: `document_1.pdf`
- Third file: `document_2.pdf`

## API Integration

### Upload Files Programmatically

```python
import httpx

# Prepare task with files
files = [
    ('files', ('data.csv', open('data.csv', 'rb'), 'text/csv')),
    ('files', ('report.pdf', open('report.pdf', 'rb'), 'application/pdf'))
]

form_data = {
    'description': 'Analyze the attached data and generate a report',
    'user_id': 'api_user'
}

# Submit
response = httpx.post(
    'http://localhost:8000/tasks',
    data=form_data,
    files=files
)

task_data = response.json()
print(f"Task ID: {task_data['task_id']}")
print(f"Files uploaded: {task_data['files_uploaded']}")
```

### Response Format

```json
{
  "task_id": "041025150230_task_abc123def456",
  "status": "created",
  "subtasks_count": 3,
  "initial_subtasks_queued": 2,
  "files_uploaded": 2
}
```

## Database Schema

### Tasks Table

New columns:
- `attachments` (JSONB): Array of file metadata
- `uploads_folder` (TEXT): Path to task's upload folder

### Example Data

```json
{
  "attachments": [
    {
      "filename": "sales_data.csv",
      "original_filename": "Q4 Sales Data.csv",
      "file_path": "uploads/041025150230_task_abc/sales_data.csv",
      "file_size": 2621440,
      "mime_type": "text/csv",
      "uploaded_at": "2025-10-04T15:02:30.123456"
    }
  ],
  "uploads_folder": "uploads/041025150230_task_abc"
}
```

## Storage Management

### Cleanup

To clean up old task files:

```python
from shared.file_storage import file_storage

# Delete files for a specific task
file_storage.delete_task_files("041025150230_task_abc123def456")
```

### Manual Cleanup

```bash
# Delete uploads older than 30 days
find uploads/ -type d -mtime +30 -exec rm -rf {} +
```

### Storage Location

```
MultiAgents_ClaudeCode/
├── uploads/           # All task files
│   ├── 041025150230_task_abc/
│   └── 041025151545_task_xyz/
└── results/           # HTML results
    ├── 041025150230_task_abc_20251004_150230/
    └── 041025151545_task_xyz_20251004_151545/
```

## Best Practices

### File Naming

✅ **Good**:
- `sales_data_2025.csv`
- `contract_final.pdf`
- `product_specs.xlsx`

❌ **Avoid**:
- `../../etc/passwd` (path traversal)
- `file<script>.pdf` (dangerous chars)
- Very long names (>200 chars)

### Task Descriptions

Be specific about what you want agents to do with files:

✅ **Good**:
```
Analyze sales_data.csv and create a summary with:
1. Total revenue by product category
2. Top 10 customers
3. Identify sales trends
```

❌ **Vague**:
```
Do something with the CSV file
```

### File Preparation

- Clean data before upload
- Use standard formats (UTF-8 for text)
- Compress large files to ZIP
- Split very large datasets

## Troubleshooting

### File Not Uploaded

**Symptoms**: No files shown in task details

**Solutions**:
1. Check file size < 50MB
2. Verify file type is supported
3. Check browser console for errors
4. Try smaller files first

### Agent Can't Access File

**Symptoms**: Agent response doesn't mention file

**Solutions**:
1. Verify file uploaded successfully
2. Check file path in task details
3. Ensure file still exists in uploads/ folder
4. Check agent logs for errors

### Download Button Not Working

**Symptoms**: Can't download attached file

**Solutions**:
1. Check file exists at path
2. Verify file permissions
3. Try refreshing the page
4. Check browser download settings

## Limitations

- ⚠️ Files are not automatically deleted
- ⚠️ No virus scanning (use at own risk)
- ⚠️ No file editing in UI
- ⚠️ No preview for all file types
- ⚠️ Agents see file paths but may not process all formats

## Future Enhancements

Planned improvements:
- 📊 File preview in UI (images, PDFs)
- 🔍 Content search across uploaded files
- 🗜️ Automatic compression
- 🗑️ Auto-cleanup policies
- 📧 Email file attachments to tasks
- 🔐 Encryption at rest
- 📁 Shared file library across tasks

---

**Feature Status**: ✅ Fully implemented and ready to use!

**Last Updated**: 2025-10-04
