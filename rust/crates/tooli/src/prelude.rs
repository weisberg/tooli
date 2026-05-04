//! Convenient imports for building Tooli CLIs.

pub use crate::{
    command_schema, Annotation, App, Command, CommandMeta, Context, Dispatch, ErrorCategory,
    GlobalOptions, HumanRender, InputSource, OutputMode, Result, SecretString, Suggestion,
    ToolError, TooliCli,
};
pub use clap::{Args, CommandFactory, Parser, Subcommand};
pub use schemars::JsonSchema;
pub use serde::Serialize;
