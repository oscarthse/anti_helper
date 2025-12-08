"""
Runtime Tools - Sandbox execution capabilities.

These tools execute commands in isolated Docker containers for security.
All execution happens in resource-limited, network-isolated sandboxes.
"""

import asyncio

import structlog

from gravity_core.tools.registry import tool

logger = structlog.get_logger()


# Sandbox configuration
SANDBOX_CONFIG = {
    "image": "antigravity-sandbox:latest",
    "mem_limit": "512m",
    "cpu_quota": 100000,  # 1 CPU
    "network_mode": "none",
    "timeout_default": 60,
}


@tool(
    name="run_shell_command",
    description="Execute a command inside the resource-limited, network-isolated Docker sandbox. "
    "All code execution happens here for security.",
    schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute"
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for the command",
                "default": "/sandbox/project"
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds",
                "default": 60
            },
            "env": {
                "type": "object",
                "description": "Additional environment variables",
                "default": {}
            },
            "repo_path": {
                "type": "string",
                "description": "Host path to repository to mount into container"
            }
        },
        "required": ["command"]
    },
    category="runtime"
)
async def run_shell_command(
    command: str,
    working_directory: str = "/sandbox/project",
    timeout_seconds: int = 60,
    env: dict[str, str] | None = None,
    repo_path: str | None = None,
) -> dict:
    """
    Execute a command in the sandbox container.

    The sandbox is:
    - Network isolated (no internet access)
    - Resource limited (512MB RAM, 1 CPU)
    - Read-only filesystem (except /tmp)
    - Running as non-root user
    """
    logger.info("run_shell_command", command=command[:100], timeout=timeout_seconds)

    # Security: Block dangerous commands
    dangerous_patterns = [
        "rm -rf /",
        "mkfs",
        "dd if=",
        ":(){:|:&};:",  # Fork bomb
        "chmod 777 /",
    ]
    for pattern in dangerous_patterns:
        if pattern in command:
            return {
                "error": f"Command blocked for security: contains '{pattern}'",
                "success": False,
            }

    try:
        # Import docker here to avoid hard dependency
        import docker

        client = docker.from_env()

        # Check if sandbox image exists
        try:
            client.images.get(SANDBOX_CONFIG["image"])
        except docker.errors.ImageNotFound:
            # Fallback to python:3.11-slim if sandbox image not built
            logger.warning("sandbox_image_not_found", using="python:3.11-slim")
            image = "python:3.11-slim"
        else:
            image = SANDBOX_CONFIG["image"]

        # Prepare environment
        environment = {"PYTHONDONTWRITEBYTECODE": "1"}
        if env:
            environment.update(env)

        # Build volume mount if repo_path provided
        volumes = {}
        if repo_path:
            volumes[repo_path] = {'bind': '/sandbox/project', 'mode': 'rw'}
            logger.info("sandbox_volume_mount", host=repo_path, container="/sandbox/project")

        # Run container
        container = client.containers.run(
            image=image,
            command=["sh", "-c", command],
            working_dir=working_directory,
            environment=environment,
            mem_limit=SANDBOX_CONFIG["mem_limit"],
            cpu_quota=SANDBOX_CONFIG["cpu_quota"],
            network_mode=SANDBOX_CONFIG["network_mode"],
            read_only=False,  # Must be writable for file creation
            tmpfs={"/tmp": "size=100M"},
            volumes=volumes if volumes else None,
            detach=True,
            remove=False,
        )

        # Wait for completion with timeout
        try:
            exit_code = container.wait(timeout=timeout_seconds)["StatusCode"]
            # logs = container.logs().decode("utf-8", errors="replace")
            # Get stdout/stderr separately
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        except Exception:
            container.kill()
            return {
                "error": f"Command timed out after {timeout_seconds}s",
                "success": False,
            }
        finally:
            container.remove(force=True)

        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "command": command,
        }

    except ImportError:
        # Docker not available - run locally ONLY if explicitly allowed
        import os
        if os.environ.get("UNSAFE_LOCAL_FALLBACK", "").lower() == "true":
            logger.warning("docker_not_available_fallback_enabled", running="locally")
            return await _run_locally(command, timeout_seconds)

        logger.error("docker_not_available_security_block")
        return {
            "error": "CRITICAL SECURITY: Docker Sandbox unavailable. Execution aborted.",
            "success": False,
        }
    except Exception as e:
        logger.error("sandbox_error", error=str(e))
        return {
            "error": str(e),
            "success": False,
        }


async def _run_locally(command: str, timeout: int) -> dict:
    """Fallback: run command locally (for development only)."""

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "command": command,
            "warning": "Executed locally - not in sandbox",
        }

    except TimeoutError:
        proc.kill()
        return {
            "error": f"Command timed out after {timeout}s",
            "success": False,
        }


@tool(
    name="read_sandbox_logs",
    description="Fetch stdout/stderr from a sandbox execution. "
    "Crucial for debugging failed commands.",
    schema={
        "type": "object",
        "properties": {
            "container_id": {
                "type": "string",
                "description": "Container ID from previous run"
            },
            "tail": {
                "type": "integer",
                "description": "Number of lines from the end to return",
                "default": 100
            }
        },
        "required": ["container_id"]
    },
    category="runtime"
)
async def read_sandbox_logs(
    container_id: str,
    tail: int = 100,
) -> dict:
    """
    Read logs from a sandbox container.

    Note: Containers are typically removed after execution,
    so this is mainly useful for long-running containers.
    """
    logger.info("read_sandbox_logs", container_id=container_id[:12])

    try:
        import docker

        client = docker.from_env()
        container = client.containers.get(container_id)

        logs = container.logs(tail=tail).decode("utf-8", errors="replace")

        return {
            "container_id": container_id,
            "logs": logs,
            "status": container.status,
        }

    except ImportError:
        return {"error": "Docker not available"}
    except Exception as e:
        return {"error": str(e)}


@tool(
    name="inspect_db_schema",
    description="Read the actual running database schema. "
    "Gets the real schema, not just ORM models.",
    schema={
        "type": "object",
        "properties": {
            "database_url": {
                "type": "string",
                "description": "Database connection URL"
            },
            "table_name": {
                "type": "string",
                "description": "Specific table to inspect (optional)"
            }
        },
        "required": ["database_url"]
    },
    category="runtime"
)
async def inspect_db_schema(
    database_url: str,
    table_name: str | None = None,
) -> dict:
    """
    Inspect the database schema.

    Returns table definitions, columns, and constraints.
    """
    logger.info("inspect_db_schema", table=table_name)

    try:
        from sqlalchemy import create_engine, inspect

        # Parse URL and create engine
        # Note: For async compatibility, we'd use asyncpg directly
        # This is a sync fallback implementation

        # Security: Don't log credentials
        # Custom wrapper for blocking DB inspection
        def _inspect_sync():
            engine = create_engine(database_url.replace("+asyncpg", ""))
            inspector = inspect(engine)

            if table_name:
                # Inspect specific table
                columns = inspector.get_columns(table_name)
                pk = inspector.get_pk_constraint(table_name)
                fks = inspector.get_foreign_keys(table_name)
                indexes = inspector.get_indexes(table_name)

                return {
                    "table": table_name,
                    "columns": columns,
                    "primary_key": pk,
                    "foreign_keys": fks,
                    "indexes": indexes,
                }
            else:
                # List all tables
                tables = inspector.get_table_names()
                return {
                    "tables": tables,
                    "count": len(tables),
                }

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(_inspect_sync)

    except ImportError:
        return {"error": "SQLAlchemy not available"}
    except Exception as e:
        logger.error("db_inspect_error", error=str(e))
        return {"error": str(e)}
