"""
Project Loader — load real-world projects from disk or git for workload evaluation.

Supports:
- Loading projects from a local directory
- Cloning from git repositories (cached)
- Filtering relevant source files by language
- Extracting function/class/export metadata
"""

import os
import re
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from datetime import datetime


@dataclass
class ProjectFile:
    """A single file within a loaded project."""
    path: str                    # Relative path within the project
    content: str                 # Full file content
    language: str                # Detected language (typescript, python, rust, etc.)
    size_bytes: int
    line_count: int
    
    # Parsed metadata
    exports: List[str] = field(default_factory=list)       # Exported symbols
    classes: List[str] = field(default_factory=list)       # Class names
    functions: List[Dict[str, Any]] = field(default_factory=list)  # Function defs
    imports: List[Dict[str, str]] = field(default_factory=list)    # Import statements


@dataclass
class Project:
    """A loaded project ready for task generation."""
    name: str
    root_path: str
    language: str                    # Primary language
    framework: str                   # Framework (nestjs, react, django, etc.)
    files: List[ProjectFile]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Aggregated stats
    total_files: int = 0
    total_lines: int = 0
    
    def __post_init__(self):
        self.total_files = len(self.files)
        self.total_lines = sum(f.line_count for f in self.files)
    
    def get_file_by_path(self, rel_path: str) -> Optional[ProjectFile]:
        """Find a file by its relative path."""
        for f in self.files:
            if f.path == rel_path:
                return f
        return None
    
    def get_files_by_language(self, language: str) -> List[ProjectFile]:
        """Get all files matching a language."""
        return [f for f in self.files if f.language == language]
    
    def get_files_by_pattern(self, pattern: str) -> List[ProjectFile]:
        """Get files whose path matches a glob-like pattern."""
        import fnmatch
        return [f for f in self.files if fnmatch.fnmatch(f.path, pattern)]


# ── Language/Framework detection ───────────────────────────────────

LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx"],
    "python": [".py"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "ruby": [".rb"],
    "php": [".php"],
}

FRAMEWORK_PATTERNS: Dict[str, List[str]] = {
    "nestjs": ["@nestjs/core", "@nestjs/common", "nest-cli.json"],
    "react": ["react", "react-dom", "react-scripts"],
    "nextjs": ["next", "next.config"],
    "django": ["django", "manage.py", "wsgi.py"],
    "flask": ["flask", "app.py"],
    "fastapi": ["fastapi"],
    "actix": ["actix-web", "Cargo.toml"],
    "axum": ["axum", "Cargo.toml"],
    "rocket": ["rocket", "Cargo.toml"],
}

IGNORED_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", "target",
    "dist", "build", ".next", ".nuxt", "venv", ".venv",
    "coverage", ".nyc_output", ".svelte-kit",
}

IGNORED_FILES: Set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    ".DS_Store", "*.min.js", "*.bundle.js",
}


class ProjectLoader:
    """Load real-world projects for workload evaluation.
    
    Supports loading from:
    1. A local directory path
    2. A git repository URL (clones automatically, cached)
    3. Built-in sample projects (demo/dry-run mode)
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".modellens" / "projects"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_project(self, source: str, language: Optional[str] = None) -> Project:
        """Load a project from a local path or git URL.
        
        Args:
            source: Local directory path or git repository URL
            language: Optional language hint for filtering
            
        Returns:
            Project with parsed files
        """
        if os.path.isdir(source):
            return self._load_local(source, language)
        elif self._is_git_url(source):
            return self._load_git(source, language)
        else:
            raise ValueError(
                f"Source '{source}' is neither a valid directory nor a git URL. "
                "Provide a local path or a git repository URL."
            )
    
    def load_builtin(self, name: str) -> Project:
        """Load a built-in sample project for demo/dry-run mode."""
        samples = self._get_builtin_projects()
        if name not in samples:
            available = ", ".join(samples.keys())
            raise ValueError(f"Built-in project '{name}' not found. Available: {available}")
        return self._generate_sample_project(name, samples[name])
    
    def list_builtin(self) -> Dict[str, str]:
        """List available built-in sample projects."""
        return {k: v["description"] for k, v in self._get_builtin_projects().items()}
    
    # ── Internal loaders ──────────────────────────────────────────
    
    def _load_local(self, path: str, language: Optional[str] = None) -> Project:
        """Load a project from a local directory."""
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Project directory not found: {root}")
        
        files = []
        for file_path in root.rglob("*"):
            if self._should_ignore(file_path, root):
                continue
            if file_path.is_file():
                parsed = self._parse_file(file_path, root, language)
                if parsed:
                    files.append(parsed)
        
        detected_lang, detected_framework = self._detect_project(files)
        
        return Project(
            name=root.name,
            root_path=str(root),
            language=language or detected_lang or "unknown",
            framework=detected_framework or "unknown",
            files=files,
            metadata={
                "source": "local",
                "loaded_at": datetime.now().isoformat(),
            },
        )
    
    def _load_git(self, url: str, language: Optional[str] = None) -> Project:
        """Clone a git repository and load it."""
        import hashlib
        
        repo_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        clone_path = self.cache_dir / repo_hash
        
        if clone_path.exists():
            # Update existing clone
            try:
                subprocess.run(
                    ["git", "pull", "--rebase"],
                    cwd=clone_path,
                    capture_output=True, text=True, timeout=60,
                )
            except Exception:
                pass  # Continue with existing clone
        else:
            # Fresh clone
            subprocess.run(
                ["git", "clone", "--depth", "1", url, str(clone_path)],
                capture_output=True, text=True, timeout=120,
            )
        
        if not clone_path.exists():
            raise RuntimeError(f"Failed to clone repository: {url}")
        
        return self._load_local(str(clone_path), language)
    
    # ── File parsing ──────────────────────────────────────────────
    
    def _parse_file(self, file_path: Path, root: Path, language_hint: Optional[str] = None) -> Optional[ProjectFile]:
        """Parse a single file and extract metadata."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
        
        ext = file_path.suffix.lower()
        rel_path = str(file_path.relative_to(root))
        
        # Detect language
        language = language_hint or self._detect_language(ext, file_path.name)
        if not language:
            return None  # Skip unknown file types
        
        pf = ProjectFile(
            path=rel_path,
            content=content,
            language=language,
            size_bytes=len(content.encode("utf-8")),
            line_count=content.count("\n") + 1,
        )
        
        # Parse metadata based on language
        if language == "typescript":
            pf.exports = self._parse_ts_exports(content)
            pf.classes = self._parse_ts_classes(content)
            pf.functions = self._parse_ts_functions(content)
            pf.imports = self._parse_ts_imports(content)
        elif language == "python":
            pf.exports = self._parse_py_exports(content)
            pf.classes = self._parse_py_classes(content)
            pf.functions = self._parse_py_functions(content)
            pf.imports = self._parse_py_imports(content)
        elif language == "rust":
            pf.exports = self._parse_rust_exports(content)
            pf.functions = self._parse_rust_functions(content)
        
        return pf
    
    def _should_ignore(self, path: Path, root: Path) -> bool:
        """Check if a path should be ignored."""
        rel = path.relative_to(root)
        parts = rel.parts
        
        # Ignore directories
        for part in parts[:-1]:
            if part in IGNORED_DIRS:
                return True
        
        # Ignore specific files
        if path.name in IGNORED_FILES:
            return True
        if any(path.name.endswith(suffix) for suffix in [".min.js", ".bundle.js", ".map"]):
            return True
        
        return False
    
    # ── Language/framework detection ──────────────────────────────
    
    @staticmethod
    def _detect_language(ext: str, filename: str) -> Optional[str]:
        """Detect programming language from file extension."""
        for lang, extensions in LANGUAGE_EXTENSIONS.items():
            if ext in extensions:
                return lang
        # Check for known config files
        if filename in ("Cargo.toml", "Cargo.lock"):
            return "rust"
        if filename == "go.mod":
            return "go"
        return None
    
    @staticmethod
    def _detect_project(files: List[ProjectFile]) -> tuple:
        """Detect primary language and framework from loaded files."""
        lang_counts: Dict[str, int] = {}
        framework_scores: Dict[str, int] = {}
        
        for f in files:
            lang_counts[f.language] = lang_counts.get(f.language, 0) + 1
            
            for framework, patterns in FRAMEWORK_PATTERNS.items():
                for pattern in patterns:
                    if pattern in f.content or pattern in f.path:
                        framework_scores[framework] = framework_scores.get(framework, 0) + 1
        
        primary_lang = max(lang_counts, key=lang_counts.get) if lang_counts else None
        primary_framework = max(framework_scores, key=framework_scores.get) if framework_scores else None
        
        return primary_lang, primary_framework
    
    # ── Built-in sample projects ──────────────────────────────────
    
    def _get_builtin_projects(self) -> Dict[str, Dict]:
        """Get built-in sample project definitions."""
        return {
            "nestjs-api": {
                "description": "NestJS REST API with Prisma, Auth, and Kafka (sample)",
                "language": "typescript",
                "framework": "nestjs",
            },
            "react-app": {
                "description": "React dashboard with state management and components (sample)",
                "language": "typescript",
                "framework": "react",
            },
            "python-cli": {
                "description": "Python CLI tool with Click and async I/O (sample)",
                "language": "python",
                "framework": "click",
            },
            "rust-server": {
                "description": "Rust HTTP server with Actix-web (sample)",
                "language": "rust",
                "framework": "actix",
            },
        }
    
    def _generate_sample_project(self, name: str, definition: Dict) -> Project:
        """Generate a sample project for demo/dry-run mode."""
        files = self._generate_sample_files(name, definition)
        return Project(
            name=name,
            root_path=f"[builtin:{name}]",
            language=definition["language"],
            framework=definition["framework"],
            files=files,
            metadata={
                "source": "builtin",
                "description": definition["description"],
                "loaded_at": datetime.now().isoformat(),
            },
        )
    
    def _generate_sample_files(self, name: str, definition: Dict) -> List[ProjectFile]:
        """Generate sample files for the built-in project."""
        samples = []
        
        if name == "nestjs-api":
            samples = self._sample_nestjs_files()
        elif name == "react-app":
            samples = self._sample_react_files()
        elif name == "python-cli":
            samples = self._sample_python_files()
        elif name == "rust-server":
            samples = self._sample_rust_files()
        
        return samples
    
    # ── TypeScript parsing utilities ──────────────────────────────
    
    @staticmethod
    def _parse_ts_exports(content: str) -> List[str]:
        """Extract exported symbols from TypeScript."""
        exports = []
        for match in re.finditer(r'export\s+(?:default\s+)?(?:class|function|interface|type|const|enum|abstract\s+class)\s+(\w+)', content):
            exports.append(match.group(1))
        return exports
    
    @staticmethod
    def _parse_ts_classes(content: str) -> List[str]:
        """Extract class names."""
        classes = []
        for match in re.finditer(r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)', content):
            classes.append(match.group(1))
        return classes
    
    @staticmethod
    def _parse_ts_functions(content: str) -> List[Dict[str, Any]]:
        """Extract function definitions with metadata."""
        functions = []
        for match in re.finditer(
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\w+))?\s*{',
            content,
        ):
            functions.append({
                "name": match.group(1),
                "params": match.group(2).strip() if match.group(2) else "",
                "return_type": match.group(3) if match.group(3) else "unknown",
            })
        # Also detect arrow functions assigned to const/let
        for match in re.finditer(
            r'(?:export\s+)?(?:const|let)\s+(\w+)\s*[=:]\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*(\w+))?\s*=>',
            content,
        ):
            functions.append({
                "name": match.group(1),
                "params": match.group(2).strip() if match.group(2) else "",
                "return_type": match.group(3) if match.group(3) else "unknown",
            })
        return functions
    
    @staticmethod
    def _parse_ts_imports(content: str) -> List[Dict[str, str]]:
        """Extract import statements."""
        imports = []
        for match in re.finditer(
            r'import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
            content,
        ):
            imports.append({"from": match.group(1)})
        return imports
    
    # ── Python parsing utilities ──────────────────────────────────
    
    @staticmethod
    def _parse_py_exports(content: str) -> List[str]:
        """Extract exported symbols (__all__ or top-level definitions)."""
        exports = []
        # Check __all__
        all_match = re.search(r'__all__\s*=\s*\[([^\]]*)\]', content)
        if all_match:
            exports = re.findall(r'[\'"]([^\'"]+)[\'"]', all_match.group(1))
        return exports
    
    @staticmethod
    def _parse_py_classes(content: str) -> List[str]:
        """Extract class definitions."""
        classes = []
        for match in re.finditer(r'(?:class\s+)(\w+)', content):
            classes.append(match.group(1))
        return classes
    
    @staticmethod
    def _parse_py_functions(content: str) -> List[Dict[str, Any]]:
        """Extract function definitions."""
        functions = []
        for match in re.finditer(
            r'(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*(\w+))?\s*:',
            content,
        ):
            functions.append({
                "name": match.group(1),
                "params": match.group(2).strip() if match.group(2) else "",
                "return_type": match.group(3) if match.group(3) else "None",
            })
        return functions
    
    @staticmethod
    def _parse_py_imports(content: str) -> List[Dict[str, str]]:
        """Extract import statements from Python."""
        imports = []
        for match in re.finditer(r'(?:from\s+(\S+)\s+)?import\s+(\S+)', content):
            imports.append({
                "from": match.group(1) or "",
                "name": match.group(2),
            })
        return imports
    
    # ── Rust parsing utilities ────────────────────────────────────
    
    @staticmethod
    def _parse_rust_exports(content: str) -> List[str]:
        """Extract pub symbols from Rust."""
        exports = []
        for match in re.finditer(r'pub\s+(?:fn|struct|enum|trait|type|const|mod|use)\s+(\w+)', content):
            exports.append(match.group(1))
        return exports
    
    @staticmethod
    def _parse_rust_functions(content: str) -> List[Dict[str, Any]]:
        """Extract function definitions from Rust."""
        functions = []
        for match in re.finditer(
            r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*(\w+))?\s*{',
            content,
        ):
            functions.append({
                "name": match.group(1),
                "params": match.group(2).strip() if match.group(2) else "",
                "return_type": match.group(3) if match.group(3) else "()",
            })
        return functions
    
    # ── Sample file generators ────────────────────────────────────
    
    def _sample_nestjs_files(self) -> List[ProjectFile]:
        """Generate sample NestJS project files."""
        return [
            ProjectFile(
                path="src/app.module.ts", language="typescript", size_bytes=300, line_count=12,
                content="""import { Module } from '@nestjs/common';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { KafkaModule } from './kafka/kafka.module';

@Module({
  imports: [PrismaModule, AuthModule, UsersModule, KafkaModule],
})
export class AppModule {}
""",
                exports=["AppModule"], classes=["AppModule"],
                functions=[], imports=[{"from": "@nestjs/common"}, {"from": "./prisma/prisma.module"}, {"from": "./auth/auth.module"}, {"from": "./users/users.module"}, {"from": "./kafka/kafka.module"}],
            ),
            ProjectFile(
                path="src/users/users.service.ts", language="typescript", size_bytes=1200, line_count=45,
                content="""import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';

@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreateUserDto) {
    const existing = await this.prisma.user.findUnique({ where: { email: dto.email } });
    if (existing) throw new ConflictException('Email already exists');
    return this.prisma.user.create({ data: dto });
  }

  async findAll(query: { page?: number; limit?: number }) {
    const page = query.page || 1;
    const limit = query.limit || 10;
    const [users, total] = await Promise.all([
      this.prisma.user.findMany({ skip: (page - 1) * limit, take: limit }),
      this.prisma.user.count(),
    ]);
    return { data: users, total, page, limit };
  }

  async findOne(id: string) {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  async update(id: string, dto: UpdateUserDto) {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) throw new NotFoundException('User not found');
    return this.prisma.user.update({ where: { id }, data: dto });
  }

  async remove(id: string) {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) throw new NotFoundException('User not found');
    return this.prisma.user.delete({ where: { id } });
  }
}
""",
                exports=["UsersService"], classes=["UsersService"],
                functions=[], imports=[],
            ),
            ProjectFile(
                path="src/users/users.controller.ts", language="typescript", size_bytes=800, line_count=30,
                content="""import { Controller, Get, Post, Body, Param, Delete, Put, Query } from '@nestjs/common';
import { UsersService } from './users.service';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';

@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Post()
  create(@Body() createUserDto: CreateUserDto) {
    return this.usersService.create(createUserDto);
  }

  @Get()
  findAll(@Query() query: { page?: number; limit?: number }) {
    return this.usersService.findAll(query);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.usersService.findOne(id);
  }

  @Put(':id')
  update(@Param('id') id: string, @Body() updateUserDto: UpdateUserDto) {
    return this.usersService.update(id, updateUserDto);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.usersService.remove(id);
  }
}
""",
                exports=["UsersController"], classes=["UsersController"],
                functions=[], imports=[],
            ),
        ]

    def _sample_react_files(self) -> List[ProjectFile]:
        """Generate sample React project files."""
        return [
            ProjectFile(
                path="src/App.tsx", language="typescript", size_bytes=500, line_count=20,
                content="""import React from 'react';
import { DashboardLayout } from './components/DashboardLayout';
import { ModelCard } from './components/ModelCard';
import { useModels } from './hooks/useModels';

export default function App() {
  const { models, loading, error } = useModels();
  return (
    <DashboardLayout>
      <h1>Model Dashboard</h1>
      {loading && <p>Loading models...</p>}
      {error && <p>Error: {error.message}</p>}
      <div className="models-grid">
        {models.map(model => <ModelCard key={model.id} model={model} />)}
      </div>
    </DashboardLayout>
  );
}
""",
                exports=["App"], classes=[], functions=[], imports=[],
            ),
            ProjectFile(
                path="src/hooks/useModels.ts", language="typescript", size_bytes=400, line_count=16,
                content="""import { useState, useEffect } from 'react';

interface Model {
  id: string;
  name: string;
  provider: string;
  status: 'running' | 'stopped';
}

export function useModels() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    fetch('/api/models')
      .then(res => res.json())
      .then(data => { setModels(data); setLoading(false); })
      .catch(err => { setError(err); setLoading(false); });
  }, []);

  return { models, loading, error };
}
""",
                exports=["useModels"], classes=[], functions=[], imports=[],
            ),
            ProjectFile(
                path="src/components/ModelCard.tsx", language="typescript", size_bytes=600, line_count=22,
                content="""import React from 'react';

interface ModelCardProps {
  model: { id: string; name: string; provider: string; status: string };
}

export function ModelCard({ model }: ModelCardProps) {
  return (
    <div className="model-card">
      <h3>{model.name}</h3>
      <p>Provider: {model.provider}</p>
      <span className={`status-badge ${model.status}`}>{model.status}</span>
    </div>
  );
}
""",
                exports=["ModelCard"], classes=[], functions=[], imports=[],
            ),
        ]

    def _sample_python_files(self) -> List[ProjectFile]:
        """Generate sample Python project files."""
        return [
            ProjectFile(
                path="cli.py", language="python", size_bytes=800, line_count=30,
                content="""import click
from typing import Optional

@click.group()
def cli():
    \"\"\"A sample CLI tool.\"\"\"
    pass

@cli.command()
@click.argument('name')
@click.option('--greeting', '-g', default='Hello')
def greet(name: str, greeting: str):
    \"\"\"Greet someone.\"\"\"
    click.echo(f'{greeting}, {name}!')

@cli.command()
@click.argument('numbers', nargs=-1, type=int)
@click.option('--operation', '-o', type=click.Choice(['sum', 'avg', 'max']), default='sum')
def math(numbers: tuple, operation: str):
    \"\"\"Perform math operations on numbers.\"\"\"
    if operation == 'sum':
        result = sum(numbers)
    elif operation == 'avg':
        result = sum(numbers) / len(numbers) if numbers else 0
    elif operation == 'max':
        result = max(numbers) if numbers else 0
    click.echo(f'Result: {result}')

if __name__ == '__main__':
    cli()
""",
                exports=["cli"], classes=[], functions=[{"name": "cli", "params": "", "return_type": "None"}, {"name": "greet", "params": "name, greeting", "return_type": "None"}, {"name": "math", "params": "numbers, operation", "return_type": "None"}],
                imports=[],
            ),
        ]

    def _sample_rust_files(self) -> List[ProjectFile]:
        """Generate sample Rust project files."""
        return [
            ProjectFile(
                path="src/main.rs", language="rust", size_bytes=600, line_count=25,
                content="""use actix_web::{web, App, HttpServer, HttpResponse, middleware};

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({"status": "ok"}))
}

async fn echo(body: web::Json<serde_json::Value>) -> HttpResponse {
    HttpResponse::Ok().json(body.into_inner())
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .route("/health", web::get().to(health))
            .route("/echo", web::post().to(echo))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
""",
                exports=["health", "echo", "main"], classes=[], functions=[], imports=[],
            ),
        ]

    @staticmethod
    def _is_git_url(url: str) -> bool:
        """Check if a string looks like a git repository URL."""
        patterns = [
            r'^https?://.*\.git$',
            r'^https?://(?:github|gitlab|bitbucket)\.(?:com|org)/\w+/\w+',
            r'^git@',
            r'^ssh://',
        ]
        return any(re.match(p, url) for p in patterns)
