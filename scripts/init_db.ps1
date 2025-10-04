# PowerShell script to initialize PostgreSQL database
# Usage: .\scripts\init_db.ps1

Write-Host "Initializing Multi-Agent Database..." -ForegroundColor Cyan

$dbHost = "192.168.1.33"
$dbPort = "5432"
$dbUser = "postgres"
$dbName = "multi_agent_db"

# Set password environment variable to avoid prompt
$env:PGPASSWORD = "postgres"

try {
    # Try to find psql.exe
    $psqlPaths = @(
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\PostgreSQL\14\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "psql"
    )

    $psqlCmd = $null
    foreach ($path in $psqlPaths) {
        if (Get-Command $path -ErrorAction SilentlyContinue) {
            $psqlCmd = $path
            break
        }
    }

    if (-not $psqlCmd) {
        Write-Host "ERROR: psql command not found!" -ForegroundColor Red
        Write-Host "Please install PostgreSQL or add it to your PATH" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "Found psql at: $psqlCmd" -ForegroundColor Green

    # Execute SQL script
    Write-Host "Running init_database.sql..." -ForegroundColor Cyan
    & $psqlCmd -h $dbHost -p $dbPort -U $dbUser -f "scripts\init_database.sql"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Database initialized successfully!" -ForegroundColor Green
        Write-Host "`nVerifying tables..." -ForegroundColor Cyan
        & $psqlCmd -h $dbHost -p $dbPort -U $dbUser -d $dbName -c "\dt"
    }
    else {
        Write-Host "`n❌ Database initialization failed!" -ForegroundColor Red
        exit 1
    }
}
finally {
    # Clear password
    $env:PGPASSWORD = $null
}
