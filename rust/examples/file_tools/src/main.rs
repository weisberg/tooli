use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use tooli::prelude::*;

#[derive(Debug, Parser)]
#[command(name = "file-tools", version, about = "Example Tooli Rust CLI")]
struct Cli {
    #[command(flatten)]
    global: GlobalOptions,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Debug, Subcommand, TooliCli)]
enum Commands {
    /// Find files matching a simple glob pattern.
    Find(FindArgs),
    /// Read a file or stdin and return a compact summary.
    Read(ReadArgs),
}

#[derive(Debug, Args, JsonSchema)]
struct FindArgs {
    /// Glob pattern to match, such as '*.rs' or 'Cargo.*'.
    pattern: String,

    /// Root directory to search from.
    #[arg(long, default_value = ".")]
    #[schemars(default = "default_root")]
    root: String,
}

#[derive(Debug, Serialize, JsonSchema)]
struct FileHit {
    path: String,
    size: u64,
}

#[derive(Debug, Args, JsonSchema)]
struct ReadArgs {
    /// File path to read, or '-' for stdin.
    source: InputSource,
}

#[derive(Debug, Serialize, JsonSchema)]
struct ReadSummary {
    bytes: usize,
    lines: usize,
    preview: String,
}

fn default_root() -> String {
    ".".to_string()
}

impl Command for FindArgs {
    type Output = Vec<FileHit>;

    fn meta() -> CommandMeta {
        CommandMeta::new()
            .description("Find files matching a simple glob pattern.")
            .annotation(Annotation::ReadOnly)
            .annotation(Annotation::Idempotent)
            .capability("fs:read")
            .example_with_description(
                "find '*.rs' --root ./src",
                "Find Rust source files below ./src.",
            )
    }

    fn run(self, _ctx: Context) -> tooli::Result<Self::Output> {
        if self.pattern.trim().is_empty() {
            return Err(ToolError::input("pattern must not be empty")
                .code("E1001")
                .field("pattern")
                .retryable(true)
                .suggestion(Suggestion::retry(
                    "Provide a non-empty pattern such as '*.rs'.",
                    "file-tools find '*.rs'",
                )));
        }

        let root = PathBuf::from(&self.root);
        if !root.exists() {
            return Err(
                ToolError::state(format!("root path does not exist: {}", root.display()))
                    .code("E3001")
                    .field("root"),
            );
        }

        let mut hits = Vec::new();
        visit_dir(&root, &self.pattern, &mut hits)?;
        hits.sort_by(|left, right| left.path.cmp(&right.path));
        Ok(hits)
    }

    /// Demonstrate `Command::render_human` overriding the default
    /// JSON-pretty-print fallback. For text/auto output, list one path per
    /// line — what a human actually wants from `find`.
    fn render_human(output: &Self::Output, writer: &mut dyn Write) -> io::Result<()> {
        for hit in output {
            writeln!(writer, "{}", hit.path)?;
        }
        Ok(())
    }
}

impl Command for ReadArgs {
    type Output = ReadSummary;

    fn meta() -> CommandMeta {
        CommandMeta::new()
            .description("Read a file or stdin and return a compact summary.")
            .annotation(Annotation::ReadOnly)
            .annotation(Annotation::Idempotent)
            .capability("fs:read")
            .example_with_description("read ./README.md", "Summarize README.md.")
            .example_with_description("read -", "Read text from stdin.")
    }

    fn run(self, _ctx: Context) -> tooli::Result<Self::Output> {
        let content = self.source.read_to_string().map_err(|err| {
            ToolError::state(format!("failed to read input source: {err}")).code("E3002")
        })?;
        let preview: String = content.chars().take(120).collect();

        Ok(ReadSummary {
            bytes: content.len(),
            lines: content.lines().count(),
            preview,
        })
    }
}

fn main() -> ExitCode {
    let app = App::new("file-tools")
        .version(env!("CARGO_PKG_VERSION"))
        .description("Example Tooli Rust CLI for file discovery and file/stdin reading.");

    if let Some(exit) = app.handle_pre_parse_intents::<Commands>() {
        return exit;
    }

    let cli = match Cli::try_parse() {
        Ok(cli) => cli,
        Err(err) => return app.exit_for_clap_error(err),
    };

    app.dispatch::<Commands>(&cli.global, cli.command)
}

fn visit_dir(root: &Path, pattern: &str, hits: &mut Vec<FileHit>) -> tooli::Result<()> {
    let entries = fs::read_dir(root).map_err(|err| {
        ToolError::runtime(format!(
            "failed to read directory {}: {err}",
            root.display()
        ))
        .code("E4001")
    })?;

    for entry in entries {
        let entry = entry.map_err(|err| {
            ToolError::runtime(format!("failed to inspect directory entry: {err}")).code("E4002")
        })?;
        let path = entry.path();
        let metadata = entry.metadata().map_err(|err| {
            ToolError::runtime(format!(
                "failed to read metadata for {}: {err}",
                path.display()
            ))
            .code("E4003")
        })?;

        if metadata.is_dir() {
            visit_dir(&path, pattern, hits)?;
            continue;
        }

        let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
            continue;
        };
        if matches_pattern(name, pattern) {
            hits.push(FileHit {
                path: path.display().to_string(),
                size: metadata.len(),
            });
        }
    }

    Ok(())
}

fn matches_pattern(name: &str, pattern: &str) -> bool {
    if pattern == "*" {
        return true;
    }

    if !pattern.contains('*') {
        return name == pattern;
    }

    let parts: Vec<&str> = pattern.split('*').collect();
    let mut remainder = name;

    if let Some(first) = parts.first().filter(|part| !part.is_empty()) {
        if !remainder.starts_with(first) {
            return false;
        }
        remainder = &remainder[first.len()..];
    }

    for part in parts
        .iter()
        .skip(1)
        .take(parts.len().saturating_sub(2))
        .filter(|part| !part.is_empty())
    {
        let Some(index) = remainder.find(part) else {
            return false;
        };
        remainder = &remainder[index + part.len()..];
    }

    if let Some(last) = parts.last().filter(|part| !part.is_empty()) {
        return remainder.ends_with(last);
    }

    true
}

#[cfg(test)]
mod tests {
    use super::matches_pattern;

    #[test]
    fn simple_star_patterns_work() {
        assert!(matches_pattern("main.rs", "*.rs"));
        assert!(matches_pattern("Cargo.toml", "Cargo.*"));
        assert!(matches_pattern("abc.txt", "a*.txt"));
        assert!(!matches_pattern("main.py", "*.rs"));
    }
}
