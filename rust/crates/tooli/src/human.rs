//! Human-facing rendering. Override on a per-`Command` basis when the default
//! "pretty-print the JSON value" fallback isn't ideal.
//!
//! The previous implementation collapsed human output and JSON output into the
//! same `serde_json::to_string_pretty` path. That works but bakes in JSON
//! aesthetics for human readers and offers no extension point. `HumanRender`
//! is the explicit hook: commands that want a table, a one-liner, or a tree
//! view can implement it on their `Output` type.

use serde::Serialize;
use serde_json::Value;
use std::io::{self, Write};

/// Render a command result for a human reader.
pub trait HumanRender {
    /// Write a human-readable representation to `writer`.
    fn render_human(&self, writer: &mut dyn Write) -> io::Result<()>;
}

/// Default rendering: pretty-printed JSON for structured values, the string
/// itself for a single string result, and nothing for `null`. Commands that
/// want richer human output (tables, columns, summaries) should impl
/// `HumanRender` directly on their `Output` type and the runtime will pick it
/// up when the output mode is text/auto.
pub fn render_default<T: Serialize>(value: &T, writer: &mut dyn Write) -> io::Result<()> {
    let value = serde_json::to_value(value)
        .map_err(|err| io::Error::new(io::ErrorKind::InvalidData, err))?;
    match value {
        Value::Null => Ok(()),
        Value::String(text) => writeln!(writer, "{text}"),
        other => {
            let rendered = serde_json::to_string_pretty(&other)
                .map_err(|err| io::Error::new(io::ErrorKind::InvalidData, err))?;
            writeln!(writer, "{rendered}")
        }
    }
}
