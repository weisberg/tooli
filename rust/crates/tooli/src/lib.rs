//! Lean Rust runtime for building agent-friendly CLI tools.
//!
//! Tooli is a thin layer over `clap` that adds a stable JSON envelope, structured
//! errors, JSON Schema export, and a non-interactive contract suitable for
//! agents and scripts. Most CLIs can wire it up in a five-line `main()`:
//!
//! ```ignore
//! use tooli::prelude::*;
//!
//! #[derive(Debug, Parser)]
//! struct Cli {
//!     #[command(flatten)]
//!     global: GlobalOptions,
//!     #[command(subcommand)]
//!     command: Option<Commands>,
//! }
//!
//! #[derive(Debug, Subcommand, TooliCli)]
//! enum Commands {
//!     Find(FindArgs),
//! }
//!
//! fn main() -> std::process::ExitCode {
//!     let app = App::new("file-tools").version(env!("CARGO_PKG_VERSION"));
//!     if let Some(exit) = app.handle_pre_parse_intents::<Commands>() {
//!         return exit;
//!     }
//!     let cli = match Cli::try_parse() {
//!         Ok(cli) => cli,
//!         Err(err) => return app.exit_for_clap_error(err),
//!     };
//!     app.dispatch::<Commands>(&cli.global, cli.command)
//! }
//! ```
//!
//! ## JSON naming policy
//!
//! Two naming conventions coexist on purpose, matching the Python Tooli
//! contract:
//!
//! - **snake_case**: envelope and error fields (`duration_ms`, `dry_run`,
//!   `is_retryable`, `caller_id`).
//! - **camelCase**: schema/metadata hint fields, for MCP compatibility
//!   (`inputSchema`, `outputSchema`, `readOnlyHint`, `requiresConfirmation`).
//!
//! Each module documents its own convention.

mod app;
mod capability;
mod command;
mod context;
mod envelope;
mod error;
mod human;
mod input;
mod intent;
mod manifest;
mod meta;
mod output;
pub mod prelude;
mod schema;
mod util;

pub use app::App;
pub use capability::{capabilities_allowed, enforce_capabilities};
pub use command::{Command, Dispatch};
pub use context::{Context, ContextBuilder};
pub use envelope::{EnvelopeMeta, ErrorEnvelope, SuccessEnvelope};
pub use error::{ErrorCategory, Suggestion, ToolError};
pub use human::HumanRender;
pub use input::{InputSource, SecretString};
pub use intent::{detect as detect_intent, detect_from_args as detect_intent_from_args, Intent};
pub use manifest::{AgentManifest, GlobalFlag, SkillGuide, SCHEMA_VERSION};
pub use meta::{Annotation, AnnotationSet, CommandMeta, Example};
pub use output::{resolve_output_mode, GlobalOptions, OutputMode};
pub use schema::{command_schema, CommandSchema};

pub use tooli_macros::TooliCli;

/// Crate-wide result type for Tooli command implementations.
pub type Result<T> = std::result::Result<T, ToolError>;
