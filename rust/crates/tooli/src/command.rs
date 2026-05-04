//! The `Command` and `Dispatch` traits.

use crate::human::HumanRender;
use crate::{App, CommandMeta, Context, GlobalOptions, OutputMode, Result};
use schemars::JsonSchema;
use serde::Serialize;
use std::io::{self, Write};
use std::process::ExitCode;

/// A typed command that can be executed by the Tooli runtime.
///
/// Implement this for a Clap `Args` struct. The argument struct supplies the
/// input schema; `Self::Output` supplies the output schema and the value the
/// runtime serializes into a Tooli envelope.
pub trait Command: Sized + JsonSchema {
    /// Serializable, schema-compatible command output.
    type Output: Serialize + JsonSchema;

    /// Execute the command.
    fn run(self, ctx: Context) -> Result<Self::Output>;

    /// Optional agent-facing metadata for this command.
    fn meta() -> CommandMeta {
        CommandMeta::default()
    }

    /// Render `output` for a human reader. The default delegates to
    /// `HumanRender` if implemented, falling back to pretty-printed JSON.
    fn render_human(output: &Self::Output, writer: &mut dyn Write) -> io::Result<()> {
        render_with_human_fallback(output, writer)
    }
}

/// Internal helper that prefers a `HumanRender` impl on `T` when one exists,
/// otherwise pretty-prints the serde_json `Value`. We use specialization-by-
/// trait-bound on the explicit override path via `Command::render_human`; the
/// default implementation always falls back to JSON.
pub(crate) fn render_with_human_fallback<T: Serialize>(
    value: &T,
    writer: &mut dyn Write,
) -> io::Result<()> {
    crate::human::render_default(value, writer)
}

/// Glue layer between a Clap `Subcommand` enum and the Tooli runtime.
///
/// In hand-written code the trait can be implemented directly. In practice the
/// `#[derive(TooliCli)]` macro from `tooli-macros` generates the implementation
/// from the subcommand enum's variants.
pub trait Dispatch: Sized {
    /// CLI-facing names for every variant, in declaration order.
    fn names() -> &'static [&'static str];

    /// Run the matched subcommand.
    fn dispatch(self, app: &App, options: &GlobalOptions) -> ExitCode;

    /// Emit the schema for `name`, or `None` if `name` is not one of `names()`.
    fn dispatch_schema(name: &str, app: &App, mode: OutputMode) -> Option<ExitCode>;

    /// Schemas for every command, used by the agent manifest.
    fn schemas() -> Vec<crate::CommandSchema>;
}

// `HumanRender` is intentionally not auto-derived for every `Serialize`. If
// users want custom human rendering they should `impl HumanRender for MyOutput`
// and override `Command::render_human` to call into it. We expose the trait
// here so the override site is obvious.
#[allow(dead_code)]
fn _human_render_is_implemented<T: HumanRender>(_value: &T) {}
