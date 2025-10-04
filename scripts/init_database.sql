-- Database initialization script for Multi-Agent Task Execution System
-- Run this with: psql -U postgres -h localhost -p 5432 -f scripts/init_database.sql

-- Drop existing database if it exists
DROP DATABASE IF EXISTS multi_agent_db;

-- Create new database
CREATE DATABASE multi_agent_db;

-- Connect to the new database
\c multi_agent_db

-- Create tasks table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    subtasks JSONB,
    result JSONB,
    error TEXT,
    CONSTRAINT description_length CHECK (LENGTH(description) BETWEEN 10 AND 5000)
);

-- Create indexes for tasks table
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- Create subtask_results table
CREATE TABLE subtask_results (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL,
    subtask_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    output JSONB,
    error TEXT,
    execution_time FLOAT NOT NULL CHECK (execution_time > 0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CHECK ((status = 'completed' AND output IS NOT NULL) OR (status = 'failed' AND error IS NOT NULL))
);

-- Create indexes for subtask_results table
CREATE INDEX idx_subtask_results_task ON subtask_results(task_id);
CREATE INDEX idx_subtask_results_agent ON subtask_results(agent_id);
CREATE INDEX idx_subtask_results_created ON subtask_results(created_at DESC);

-- Create agent_logs table
CREATE TABLE agent_logs (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT,
    log_level TEXT NOT NULL CHECK (log_level IN ('INFO', 'DEBUG', 'ERROR', 'WARN')),
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for agent_logs table
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_id);
CREATE INDEX idx_agent_logs_task ON agent_logs(task_id);
CREATE INDEX idx_agent_logs_level ON agent_logs(log_level);
CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC);

-- Display table information
\dt
\d tasks
\d subtask_results
\d agent_logs
